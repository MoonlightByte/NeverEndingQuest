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
register_callsite("T047", "core/managers/level_up_manager.py", 287)
register_callsite("T048", "core/managers/level_up_manager.py", 329)
from utils.file_operations import safe_read_json
from updates.update_character_info import update_character_info, normalize_character_name
from utils.character_sheet_contract import extract_json_object
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
        self._started = False
        self.conversation_file = "modules/conversation_history/level_up_conversation.json"

    def start(self):
        """
        Initializes the session and returns the first AI message.
        Returns:
            str: The initial greeting/prompt from the AI.
        """
        if self._started:
            return self.summary or "The level up process has already started."

        self._started = True
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
        return self._handle_assistant_response(ai_response)

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
        return self._handle_assistant_response(ai_response)

    def _handle_assistant_response(self, ai_response, allow_correction=True):
        """Persist and process one T047 assistant turn exactly once."""
        self.conversation.append({"role": "assistant", "content": ai_response})

        # The assistant turn is the recovery journal for this workflow. Persist it
        # before validation or character mutation so a rejected response, process
        # interruption, or failed update never disappears from the session record.
        self._save_conversation()

        update_params = self._extract_update_action(ai_response)
        if update_params is None:
            return ai_response

        print("[Level Up Session] AI returned final action. Validating...")
        is_valid, validation_msg = self._validate_level_up_response(ai_response)
        if not is_valid:
            if allow_correction:
                return self._request_single_correction(validation_msg)

            self.success = False
            self.summary = (
                "Error: The corrected final level-up update was rejected. "
                f"Reason: {validation_msg}"
            )
            self.conversation.append(
                {
                    "role": "user",
                    "content": (
                        "The corrected final update was still invalid. Do not "
                        "assume the level up was applied. Continue the interview "
                        "and produce a new complete final action after resolving "
                        f"this validation result: {validation_msg}"
                    ),
                }
            )
            self._save_conversation()
            return ai_response

        changes, preparation_error = self._prepare_level_up_changes(update_params)
        if preparation_error:
            return self._record_update_failure(preparation_error)

        try:
            update_succeeded = update_character_info(self.character_name, changes)
        except Exception as exc:
            print(f"[ERROR] Applying final level-up update: {exc}")
            update_succeeded = False

        if not update_succeeded:
            return self._record_update_failure(
                "The final character update failed to apply."
            )

        print(f"[Level Up Session] SUCCESS! {self.character_name} updated.")
        self.is_complete = True
        self.success = True
        self.summary = self._generate_level_up_summary(ai_response)
        # Return the full AI response so the main DM can generate proper narration.
        return ai_response

    def _request_single_correction(self, validation_msg):
        """Ask T047 for one correction and immediately process that response."""
        correction_prompt = (
            "That final JSON was not valid. "
            f"Reason: {validation_msg}. Please correct the JSON and provide it "
            "again, containing ALL the level up changes."
        )
        self.conversation.append({"role": "user", "content": correction_prompt})
        self._save_conversation()

        corrected_response = self._get_ai_response()
        return self._handle_assistant_response(
            corrected_response,
            allow_correction=False,
        )

    def _record_update_failure(self, reason):
        """Keep a failed final turn recoverable without replaying it automatically."""
        self.is_complete = False
        self.success = False
        self.summary = f"Error: {reason}"
        self.conversation.append(
            {
                "role": "user",
                "content": (
                    "The validated character update was not applied. Do not "
                    "assume the level up succeeded and do not reuse the prior "
                    "action implicitly. After the user asks to retry, provide a "
                    "new complete updateCharacterInfo action."
                ),
            }
        )
        self._save_conversation()
        return self.summary

    @staticmethod
    def _prepare_level_up_changes(update_params):
        """Return a JSON delta with experience_points removed deterministically."""
        if not isinstance(update_params, dict) or "changes" not in update_params:
            return None, "The final action did not contain a changes object."

        changes = update_params["changes"]
        if isinstance(changes, str):
            try:
                changes = json.loads(changes)
            except json.JSONDecodeError:
                return None, "The final action changes value was not valid JSON."
        elif isinstance(changes, dict):
            changes = dict(changes)
        else:
            return None, "The final action changes value was not a JSON object."

        if not isinstance(changes, dict):
            return None, "The final action changes value was not a JSON object."

        if "experience_points" in changes:
            print("[Level Up Session] Removing experience_points from level-up changes")
            changes.pop("experience_points", None)

        return json.dumps(changes), None

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
                _request_provider=MODEL_PROVIDER,
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
                _request_provider=MODEL_PROVIDER,
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
        except Exception as e:
            print(f"[ERROR] Validating AI response: {e}")
            return False, "Validation system error."

        try:
            validation_result = self._parse_level_up_validation_response(
                validation_response
            )
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"[ERROR] Malformed level-up validation response: {e}")
            return False, f"Malformed validation response: {e}"

        return (
            validation_result["valid"],
            self._format_level_up_validation_message(validation_result),
        )

    @staticmethod
    def _parse_level_up_validation_response(validation_response):
        """Parse and validate T048's documented structured verdict contract."""
        json_blob = extract_json_object(validation_response)
        if json_blob is None:
            raise ValueError("no JSON object found")

        result = json.loads(json_blob)
        if not isinstance(result, dict):
            raise ValueError("validation result must be a JSON object")

        required_fields = {"valid", "errors", "warnings", "recommendation"}
        actual_fields = set(result)
        if actual_fields != required_fields:
            missing_fields = required_fields.difference(actual_fields)
            unexpected_fields = actual_fields.difference(required_fields)
            shape_errors = []
            if missing_fields:
                shape_errors.append(
                    "missing required field(s): "
                    + ", ".join(sorted(missing_fields))
                )
            if unexpected_fields:
                shape_errors.append(
                    "unexpected field(s): "
                    + ", ".join(sorted(unexpected_fields))
                )
            raise ValueError("; ".join(shape_errors))

        if type(result["valid"]) is not bool:
            raise ValueError("'valid' must be a boolean")

        for field in ("errors", "warnings"):
            if not isinstance(result[field], list) or not all(
                isinstance(item, str) for item in result[field]
            ):
                raise ValueError(f"'{field}' must be an array of strings")

        if not isinstance(result["recommendation"], str):
            raise ValueError("'recommendation' must be a string")

        return result

    @staticmethod
    def _format_level_up_validation_message(validation_result):
        """Create actionable correction text from a parsed T048 verdict."""
        parts = []
        if validation_result["errors"]:
            parts.append("Errors: " + "; ".join(validation_result["errors"]))
        if validation_result["warnings"]:
            parts.append("Warnings: " + "; ".join(validation_result["warnings"]))
        if validation_result["recommendation"].strip():
            parts.append(
                "Recommendation: " + validation_result["recommendation"].strip()
            )

        if parts:
            return " ".join(parts)
        return (
            "Validation passed."
            if validation_result["valid"]
            else "Validation failed."
        )


    @staticmethod
    def _extract_update_action(ai_response):
        try:
            if not isinstance(ai_response, str):
                return None
            if not (ai_response.strip().startswith('{') and ai_response.strip().endswith('}')):
                return None
            response_data = json.loads(ai_response)
            if not isinstance(response_data, dict):
                return None
            actions = response_data.get("actions", [])
            if not isinstance(actions, list):
                return None
            for action in actions:
                if not isinstance(action, dict):
                    continue
                if action.get("action") == "updateCharacterInfo":
                    parameters = action.get("parameters")
                    return parameters if isinstance(parameters, dict) else {}
        except (json.JSONDecodeError, AttributeError, TypeError):
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