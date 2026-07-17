#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Quest Player Formatter Module
Uses AI to convert DM-oriented quest descriptions into immersive player-friendly journal entries
"""

import hashlib
import json
import os
import stat
from datetime import datetime
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T090", "utils/quest_player_formatter.py", 98)
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json, safe_write_json
from utils.path_transaction_lock import path_transaction_lock
from utils.module_refresh_lock import (
    module_refresh_lock,
)
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.encoding_utils import sanitize_text

# Set script name for logging
set_script_name("quest_player_formatter")

# Constants
TEMPERATURE = 0.3
MAX_RETRIES = 3
SOURCE_RETRY_LIMIT = 3


class _QuestSourceDriftError(RuntimeError):
    """The plot or its owning directory changed during T090 generation."""

def _quest_file_lock(player_quests_path):
    """Lock a complete derived-file transaction across threads/processes."""
    return path_transaction_lock(player_quests_path)


def _path_identity(path):
    metadata = os.lstat(path)
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        stat.S_IFMT(metadata.st_mode),
    )


def _capture_plot_source(module_dir, plot_path):
    """Capture exact contained plot bytes plus stable path identities."""
    canonical_module = os.path.abspath(os.path.normpath(os.fspath(module_dir)))
    canonical_plot = os.path.abspath(os.path.normpath(os.fspath(plot_path)))
    module_metadata = os.lstat(canonical_module)
    if stat.S_ISLNK(module_metadata.st_mode) or not stat.S_ISDIR(
        module_metadata.st_mode
    ):
        raise _QuestSourceDriftError("Module target is not an ordinary directory")

    module_real = os.path.realpath(canonical_module)
    module_identity = (
        int(module_metadata.st_dev),
        int(module_metadata.st_ino),
        stat.S_IFMT(module_metadata.st_mode),
    )
    plot_real = os.path.realpath(canonical_plot)
    try:
        contained = os.path.commonpath([module_real, plot_real]) == module_real
    except ValueError:
        contained = False
    if not contained:
        raise _QuestSourceDriftError("Plot source is outside its module directory")

    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(canonical_plot, flags)
    try:
        file_metadata = os.fstat(descriptor)
        if not stat.S_ISREG(file_metadata.st_mode):
            raise _QuestSourceDriftError("Plot source is not a regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    file_identity = (
        int(file_metadata.st_dev),
        int(file_metadata.st_ino),
        stat.S_IFMT(file_metadata.st_mode),
    )
    # The file descriptor gives us stable bytes, but prove those bytes still
    # belong to the same directory entry and module tree at snapshot return.
    # Otherwise an atomic replacement during capture could combine an old
    # file with a new directory identity into a snapshot that never existed.
    if (
        _path_identity(canonical_module) != module_identity
        or os.path.realpath(canonical_module) != module_real
        or _path_identity(canonical_plot) != file_identity
        or os.path.realpath(canonical_plot) != plot_real
    ):
        raise _QuestSourceDriftError("Plot source changed during snapshot")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _QuestSourceDriftError("Plot source is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise _QuestSourceDriftError("Plot source is not a JSON object")
    return {
        "module_path": canonical_module,
        "module_real": module_real,
        "module_identity": module_identity,
        "plot_path": canonical_plot,
        "plot_real": plot_real,
        "plot_identity": file_identity,
        "digest": hashlib.sha256(raw).hexdigest(),
        "payload": payload,
    }


def _plot_source_matches(snapshot):
    try:
        current = _capture_plot_source(
            snapshot["module_path"], snapshot["plot_path"]
        )
    except (OSError, _QuestSourceDriftError):
        return False
    return all(
        current[field] == snapshot[field]
        for field in (
            "module_path",
            "module_real",
            "module_identity",
            "plot_path",
            "plot_real",
            "plot_identity",
            "digest",
        )
    )


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
            mini_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            mini_cfg = config.MINI_UTIL_LMSTUDIO
        else:  # legacy
            mini_cfg = config.MINI_UTIL_LEGACY

        response = capture_and_fanout("T090", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            model=mini_cfg["model"],
            temperature=TEMPERATURE,
            response_format={"type": "json_object"},
            **{
                k: v
                for k, v in mini_cfg.items()
                if k not in {"model", "response_format"}
            })
        
        ai_response = response.choices[0].message.content.strip()
        
        # Parse the response
        try:
            # Remove any markdown code blocks if present
            if ai_response.startswith("```"):
                ai_response = ai_response.split("```")[1]
                if ai_response.startswith("json"):
                    ai_response = ai_response[4:]

            reformatted = json.loads(ai_response)

            if type(reformatted) is not dict:
                raise ValueError("T090 response must be a JSON object")

            expected_ids = set(quest_input)
            returned_ids = set(reformatted)
            if returned_ids != expected_ids:
                missing_ids = sorted(expected_ids - returned_ids, key=str)
                extra_ids = sorted(returned_ids - expected_ids, key=str)
                raise ValueError(
                    "T090 response IDs must exactly match the requested batch "
                    f"(missing={missing_ids}, extra={extra_ids})"
                )

            normalized = {}
            for quest_id in quest_input:
                description = reformatted[quest_id]
                if not isinstance(description, str):
                    raise ValueError(
                        f"T090 description for {quest_id!r} must be a string"
                    )
                description = sanitize_text(description).strip()
                if not description:
                    raise ValueError(
                        f"T090 description for {quest_id!r} must not be empty"
                    )
                normalized[quest_id] = description

            info(f"SUCCESS: Reformatted {len(normalized)} quest descriptions", category="quest_formatting")
            return normalized
            
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            error(f"FAILURE: AI response failed validation: {e}", category="quest_formatting")
            debug(f"AI_RESPONSE: {ai_response}", category="quest_formatting")
            return None
            
    except Exception as e:
        error("FAILURE: Error calling AI for quest formatting", exception=e, category="quest_formatting")
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
        path_manager = ModulePathManager(module_name)
        plot_path = path_manager.get_plot_path()
        player_quests_path = os.path.join(
            path_manager.module_dir,
            f"player_quests_{module_name}.json",
        )

        # A managed caller may already own refresh. Nested acquisition is
        # reentrant and deliberately leaves that outer fence held throughout
        # the provider call. A standalone caller owns no lower-ranked lock, so
        # exiting this first scope releases refresh during the network wait.
        for source_attempt in range(SOURCE_RETRY_LIMIT):
            with module_refresh_lock() as snapshot_acquired:
                if not snapshot_acquired:
                    warning(
                        "T090 skipped because module refresh is busy",
                        category="quest_formatting",
                    )
                    return False
                try:
                    source = _capture_plot_source(
                        path_manager.module_dir,
                        plot_path,
                    )
                except (OSError, _QuestSourceDriftError) as exc:
                    error(
                        f"FAILURE: Could not snapshot plot data for {module_name}: {exc}",
                        category="quest_formatting",
                    )
                    return False

            candidate = _build_player_quests(
                module_name,
                source["payload"],
                source["digest"],
            )
            if candidate is None:
                return False

            with module_refresh_lock() as commit_acquired:
                if not commit_acquired:
                    warning(
                        "T090 commit skipped because module refresh is busy",
                        category="quest_formatting",
                    )
                    return False
                with _quest_file_lock(player_quests_path):
                    if not _plot_source_matches(source):
                        warning(
                            "T090 source changed during formatting; discarding stale result",
                            category="quest_formatting",
                        )
                        continue
                    if safe_write_json(player_quests_path, candidate):
                        info(
                            f"SUCCESS: Saved player-friendly quests to {player_quests_path}",
                            category="quest_formatting",
                        )
                        return True
                    error(
                        "FAILURE: Could not save player quests file",
                        category="quest_formatting",
                    )
                    return False

        warning(
            "T090 source remained unstable; last-good player quests were retained",
            category="quest_formatting",
        )
        return False
    except Exception as e:
        error("FAILURE: Unexpected error in format_quests_for_player", exception=e, category="quest_formatting")
        return False


def _format_quests_for_player_unlocked(
    module_name,
    path_manager,
    player_quests_path,
):
    """Compatibility helper for callers already holding the required locks."""
    try:
        plot_path = path_manager.get_plot_path()
        source = _capture_plot_source(path_manager.module_dir, plot_path)
        candidate = _build_player_quests(
            module_name,
            source["payload"],
            source["digest"],
        )
        if candidate is None or not _plot_source_matches(source):
            return False
        return safe_write_json(player_quests_path, candidate)
    except Exception as e:
        error("FAILURE: Unexpected error in format_quests_for_player", exception=e, category="quest_formatting")
        return False


def _build_player_quests(module_name, plot_data, source_digest):
    """Build a complete derived candidate without performing filesystem writes."""
    try:
        info(f"STATE_CHANGE: Starting quest formatting for module {module_name}", category="quest_formatting")

        # Prepare the player quest structure
        player_quests = {
            "module": module_name,
            "lastUpdated": datetime.now().isoformat(),
            "sourceDigest": source_digest,
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
            return player_quests
        
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
        
        return player_quests

    except Exception as e:
        error("FAILURE: Unexpected error building player quests", exception=e, category="quest_formatting")
        return None


def load_current_player_quests(module_name):
    """Return derived quests only when they match the current exact plot bytes.

    UI/catalog readers should use this entry point instead of loading the
    derived JSON directly. Unsupported manual writers cannot be excluded by an
    advisory lock, so the persisted source digest is the reader-side guard.
    """
    try:
        path_manager = ModulePathManager(module_name)
        plot_path = path_manager.get_plot_path()
        destination = os.path.join(
            path_manager.module_dir,
            f"player_quests_{module_name}.json",
        )
        with module_refresh_lock() as acquired:
            if not acquired:
                return None
            source = _capture_plot_source(path_manager.module_dir, plot_path)
            with _quest_file_lock(destination):
                derived = safe_read_json(destination)
                if (
                    not isinstance(derived, dict)
                    or derived.get("sourceDigest") != source["digest"]
                ):
                    return None
                return derived
    except Exception:
        return None


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
