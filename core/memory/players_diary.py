# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Memory - Players Diary markdown artifact service.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

KISS artifact-first confirmed diary flow:
- Source of truth: journal.json
- Confirmed diary artifact: data/players_diary.md
- Bookmark state: data/players_diary_bookmark.json
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from model_config import DM_SUMMARIZATION_MODEL
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import error, warning
from utils.file_operations import safe_write_json

try:
    from model_config import ENABLE_PLAYERS_DIARY_APPEND_LLM
except ImportError:
    ENABLE_PLAYERS_DIARY_APPEND_LLM = True

try:
    from utils.ai_client_factory import create_chat_client, get_model_config, handle_provider_error

    AI_CLIENTS_AVAILABLE = True
except ImportError:
    AI_CLIENTS_AVAILABLE = False


JOURNAL_PATH = "journal.json"
PLAYERS_DIARY_PATH = "data/players_diary.md"
PLAYERS_DIARY_BOOKMARK_PATH = "data/players_diary_bookmark.json"
MAX_JOURNAL_SUMMARY_CHARS = 1200
DIARY_TAIL_CHARS = 5000
MAX_DELTA_ENTRIES_PER_APPEND = 12


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[1]


APPEND_PROMPT_TEMPLATE = """You are writing the Players Diary for an ongoing fantasy campaign.

Write as an anonymous chronicler recounting the party's journey in an engaging, concise, pithy, fun, fantasy-immersive style for players reading the in-game GUI.

Your job is to APPEND only the next diary section(s), based strictly on the new journal entries provided below.

Rules:
- Keep the same tone and style as the existing diary excerpt.
- Be faithful to the facts in the new journal entries.
- Do not invent events, outcomes, or character moments not supported by the journal entries.
- Do not rewrite, summarize, or repeat earlier diary content except where needed for a smooth transition.
- Output markdown only.
- Do not output JSON, notes, commentary, headers like "Here is the update", or system text.
- Do not mention prompts, journal files, bookmarks, or metadata.
- Prefer vivid, readable prose over exhaustive detail.
- Keep sections clean and GUI-friendly.
- If duplicate or near-duplicate journal variants appear, collapse them into one coherent beat.

Existing diary tail for style continuity:
{diary_tail}

New journal entries to incorporate:
{journal_delta}

Return only the new markdown to append.
"""


REBUILD_PROMPT_TEMPLATE = """You are writing the Players Diary for an ongoing fantasy campaign.

Write as an anonymous chronicler recounting the party's journey in an engaging, concise, pithy, fun, fantasy-immersive style for players reading the in-game GUI.

Using the full journal chronology below, generate the complete current Players Diary as a polished markdown chronicle.

Rules:
- Be faithful to the journal events.
- Group events naturally into readable diary sections.
- Keep the tone lively, immersive, and player-facing.
- Do not invent plot developments not supported by the journal.
- Output markdown only.
- Do not output JSON, notes, commentary, or system text.
- Keep the result readable in a game GUI.
- If duplicate or near-duplicate journal variants appear, collapse them into one coherent beat.

Full journal chronology:
{journal_full}

Return only the complete markdown diary.
"""


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_runtime_path(relative_path: str) -> str:
    """Resolve runtime paths against cwd first, then project root."""
    cwd_path = Path(relative_path)
    if cwd_path.exists():
        return str(cwd_path)
    return str((PROJECT_ROOT / relative_path).resolve())


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert value to int with fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ensure_parent_dir(path_value: str) -> None:
    """Ensure parent directory exists."""
    parent_dir = os.path.dirname(path_value)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def _safe_write_markdown(path_value: str, content: str) -> bool:
    """Atomically write markdown content to disk."""
    try:
        _ensure_parent_dir(path_value)
        parent_dir = os.path.dirname(path_value) or "."
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=parent_dir, delete=False) as handle:
            handle.write(content)
            temp_path = handle.name
        os.replace(temp_path, path_value)
        return True
    except Exception as write_error:
        error(
            f"PLAYERS_DIARY: Failed to write markdown artifact: {write_error}",
            exception=write_error,
            category="memory_db",
        )
        return False


def _read_markdown(path_value: str) -> str:
    """Read markdown file with empty fallback."""
    if not os.path.exists(path_value):
        return ""
    try:
        with open(path_value, "r", encoding="utf-8") as handle:
            return str(handle.read() or "")
    except Exception as read_error:
        warning(
            f"PLAYERS_DIARY: Failed to read markdown artifact: {read_error}",
            category="memory_db",
        )
        return ""


