# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Session diary runtime hooks.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

from typing import Any, Dict

from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, error, info, warning

try:
    from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH
    from core.memory.session_diary import refresh_draft_if_stale

    SESSION_DIARY_RUNTIME_AVAILABLE = True
except ImportError:
    DEFAULT_MEMORY_DB_PATH = "data/memory.db"
    SESSION_DIARY_RUNTIME_AVAILABLE = False


def get_session_diary_world_conditions() -> Dict[str, Any]:
    """Load current world conditions for diary refresh context."""
    try:
        party_tracker = safe_json_load("party_tracker.json")
        if isinstance(party_tracker, dict):
            world_conditions = party_tracker.get("worldConditions", {})
            if isinstance(world_conditions, dict):
                return world_conditions
    except Exception as world_error:
        warning(
            f"SESSION_DIARY: Failed to load party tracker world conditions: {world_error}",
            category="web_interface",
        )
    return {}


def refresh_session_diary_start_hook(db_path: str = DEFAULT_MEMORY_DB_PATH) -> Dict[str, Any]:
    """Best-effort Start Game draft refresh hook."""
    if not SESSION_DIARY_RUNTIME_AVAILABLE:
        return {
            "status": "disabled",
            "message": "Session diary runtime unavailable",
            "db_path": db_path,
        }

    try:
        result = refresh_draft_if_stale(db_path, get_session_diary_world_conditions())
        action = result.get("action")
        if result.get("status") == "success":
            debug(
                f"SESSION_DIARY: Start hook completed action={action}",
                category="web_interface",
            )
            if action == "updated":
                info(
                    "SESSION_DIARY: Journal draft updated on Start Game",
                    category="web_interface",
                )
        else:
            warning(
                f"SESSION_DIARY: Start hook degraded with status={result.get('status')}",
                category="web_interface",
            )
        return result
    except Exception as hook_error:
        error(
            f"SESSION_DIARY: Start hook failed: {hook_error}",
            exception=hook_error,
            category="web_interface",
        )
        return {
            "status": "error",
            "message": str(hook_error),
            "db_path": db_path,
        }
