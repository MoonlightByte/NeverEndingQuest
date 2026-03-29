# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Memory - Session Diary service.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

TABLETOP MODE: Diary checkpoint helpers for Start Game draft and Save confirmed entries.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.memory.memory_db import init_memory_db
from core.memory.memory_ingest import backfill_memory_db_from_histories
from utils.enhanced_logger import debug, error


_MONTH_INDEX_BY_NAME = {
    "hammer": 1,
    "alturiak": 2,
    "ches": 3,
    "tarsakh": 4,
    "mirtul": 5,
    "kythorn": 6,
    "flamerule": 7,
    "eleasis": 8,
    "eleint": 9,
    "marpenoth": 10,
    "uktar": 11,
    "nightal": 12,
}

MAX_SOURCE_EVENTS = 120
MIN_LIST_LIMIT = 1
MAX_LIST_LIMIT = 100
DIARY_BACKFILL_SOURCES = ["journal", "conversation", "combat"]


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert value to int with fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _connect(db_path: str) -> sqlite3.Connection:
    """Create SQLite connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _refresh_diary_source_history(db_path: str) -> Dict[str, Any]:
    """Best-effort sync of runtime history sources into memory DB before checkpoints."""
    try:
        result = backfill_memory_db_from_histories(
            db_path=db_path,
            include_system_messages=False,
            sources=DIARY_BACKFILL_SOURCES,
            batch_size=100,
        )
        if result.get("status") == "error":
            debug(
                f"SESSION_DIARY: Source sync degraded: {result.get('message')}",
                category="memory_db",
            )
        return result
    except Exception as sync_error:
        debug(
            f"SESSION_DIARY: Source sync suppressed: {sync_error}",
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(sync_error),
        }


def _clamp_limit(limit: Any, default: int = 20) -> int:
    """Clamp list limits to a safe bounded range."""
    parsed = _safe_int(limit, default)
    if parsed < MIN_LIST_LIMIT:
        return MIN_LIST_LIMIT
    if parsed > MAX_LIST_LIMIT:
        return MAX_LIST_LIMIT
    return parsed


def _ensure_state_row(conn: sqlite3.Connection) -> None:
    """Ensure singleton state row exists."""
    conn.execute(
        """
        INSERT OR IGNORE INTO session_diary_state (
            state_id,
            last_draft_event_id,
            last_confirmed_event_id,
            updated_at
        ) VALUES (1, 0, 0, ?)
        """,
        (_utc_now_iso(),),
    )


def _normalize_world_fields(world_conditions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize world fields for diary row persistence."""
    payload = world_conditions if isinstance(world_conditions, dict) else {}

    year = _safe_int(payload.get("year"), 0)
    month = str(payload.get("month", "")).strip()
    month_index = _safe_int(payload.get("month_index"), 0)
    if month_index <= 0:
        month_index = _MONTH_INDEX_BY_NAME.get(month.lower(), 0)

    day = _safe_int(payload.get("day"), 0)

    hour = _safe_int(payload.get("hour"), 0)
    minute = _safe_int(payload.get("minute"), 0)
    second = _safe_int(payload.get("second"), 0)
    if hour == 0 and minute == 0 and second == 0:
        parsed_hour, parsed_minute, parsed_second = _parse_time_parts(payload.get("time"))
        hour = parsed_hour
        minute = parsed_minute
        second = parsed_second

    world_time = f"{hour:02d}:{minute:02d}:{second:02d}"
    sort_key = compute_world_sort_key(
        {
            "year": year,
            "month": month,
            "month_index": month_index,
            "day": day,
            "hour": hour,
            "minute": minute,
            "second": second,
            "time": world_time,
        }
    )

    return {
        "world_year": year,
        "world_month": month,
        "world_month_index": month_index,
        "world_day": day,
        "world_time": world_time,
        "world_sort_key": sort_key,
    }