def _load_bookmark(path_value: str) -> Dict[str, Any]:
    """Load bookmark payload with safe defaults."""
    payload = safe_json_load(path_value) or {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "last_processed_index": _safe_int(payload.get("last_processed_index"), -1),
        "updated_at": str(payload.get("updated_at", "") or "").strip(),
    }


def _write_bookmark(path_value: str, last_processed_index: int) -> bool:
    """Persist bookmark state to runtime bookmark file."""
    bookmark_payload = {
        "last_processed_index": max(-1, int(last_processed_index)),
        "updated_at": _utc_now_iso(),
    }
    return safe_write_json(path_value, bookmark_payload)


def _load_journal_entries(journal_path: str) -> List[Dict[str, Any]]:
    """Load journal entries from journal.json."""
    payload = safe_json_load(journal_path) or {}
    if isinstance(payload, dict):
        entries = payload.get("entries")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    return []


def _normalize_text(value: Any) -> str:
    """Normalize text for prompt packets."""
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _sanitize_journal_summary(value: Any) -> str:
    """Sanitize journal summary before prompt embedding."""
    text = _normalize_text(value)
    text = re.sub(r"^\s*journal\s+entry\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*date\s*[:\-].*?$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_JOURNAL_SUMMARY_CHARS:
        text = text[:MAX_JOURNAL_SUMMARY_CHARS].rstrip(" ,;:-") + "..."
    return text


def _format_journal_entries_for_prompt(entries: List[Dict[str, Any]], start_index: int = 0) -> str:
    """Format journal entries into compact prompt packet."""
    lines: List[str] = []
    for offset, entry in enumerate(entries):
        index = start_index + offset
        date_text = _normalize_text(entry.get("date", "")) or "Unknown Date"
        time_text = _normalize_text(entry.get("time", "")) or "00:00:00"
        location_text = _normalize_text(entry.get("location", "")) or "Unknown Location"
        summary_text = _sanitize_journal_summary(entry.get("summary", ""))
        if not summary_text:
            continue
        lines.append(f"[{index}] {date_text} at {time_text} -- {location_text}")
        lines.append(summary_text)
        lines.append("")
    return "\n".join(lines).strip()


def _extract_diary_tail(markdown_text: str) -> str:
    """Extract bounded trailing diary text for style continuity."""
    content = str(markdown_text or "")
    if len(content) <= DIARY_TAIL_CHARS:
        return content
    return content[-DIARY_TAIL_CHARS:]


def _sanitize_generated_markdown(markdown_text: str) -> str:
    """Sanitize generated markdown append/rebuild content."""
    text = str(markdown_text or "").strip()
    if not text:
        return ""

    text = re.sub(r"^```(?:markdown|md)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.IGNORECASE)
    text = text.strip()

    if re.match(r"^\s*\{[\s\S]*\}\s*$", text):
        return ""

    disallowed = ["{\"", "[SYSTEM]", "debug", "prompt", "bookmark", "journal file"]
    lowered = text.lower()
    for token in disallowed:
        if token.lower() in lowered:
            return ""

    return text


def _build_append_prompt(diary_tail: str, journal_delta_packet: str) -> str:
    """Render append prompt using template contract."""
    tail_payload = diary_tail.strip() or "(Diary currently empty; start the chronicle.)"
    return APPEND_PROMPT_TEMPLATE.format(
        diary_tail=tail_payload,
        journal_delta=journal_delta_packet.strip() or "(No new entries)",
    )


def _build_rebuild_prompt(journal_full_packet: str) -> str:
    """Render rebuild prompt using template contract."""
    return REBUILD_PROMPT_TEMPLATE.format(
        journal_full=journal_full_packet.strip() or "(No journal entries)",
    )


def _generate_markdown_from_prompt(prompt_text: str, context_tag: str) -> Dict[str, Any]:
    """Generate markdown through provider-agnostic chat client."""
    if not ENABLE_PLAYERS_DIARY_APPEND_LLM:
        return {
            "status": "error",
            "message": "Players diary LLM generation disabled",
            "markdown": "",
            "model": None,
        }

    if not AI_CLIENTS_AVAILABLE:
        warning(
            "PLAYERS_DIARY: LLM generation unavailable in current interpreter (missing AI client deps)",
            category="memory_db",
        )
        return {
            "status": "error",
            "message": "AI client dependencies unavailable",
            "markdown": "",
            "model": None,
        }

    config = get_model_config("summaries", DM_SUMMARIZATION_MODEL)
    client = create_chat_client()

    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "Write only markdown chronicle content suitable for direct GUI display.",
                },
                {
                    "role": "user",
                    "content": prompt_text,
                },
            ],
            temperature=config.get("temperature", 0.8),
            **config.get("extra_body", {}),
        )
        raw_text = ""
        if response.choices and response.choices[0].message:
            raw_text = str(response.choices[0].message.content or "")
        markdown_text = _sanitize_generated_markdown(raw_text)
        if not markdown_text:
            return {
                "status": "error",
                "message": f"{context_tag} returned unusable markdown",
                "markdown": "",
                "model": config["model"],
            }
        return {
            "status": "success",
            "message": "ok",
            "markdown": markdown_text,
            "model": config["model"],
        }
    except Exception as generation_error:
        error_info = handle_provider_error(generation_error, context=context_tag)
        if error_info.get("should_fallback"):
            try:
                fallback_client = create_chat_client(use_fallback=True)
                fallback_response = fallback_client.chat.completions.create(
                    model=DM_SUMMARIZATION_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "Write only markdown chronicle content suitable for direct GUI display.",
                        },
                        {
                            "role": "user",
                            "content": prompt_text,
                        },
                    ],
                    temperature=config.get("temperature", 0.8),
                )
                raw_text = ""
                if fallback_response.choices and fallback_response.choices[0].message:
                    raw_text = str(fallback_response.choices[0].message.content or "")
                markdown_text = _sanitize_generated_markdown(raw_text)
                if markdown_text:
                    return {
                        "status": "success",
                        "message": "ok",
                        "markdown": markdown_text,
                        "model": DM_SUMMARIZATION_MODEL,
                    }
            except Exception as fallback_error:
                warning(
                    f"PLAYERS_DIARY: Fallback generation failed: {fallback_error}",
                    category="memory_db",
                )

        warning(
            f"PLAYERS_DIARY: {context_tag} generation degraded: {generation_error}",
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(generation_error),
            "markdown": "",
            "model": None,
        }


