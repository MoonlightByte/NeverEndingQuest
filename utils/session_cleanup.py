# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Session cleanup helpers for stale startup recap markers.

Provides shared cleanup logic used by both runtime startup flow and
developer tooling scripts to avoid logic drift.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from utils.encoding_utils import safe_json_dump, safe_json_load


STALE_RESUME_RECAP_MARKER = "SESSION RESUME RECAP ONLY"


def get_default_history_filepaths() -> List[str]:
    """Return absolute paths for runtime conversation/chat history files."""
    repo_root = Path(__file__).resolve().parent.parent
    history_dir = repo_root / "modules" / "conversation_history"
    return [
        str(history_dir / "conversation_history.json"),
        str(history_dir / "chat_history.json"),
    ]


def is_stale_resume_recap_message(message: Dict[str, Any]) -> bool:
    """Return True when message content contains stale recap marker."""
    if not isinstance(message, dict):
        return False

    content = message.get("content", "")
    if not isinstance(content, str):
        return False

    return STALE_RESUME_RECAP_MARKER in content


def remove_stale_resume_recaps(messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Remove stale recap messages from message list."""
    cleaned_messages = [
        message for message in messages
        if not is_stale_resume_recap_message(message)
    ]
    removed_count = len(messages) - len(cleaned_messages)
    return cleaned_messages, removed_count


def cleanup_history_file(filepath: str, apply_changes: bool = False) -> Dict[str, Any]:
    """Clean stale recap messages from one history JSON file.

    Returns a structured summary with deterministic keys:
    status, path, applied, total_before, total_after, removed_count, error.
    """
    summary: Dict[str, Any] = {
        "status": "ok",
        "path": filepath,
        "applied": apply_changes,
        "total_before": 0,
        "total_after": 0,
        "removed_count": 0,
        "error": None,
    }

    try:
        data = safe_json_load(filepath)
        if data is None:
            summary["status"] = "missing"
            return summary

        if not isinstance(data, list):
            summary["status"] = "error"
            summary["error"] = "history file is not a JSON list"
            return summary

        summary["total_before"] = len(data)
        cleaned_data, removed_count = remove_stale_resume_recaps(data)
        summary["total_after"] = len(cleaned_data)
        summary["removed_count"] = removed_count

        if apply_changes and removed_count > 0:
            safe_json_dump(cleaned_data, filepath)

        return summary
    except Exception as exc:
        summary["status"] = "error"
        summary["error"] = str(exc)
        return summary


def cleanup_history_files(
    filepaths: Optional[Sequence[str]] = None,
    apply_changes: bool = False,
) -> List[Dict[str, Any]]:
    """Clean stale recap markers across one or more history files."""
    target_files = list(filepaths) if filepaths is not None else get_default_history_filepaths()
    return [cleanup_history_file(filepath, apply_changes=apply_changes) for filepath in target_files]