def _serialize_diary_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """Serialize a diary row for API-friendly return payloads."""
    if row is None:
        return None

    return {
        "diary_id": row["diary_id"],
        "status": row["status"],
        "save_id": row["save_id"],
        "checkpoint_type": row["checkpoint_type"] if "checkpoint_type" in row.keys() else None,
        "checkpoint_id": row["checkpoint_id"] if "checkpoint_id" in row.keys() else None,
        "draft_key": row["draft_key"],
        "summary": row["summary"],
        "generation_mode": row["generation_mode"],
        "llm_model": row["llm_model"],
        "source_start_event_id": row["source_start_event_id"],
        "source_end_event_id": row["source_end_event_id"],
        "source_counts_json": row["source_counts_json"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "world": {
            "year": row["world_year"],
            "month": row["world_month"],
            "month_index": row["world_month_index"],
            "day": row["world_day"],
            "time": row["world_time"],
            "sort_key": row["world_sort_key"],
        },
    }


def _get_latest_journal_entry_id(conn: sqlite3.Connection) -> int:
    """Return latest journal entry id or zero when no entries exist."""
    row = conn.execute("SELECT COALESCE(MAX(entry_id), 0) AS max_entry_id FROM journal_entries").fetchone()
    if row is None:
        return 0
    return _safe_int(row["max_entry_id"], 0)


def _fetch_source_entries_bounded(
    conn: sqlite3.Connection,
    start_event_id: int,
    end_event_id: int,
    limit: int = MAX_SOURCE_EVENTS,
) -> List[Dict[str, Any]]:
    """Fetch bounded journal entries for checkpoint summarization."""
    if end_event_id <= start_event_id:
        return []

    cursor = conn.execute(
        """
        SELECT entry_id, entry_ts, title, content, source_type
        FROM journal_entries
        WHERE entry_id > ? AND entry_id <= ?
        ORDER BY entry_id ASC
        LIMIT ?
        """,
        (start_event_id, end_event_id, max(MIN_LIST_LIMIT, min(limit, MAX_SOURCE_EVENTS))),
    )
    return [dict(row) for row in cursor.fetchall()]


def _build_source_counts(entries: List[Dict[str, Any]], start_event_id: int, end_event_id: int) -> str:
    """Build deterministic source count payload for diary rows."""
    payload = {
        "journal_entries": len(entries),
        "source_start_event_id": start_event_id,
        "source_end_event_id": end_event_id,
    }
    return json.dumps(payload, sort_keys=True)


def _normalize_clause(text: Any, fallback: str) -> str:
    """Normalize one fallback clause for stable sentence assembly."""
    value = str(text or "").strip()
    if not value:
        value = fallback
    return value.rstrip(".!? ")


def _parse_time_parts(value: Any) -> List[int]:
    """Parse HH:MM:SS string into three integer parts."""
    if not isinstance(value, str) or ":" not in value:
        return [0, 0, 0]

    parts = value.split(":")
    if len(parts) < 2:
        return [0, 0, 0]

    hour = _safe_int(parts[0], 0)
    minute = _safe_int(parts[1], 0)
    second = _safe_int(parts[2], 0) if len(parts) > 2 else 0
    return [hour, minute, second]


def compute_world_sort_key(world_conditions: Optional[Dict[str, Any]]) -> int:
    """Compute deterministic world-time sort key from world conditions."""
    if not isinstance(world_conditions, dict):
        return 0

    year = _safe_int(world_conditions.get("year"), 0)
    month_index = _safe_int(world_conditions.get("month_index"), 0)
    if month_index <= 0:
        month_name = str(world_conditions.get("month", "")).strip().lower()
        month_index = _MONTH_INDEX_BY_NAME.get(month_name, 0)

    day = _safe_int(world_conditions.get("day"), 0)

    hour = _safe_int(world_conditions.get("hour"), 0)
    minute = _safe_int(world_conditions.get("minute"), 0)
    second = _safe_int(world_conditions.get("second"), 0)
    if hour == 0 and minute == 0 and second == 0:
        parsed_hour, parsed_minute, parsed_second = _parse_time_parts(world_conditions.get("time"))
        hour = parsed_hour
        minute = parsed_minute
        second = parsed_second

    return int(f"{year:04d}{month_index:02d}{day:02d}{hour:02d}{minute:02d}{second:02d}")


def build_fallback_summary(source_events: List[Dict[str, Any]]) -> str:
    """Return deterministic fallback diary text from source events."""
    if not source_events:
        return "The party's recent travels left no confirmed diary events in this checkpoint window."

    first = source_events[0]
    last = source_events[-1]
    first_text = _normalize_clause(
        first.get("summary") or first.get("content"),
        "The journey continued",
    )
    last_text = _normalize_clause(
        last.get("summary") or last.get("content"),
        "the chapter closed",
    )
    return f"The chapter opened with {first_text} and closed with {last_text}."


def _get_confirmed_checkpoint_row(
    conn: sqlite3.Connection,
    checkpoint_type: str,
    checkpoint_id: str,
) -> Optional[sqlite3.Row]:
    """Return one confirmed diary row by checkpoint identity."""
    return conn.execute(
        """
        SELECT *
        FROM session_diary_entries
        WHERE status = 'confirmed'
          AND checkpoint_type = ?
          AND checkpoint_id = ?
        LIMIT 1
        """,
        (checkpoint_type, checkpoint_id),
    ).fetchone()


def refresh_draft_if_stale(db_path: str, world_conditions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Refresh one active draft entry when source history has advanced."""
    if not init_memory_db(db_path):
        return {
            "status": "error",
            "message": "Memory DB initialization failed",
            "db_path": db_path,
        }

    _refresh_diary_source_history(db_path)

    conn: Optional[sqlite3.Connection] = None
    draft_key = "active_draft"
    now_iso = _utc_now_iso()
    world_data = _normalize_world_fields(world_conditions)

    try:
        conn = _connect(db_path)
        _ensure_state_row(conn)

        state_row = conn.execute(
            """
            SELECT last_draft_event_id, last_confirmed_event_id, last_draft_key
            FROM session_diary_state
            WHERE state_id = 1
            """
        ).fetchone()

        last_draft_event_id = _safe_int(state_row["last_draft_event_id"], 0) if state_row else 0
        latest_entry_id = _get_latest_journal_entry_id(conn)

        if latest_entry_id <= last_draft_event_id:
            draft_row = conn.execute(
                """
                SELECT *
                FROM session_diary_entries
                WHERE status = 'draft'
                ORDER BY updated_at DESC, diary_id DESC
                LIMIT 1
                """
            ).fetchone()
            return {
                "status": "success",
                "action": "unchanged",
                "db_path": db_path,
                "latest_entry_id": latest_entry_id,
                "last_draft_event_id": last_draft_event_id,
                "draft": _serialize_diary_row(draft_row),
            }

        source_entries = _fetch_source_entries_bounded(conn, last_draft_event_id, latest_entry_id)
        fallback_summary = build_fallback_summary(source_entries)
        source_start_event_id = source_entries[0]["entry_id"] if source_entries else None

        with conn:
            conn.execute(
                """
                DELETE FROM session_diary_entries
                WHERE status = 'draft'
                  AND (draft_key IS NULL OR draft_key != ?)
                """,
                (draft_key,),
            )

            existing_draft = conn.execute(
                """
                SELECT diary_id
                FROM session_diary_entries
                WHERE status = 'draft' AND draft_key = ?
                LIMIT 1
                """,
                (draft_key,),
            ).fetchone()

            if existing_draft is not None:
                conn.execute(
                    """
                    UPDATE session_diary_entries
                    SET
                        world_year = ?,
                        world_month = ?,
                        world_month_index = ?,
                        world_day = ?,
                        world_time = ?,
                        world_sort_key = ?,
                        summary = ?,
                        source_start_event_id = ?,
                        source_end_event_id = ?,
                        source_counts_json = ?,
                        generation_mode = 'fallback',
                        llm_model = NULL,
                        updated_at = ?
                    WHERE diary_id = ?
                    """,
                    (
                        world_data["world_year"],
                        world_data["world_month"],
                        world_data["world_month_index"],
                        world_data["world_day"],
                        world_data["world_time"],
                        world_data["world_sort_key"],
                        fallback_summary,
                        source_start_event_id,
                        latest_entry_id,
                        _build_source_counts(source_entries, last_draft_event_id, latest_entry_id),
                        now_iso,
                        existing_draft["diary_id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO session_diary_entries (
                        status,
                        save_id,
                        draft_key,
                        world_year,
                        world_month,
                        world_month_index,
                        world_day,
                        world_time,
                        world_sort_key,
                        summary,
                        source_start_event_id,
                        source_end_event_id,
                        source_counts_json,
                        generation_mode,
                        llm_model,
                        created_at,
                        updated_at
                    ) VALUES (
                        'draft',
                        NULL,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        'fallback',
                        NULL,
                        ?,
                        ?
                    )
                    """,
                    (
                        draft_key,
                        world_data["world_year"],
                        world_data["world_month"],
                        world_data["world_month_index"],
                        world_data["world_day"],
                        world_data["world_time"],
                        world_data["world_sort_key"],
                        fallback_summary,
                        source_start_event_id,
                        latest_entry_id,
                        _build_source_counts(source_entries, last_draft_event_id, latest_entry_id),
                        now_iso,
                        now_iso,
                    ),
                )

            conn.execute(
                """
                UPDATE session_diary_state
                SET
                    last_draft_event_id = ?,
                    last_draft_key = ?,
                    updated_at = ?
                WHERE state_id = 1
                """,
                (latest_entry_id, draft_key, now_iso),
            )

        draft_row = conn.execute(
            """
            SELECT *
            FROM session_diary_entries
            WHERE status = 'draft'
              AND draft_key = ?
            ORDER BY diary_id DESC
            LIMIT 1
            """,
            (draft_key,),
        ).fetchone()

        return {
            "status": "success",
            "action": "updated",
            "db_path": db_path,
            "latest_entry_id": latest_entry_id,
            "last_draft_event_id": last_draft_event_id,
            "draft": _serialize_diary_row(draft_row),
            "source_count": len(source_entries),
            "generation_mode": "fallback",
        }
    except Exception as refresh_error:
        error(
            f"SESSION_DIARY: Draft refresh failed: {refresh_error}",
            exception=refresh_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(refresh_error),
            "db_path": db_path,
        }
    finally:
        if conn is not None:
            conn.close()


def confirm_diary_for_save(
    db_path: str,
    save_id: str,
    world_conditions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create idempotent confirmed diary entry for a save checkpoint."""
    normalized_save_id = str(save_id or "").strip()
    if not normalized_save_id:
        return {
            "status": "error",
            "message": "save_id is required",
            "db_path": db_path,
        }

    if not init_memory_db(db_path):
        return {
            "status": "error",
            "message": "Memory DB initialization failed",
            "db_path": db_path,
            "save_id": normalized_save_id,
        }

    _refresh_diary_source_history(db_path)

    conn: Optional[sqlite3.Connection] = None
    now_iso = _utc_now_iso()
    world_data = _normalize_world_fields(world_conditions)

    try:
        conn = _connect(db_path)
        _ensure_state_row(conn)

        checkpoint_type = "save"
        checkpoint_id = normalized_save_id

        existing_checkpoint_row = _get_confirmed_checkpoint_row(conn, checkpoint_type, checkpoint_id)
        if existing_checkpoint_row is not None:
            return {
                "status": "success",
                "action": "reused",
                "db_path": db_path,
                "save_id": normalized_save_id,
                "entry": _serialize_diary_row(existing_checkpoint_row),
            }

        existing_row = conn.execute(
            """
            SELECT *
            FROM session_diary_entries
            WHERE status = 'confirmed' AND save_id = ?
            LIMIT 1
            """,
            (normalized_save_id,),
        ).fetchone()
        if existing_row is not None:
            return {
                "status": "success",
                "action": "reused",
                "db_path": db_path,
                "save_id": normalized_save_id,
                "entry": _serialize_diary_row(existing_row),
            }

        state_row = conn.execute(
            """
            SELECT last_confirmed_event_id, last_draft_event_id
            FROM session_diary_state
            WHERE state_id = 1
            """
        ).fetchone()

        last_confirmed_event_id = _safe_int(state_row["last_confirmed_event_id"], 0) if state_row else 0
        last_draft_event_id = _safe_int(state_row["last_draft_event_id"], 0) if state_row else 0
        latest_entry_id = _get_latest_journal_entry_id(conn)

        source_entries = _fetch_source_entries_bounded(conn, last_confirmed_event_id, latest_entry_id)
        fallback_summary = build_fallback_summary(source_entries)
        source_start_event_id = source_entries[0]["entry_id"] if source_entries else None

        with conn:
            cursor = conn.execute(
                """
                INSERT INTO session_diary_entries (
                        status,
                        save_id,
                        checkpoint_type,
                        checkpoint_id,
                        draft_key,
                        world_year,
                        world_month,
                    world_month_index,
                    world_day,
                    world_time,
                    world_sort_key,
                    summary,
                    source_start_event_id,
                    source_end_event_id,
                    source_counts_json,
                    generation_mode,
                    llm_model,
                    created_at,
                    updated_at
                ) VALUES (
                        'confirmed',
                        ?,
                        ?,
                        ?,
                        NULL,
                        ?,
                        ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    'fallback',
                    NULL,
                    ?,
                    ?
                )
                """,
                (
                    normalized_save_id,
                    checkpoint_type,
                    checkpoint_id,
                    world_data["world_year"],
                    world_data["world_month"],
                    world_data["world_month_index"],
                    world_data["world_day"],
                    world_data["world_time"],
                    world_data["world_sort_key"],
                    fallback_summary,
                    source_start_event_id,
                    latest_entry_id,
                    _build_source_counts(source_entries, last_confirmed_event_id, latest_entry_id),
                    now_iso,
                    now_iso,
                ),
            )

            conn.execute(
                """
                DELETE FROM session_diary_entries
                WHERE status = 'draft'
                """
            )

            conn.execute(
                """
                UPDATE session_diary_state
                SET
                    last_confirmed_event_id = ?,
                    last_confirmed_save_id = ?,
                    last_draft_event_id = ?,
                    last_draft_key = NULL,
                    updated_at = ?
                WHERE state_id = 1
                """,
                (
                    latest_entry_id,
                    normalized_save_id,
                    max(last_draft_event_id, latest_entry_id),
                    now_iso,
                ),
            )

            entry_id = cursor.lastrowid

        entry_row = conn.execute(
            """
            SELECT *
            FROM session_diary_entries
            WHERE diary_id = ?
            LIMIT 1
            """,
            (entry_id,),
        ).fetchone()

        return {
            "status": "success",
            "action": "created",
            "db_path": db_path,
            "save_id": normalized_save_id,
            "entry": _serialize_diary_row(entry_row),
            "source_count": len(source_entries),
            "generation_mode": "fallback",
        }
    except Exception as confirm_error:
        error(
            f"SESSION_DIARY: Confirm checkpoint failed for save_id={normalized_save_id}: {confirm_error}",
            exception=confirm_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(confirm_error),
            "db_path": db_path,
            "save_id": normalized_save_id,
        }
    finally:
        if conn is not None:
            conn.close()


def confirm_diary_for_exit(
    db_path: str,
    world_conditions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create idempotent confirmed diary entry for explicit exit checkpoints."""
    if not init_memory_db(db_path):
        return {
            "status": "error",
            "message": "Memory DB initialization failed",
            "db_path": db_path,
        }

    _refresh_diary_source_history(db_path)

    conn: Optional[sqlite3.Connection] = None
    now_iso = _utc_now_iso()
    world_data = _normalize_world_fields(world_conditions)

    try:
        conn = _connect(db_path)
        _ensure_state_row(conn)

        state_row = conn.execute(
            """
            SELECT last_confirmed_event_id, last_draft_event_id
            FROM session_diary_state
            WHERE state_id = 1
            """
        ).fetchone()

        last_confirmed_event_id = _safe_int(state_row["last_confirmed_event_id"], 0) if state_row else 0
        last_draft_event_id = _safe_int(state_row["last_draft_event_id"], 0) if state_row else 0
        latest_entry_id = _get_latest_journal_entry_id(conn)

        if latest_entry_id <= 0:
            return {
                "status": "success",
                "action": "unchanged",
                "db_path": db_path,
                "latest_entry_id": latest_entry_id,
                "entry": None,
            }

        checkpoint_type = "exit"
        checkpoint_id = f"exit:{latest_entry_id}"

        existing_row = _get_confirmed_checkpoint_row(conn, checkpoint_type, checkpoint_id)
        if existing_row is not None:
            return {
                "status": "success",
                "action": "reused",
                "db_path": db_path,
                "latest_entry_id": latest_entry_id,
                "entry": _serialize_diary_row(existing_row),
            }

        if latest_entry_id <= last_confirmed_event_id:
            draft_row = conn.execute(
                """
                SELECT *
                FROM session_diary_entries
                WHERE status = 'draft'
                ORDER BY updated_at DESC, diary_id DESC
                LIMIT 1
                """
            ).fetchone()
            return {
                "status": "success",
                "action": "unchanged",
                "db_path": db_path,
                "latest_entry_id": latest_entry_id,
                "draft": _serialize_diary_row(draft_row),
                "entry": None,
            }

        source_entries = _fetch_source_entries_bounded(conn, last_confirmed_event_id, latest_entry_id)
        fallback_summary = build_fallback_summary(source_entries)
        source_start_event_id = source_entries[0]["entry_id"] if source_entries else None

        with conn:
            cursor = conn.execute(
                """
                INSERT INTO session_diary_entries (
                    status,
                    save_id,
                    checkpoint_type,
                    checkpoint_id,
                    draft_key,
                    world_year,
                    world_month,
                    world_month_index,
                    world_day,
                    world_time,
                    world_sort_key,
                    summary,
                    source_start_event_id,
                    source_end_event_id,
                    source_counts_json,
                    generation_mode,
                    llm_model,
                    created_at,
                    updated_at
                ) VALUES (
                    'confirmed',
                    NULL,
                    ?,
                    ?,
                    NULL,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    'fallback',
                    NULL,
                    ?,
                    ?
                )
                """,
                (
                    checkpoint_type,
                    checkpoint_id,
                    world_data["world_year"],
                    world_data["world_month"],
                    world_data["world_month_index"],
                    world_data["world_day"],
                    world_data["world_time"],
                    world_data["world_sort_key"],
                    fallback_summary,
                    source_start_event_id,
                    latest_entry_id,
                    _build_source_counts(source_entries, last_confirmed_event_id, latest_entry_id),
                    now_iso,
                    now_iso,
                ),
            )

            conn.execute(
                """
                DELETE FROM session_diary_entries
                WHERE status = 'draft'
                """
            )

            conn.execute(
                """
                UPDATE session_diary_state
                SET
                    last_confirmed_event_id = ?,
                    last_draft_event_id = ?,
                    last_draft_key = NULL,
                    updated_at = ?
                WHERE state_id = 1
                """,
                (
                    latest_entry_id,
                    max(last_draft_event_id, latest_entry_id),
                    now_iso,
                ),
            )

            entry_id = cursor.lastrowid

        entry_row = conn.execute(
            """
            SELECT *
            FROM session_diary_entries
            WHERE diary_id = ?
            LIMIT 1
            """,
            (entry_id,),
        ).fetchone()

        return {
            "status": "success",
            "action": "created",
            "db_path": db_path,
            "latest_entry_id": latest_entry_id,
            "entry": _serialize_diary_row(entry_row),
            "source_count": len(source_entries),
            "generation_mode": "fallback",
        }
    except Exception as confirm_error:
        error(
            f"SESSION_DIARY: Confirm exit checkpoint failed: {confirm_error}",
            exception=confirm_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(confirm_error),
            "db_path": db_path,
        }
    finally:
        if conn is not None:
            conn.close()


def list_diary_entries(
    db_path: str,
    include_draft: bool = True,
    limit: int = 20,
    before_sort_key: Optional[int] = None,
) -> Dict[str, Any]:
    """List diary entries with optional draft and confirmed timeline pagination."""
    if not init_memory_db(db_path):
        return {
            "status": "error",
            "message": "Memory DB initialization failed",
            "db_path": db_path,
            "draft": None,
            "entries": [],
            "next_before_sort_key": None,
        }

    safe_limit = _clamp_limit(limit)
    conn: Optional[sqlite3.Connection] = None

    try:
        conn = _connect(db_path)
        _ensure_state_row(conn)

        draft_row = None
        if include_draft:
            draft_row = conn.execute(
                """
                SELECT *
                FROM session_diary_entries
                WHERE status = 'draft'
                ORDER BY updated_at DESC, diary_id DESC
                LIMIT 1
                """
            ).fetchone()

        if before_sort_key is None:
            confirmed_rows = conn.execute(
                """
                SELECT *
                FROM session_diary_entries
                WHERE status = 'confirmed'
                ORDER BY world_sort_key DESC, diary_id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        else:
            confirmed_rows = conn.execute(
                """
                SELECT *
                FROM session_diary_entries
                WHERE status = 'confirmed'
                  AND world_sort_key < ?
                ORDER BY world_sort_key DESC, diary_id DESC
                LIMIT ?
                """,
                (_safe_int(before_sort_key, 0), safe_limit),
            ).fetchall()

        entries = [_serialize_diary_row(row) for row in confirmed_rows]
        next_before_sort_key = None
        if len(entries) >= safe_limit and entries:
            next_before_sort_key = entries[-1]["world"]["sort_key"]

        return {
            "status": "success",
            "db_path": db_path,
            "draft": _serialize_diary_row(draft_row),
            "entries": entries,
            "next_before_sort_key": next_before_sort_key,
        }
    except Exception as list_error:
        debug(
            f"SESSION_DIARY: List request degraded: {list_error}",
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(list_error),
            "db_path": db_path,
            "draft": None,
            "entries": [],
            "next_before_sort_key": None,
        }
    finally:
        if conn is not None:
            conn.close()


__all__ = [
    "compute_world_sort_key",
    "build_fallback_summary",
    "refresh_draft_if_stale",
    "confirm_diary_for_save",
    "list_diary_entries",
]