def _append_markdown(existing_markdown: str, new_markdown: str) -> str:
    """Append new markdown chunk to existing diary artifact."""
    current = str(existing_markdown or "").rstrip()
    addition = str(new_markdown or "").strip()
    if not current:
        return addition + "\n"
    if not addition:
        return current + "\n"
    return current + "\n\n" + addition + "\n"


def _entry_fingerprint(entry: Dict[str, Any]) -> str:
    """Return stable fingerprint for one journal entry."""
    payload = {
        "date": _normalize_text(entry.get("date", "")),
        "time": _normalize_text(entry.get("time", "")),
        "location": _normalize_text(entry.get("location", "")),
        "summary": _sanitize_journal_summary(entry.get("summary", "")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    return digest


def _delta_entries(entries: List[Dict[str, Any]], start_index: int) -> List[Dict[str, Any]]:
    """Return unprocessed journal entries using bookmark index."""
    if not entries:
        return []
    safe_start = max(0, start_index)
    if safe_start >= len(entries):
        return []
    return entries[safe_start:]


def rebuild_players_diary_from_journal(
    journal_path: str = JOURNAL_PATH,
    diary_path: str = PLAYERS_DIARY_PATH,
    bookmark_path: str = PLAYERS_DIARY_BOOKMARK_PATH,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Rebuild the full players diary markdown artifact from all journal entries."""
    resolved_journal_path = _resolve_runtime_path(journal_path)
    resolved_diary_path = _resolve_runtime_path(diary_path)
    resolved_bookmark_path = _resolve_runtime_path(bookmark_path)

    entries = _load_journal_entries(resolved_journal_path)
    if not entries:
        return {
            "status": "error",
            "action": "rebuild",
            "message": "No journal entries available",
            "journal_entries": 0,
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    journal_packet = _format_journal_entries_for_prompt(entries, start_index=0)
    generation = _generate_markdown_from_prompt(
        _build_rebuild_prompt(journal_packet),
        context_tag="players_diary_rebuild",
    )
    if generation.get("status") != "success":
        return {
            "status": "error",
            "action": "rebuild",
            "message": str(generation.get("message", "Rebuild generation failed")),
            "journal_entries": len(entries),
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    rebuilt_markdown = str(generation.get("markdown", "")).strip()
    if not rebuilt_markdown:
        return {
            "status": "error",
            "action": "rebuild",
            "message": "Rebuild markdown was empty",
            "journal_entries": len(entries),
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    if dry_run:
        return {
            "status": "success",
            "action": "rebuild_preview",
            "message": "Rebuild preview generated",
            "journal_entries": len(entries),
            "diary_length": len(rebuilt_markdown),
            "model": generation.get("model"),
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    if not _safe_write_markdown(resolved_diary_path, rebuilt_markdown + "\n"):
        return {
            "status": "error",
            "action": "rebuild",
            "message": "Failed to write players diary artifact",
            "journal_entries": len(entries),
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    last_index = len(entries) - 1
    if not _write_bookmark(resolved_bookmark_path, last_index):
        return {
            "status": "error",
            "action": "rebuild",
            "message": "Diary written but bookmark update failed",
            "journal_entries": len(entries),
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    return {
        "status": "success",
        "action": "rebuild",
        "message": "Players diary rebuilt",
        "journal_entries": len(entries),
        "diary_length": len(rebuilt_markdown),
        "last_processed_index": last_index,
        "model": generation.get("model"),
        "diary_path": resolved_diary_path,
        "bookmark_path": resolved_bookmark_path,
    }


def append_players_diary_from_journal(
    journal_path: str = JOURNAL_PATH,
    diary_path: str = PLAYERS_DIARY_PATH,
    bookmark_path: str = PLAYERS_DIARY_BOOKMARK_PATH,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Append only new diary markdown derived from unprocessed journal entries."""
    resolved_journal_path = _resolve_runtime_path(journal_path)
    resolved_diary_path = _resolve_runtime_path(diary_path)
    resolved_bookmark_path = _resolve_runtime_path(bookmark_path)

    entries = _load_journal_entries(resolved_journal_path)
    if not entries:
        return {
            "status": "error",
            "action": "append",
            "message": "No journal entries available",
            "journal_entries": 0,
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    existing_diary = _read_markdown(resolved_diary_path)
    bookmark = _load_bookmark(resolved_bookmark_path)
    last_processed_index = _safe_int(bookmark.get("last_processed_index"), -1)
    if last_processed_index >= len(entries):
        last_processed_index = len(entries) - 1

    if not existing_diary.strip() and last_processed_index < 0:
        # First-run path: build from scratch once.
        return rebuild_players_diary_from_journal(
            journal_path=resolved_journal_path,
            diary_path=resolved_diary_path,
            bookmark_path=resolved_bookmark_path,
            dry_run=dry_run,
        )

    start_index = max(0, last_processed_index + 1)
    delta = _delta_entries(entries, start_index)
    if not delta:
        return {
            "status": "success",
            "action": "noop",
            "message": "No new journal entries",
            "journal_entries": len(entries),
            "appended_entries": 0,
            "last_processed_index": last_processed_index,
            "diary_length": len(existing_diary),
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    working_diary = existing_diary
    processed_index = last_processed_index
    total_appended_entries = 0
    model_used = None

    for chunk_start in range(0, len(delta), MAX_DELTA_ENTRIES_PER_APPEND):
        chunk = delta[chunk_start : chunk_start + MAX_DELTA_ENTRIES_PER_APPEND]
        chunk_index_start = start_index + chunk_start
        journal_delta_packet = _format_journal_entries_for_prompt(chunk, start_index=chunk_index_start)
        diary_tail = _extract_diary_tail(working_diary)

        generation = _generate_markdown_from_prompt(
            _build_append_prompt(diary_tail, journal_delta_packet),
            context_tag="players_diary_append",
        )
        if generation.get("status") != "success":
            return {
                "status": "error",
                "action": "append",
                "message": str(generation.get("message", "Append generation failed")),
                "journal_entries": len(entries),
                "appended_entries": total_appended_entries,
                "last_processed_index": processed_index,
                "diary_length": len(working_diary),
                "diary_path": resolved_diary_path,
                "bookmark_path": resolved_bookmark_path,
            }

        appended_text = str(generation.get("markdown", "")).strip()
        if not appended_text:
            return {
                "status": "error",
                "action": "append",
                "message": "Append generation returned empty markdown",
                "journal_entries": len(entries),
                "appended_entries": total_appended_entries,
                "last_processed_index": processed_index,
                "diary_length": len(working_diary),
                "diary_path": resolved_diary_path,
                "bookmark_path": resolved_bookmark_path,
            }

        if _normalize_text(appended_text[:220]) and _normalize_text(appended_text[:220]) in _normalize_text(diary_tail):
            return {
                "status": "error",
                "action": "append",
                "message": "Append output appears to duplicate existing diary tail",
                "journal_entries": len(entries),
                "appended_entries": total_appended_entries,
                "last_processed_index": processed_index,
                "diary_length": len(working_diary),
                "diary_path": resolved_diary_path,
                "bookmark_path": resolved_bookmark_path,
            }

        working_diary = _append_markdown(working_diary, appended_text)
        processed_index = chunk_index_start + len(chunk) - 1
        total_appended_entries += len(chunk)
        model_used = generation.get("model")

    if dry_run:
        return {
            "status": "success",
            "action": "append_preview",
            "message": "Append preview generated",
            "journal_entries": len(entries),
            "appended_entries": total_appended_entries,
            "last_processed_index": processed_index,
            "diary_length": len(working_diary),
            "model": model_used,
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    if not _safe_write_markdown(resolved_diary_path, working_diary.rstrip() + "\n"):
        return {
            "status": "error",
            "action": "append",
            "message": "Failed to write players diary artifact",
            "journal_entries": len(entries),
            "appended_entries": 0,
            "last_processed_index": last_processed_index,
            "diary_length": len(existing_diary),
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    if not _write_bookmark(resolved_bookmark_path, processed_index):
        return {
            "status": "error",
            "action": "append",
            "message": "Diary written but bookmark update failed",
            "journal_entries": len(entries),
            "appended_entries": total_appended_entries,
            "last_processed_index": last_processed_index,
            "diary_length": len(working_diary),
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    return {
        "status": "success",
        "action": "append",
        "message": "Players diary appended",
        "journal_entries": len(entries),
        "appended_entries": total_appended_entries,
        "last_processed_index": processed_index,
        "diary_length": len(working_diary),
        "model": model_used,
        "diary_path": resolved_diary_path,
        "bookmark_path": resolved_bookmark_path,
    }


def get_or_update_players_diary(
    journal_path: str = JOURNAL_PATH,
    diary_path: str = PLAYERS_DIARY_PATH,
    bookmark_path: str = PLAYERS_DIARY_BOOKMARK_PATH,
    force_rebuild: bool = False,
) -> Dict[str, Any]:
    """Return confirmed players diary markdown, updating append state as needed."""
    resolved_diary_path = _resolve_runtime_path(diary_path)
    resolved_bookmark_path = _resolve_runtime_path(bookmark_path)
    resolved_journal_path = _resolve_runtime_path(journal_path)

    update_result = rebuild_players_diary_from_journal(
        journal_path=resolved_journal_path,
        diary_path=resolved_diary_path,
        bookmark_path=resolved_bookmark_path,
        dry_run=False,
    ) if force_rebuild else append_players_diary_from_journal(
        journal_path=resolved_journal_path,
        diary_path=resolved_diary_path,
        bookmark_path=resolved_bookmark_path,
        dry_run=False,
    )

    markdown_text = _read_markdown(resolved_diary_path)
    bookmark = _load_bookmark(resolved_bookmark_path)

    if update_result.get("status") != "success":
        if markdown_text:
            return {
                "status": "success",
                "mode": "degraded",
                "message": str(update_result.get("message", "Players diary update degraded")),
                "markdown": markdown_text,
                "bookmark": bookmark,
                "diary_path": resolved_diary_path,
                "bookmark_path": resolved_bookmark_path,
            }
        return {
            "status": "error",
            "mode": "error",
            "message": str(update_result.get("message", "Players diary unavailable")),
            "markdown": "",
            "bookmark": bookmark,
            "diary_path": resolved_diary_path,
            "bookmark_path": resolved_bookmark_path,
        }

    return {
        "status": "success",
        "mode": str(update_result.get("action", "append")),
        "message": str(update_result.get("message", "ok")),
        "markdown": markdown_text,
        "bookmark": bookmark,
        "update": update_result,
        "diary_path": resolved_diary_path,
        "bookmark_path": resolved_bookmark_path,
    }


__all__ = [
    "append_players_diary_from_journal",
    "rebuild_players_diary_from_journal",
    "get_or_update_players_diary",
]
