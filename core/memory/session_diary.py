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
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.memory.memory_db import init_memory_db
from core.memory.memory_ingest import backfill_memory_db_from_histories
from model_config import DM_SUMMARIZATION_MODEL
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, error, warning

try:
    from model_config import ENABLE_SESSION_DIARY_LLM
except ImportError:
    ENABLE_SESSION_DIARY_LLM = False

try:
    from utils.ai_client_factory import create_chat_client, get_model_config, handle_provider_error

    AI_CLIENTS_AVAILABLE = True
except ImportError:
    AI_CLIENTS_AVAILABLE = False


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
MAX_BEAT_SENTENCES = 2
MAX_BEAT_CHARS = 320
MAX_SUMMARY_CHARS = 280
MAX_PROMPT_BEATS = 6
MAX_PROMPT_CHARS_PER_BEAT = 220
DIARY_TEMPLATE_PATH = "prompts/tabletop/session_diary_entry.txt"
REBUILD_SUMMARY_MAX_CHARS = 680
REBUILD_UNKNOWN_MONTH_BASE = 50
JOURNAL_SOURCE_PREFIX = "journal.json:"
REBUILD_SOURCE_ORDER_SORT_BASE = 10000000000000
REBUILD_STRICT_NEAR_DUP_SECONDS = 900
REBUILD_NEAR_DUP_SECONDS = 2700
REBUILD_NEAR_DUP_SIMILARITY = 0.14


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[1]

_DIARY_STRUCTURED_PATTERNS = [
    re.compile(r'^\s*\{\s*"(?:plan|narration|actions|combat_round)"', re.IGNORECASE),
    re.compile(r'^\s*\[\s*System:', re.IGNORECASE),
    re.compile(r'^\s*===\s*[A-Z_ ]+\s*===\s*$', re.IGNORECASE),
    re.compile(r'"action"\s*:\s*"(?:updateEncounter|updateCharacterInfo|createEncounter|requestRoll)"', re.IGNORECASE),
    re.compile(r'\b(?:updateEncounter|updateCharacterInfo|createEncounter|requestRoll)\b', re.IGNORECASE),
]

_JOURNAL_HEADER_PATTERNS = [
    re.compile(r'^\s*journal\s+entry\s*[:\-].*$', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*[-*]*\s*date\s*[:\-].*$', re.IGNORECASE | re.MULTILINE),
]

_LOCATION_ID_PATTERN = re.compile(r"^(?P<name>.*?)\s*\((?P<location_id>[A-Za-z0-9_\-]+)\)\s*$")
_SUMMARY_TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}")

_SUMMARY_STOPWORDS = {
    "the",
    "and",
    "with",
    "from",
    "that",
    "this",
    "they",
    "their",
    "there",
    "into",
    "upon",
    "after",
    "before",
    "through",
    "while",
    "where",
    "when",
    "were",
    "been",
    "have",
    "had",
    "party",
    "chronos",
    "blairen",
    "vitreol",
    "kira",
}


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert value to int with fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_runtime_path(relative_path: str) -> str:
    """Resolve runtime paths against cwd first, then project root."""
    cwd_path = Path(relative_path)
    if cwd_path.exists():
        return str(cwd_path)

    return str((PROJECT_ROOT / relative_path).resolve())


def _load_diary_template() -> str:
    """Load diary prompt template from disk."""
    template_path = _resolve_runtime_path(DIARY_TEMPLATE_PATH)
    if not os.path.exists(template_path):
        return ""
    with open(template_path, "r", encoding="utf-8") as handle:
        return handle.read()


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


def _normalize_checkpoint_text(value: Any, fallback: str) -> str:
    """Normalize one checkpoint metadata field with fallback text."""
    text = str(value or "").strip()
    if not text:
        return fallback
    return text


def _prefer_checkpoint_fallback(value: Any, fallback: str, unknown_label: str) -> str:
    """Prefer fallback when existing checkpoint value is blank or placeholder unknown."""
    text = str(value or "").strip()
    if not text:
        return fallback
    if text.lower() == str(unknown_label or "").strip().lower():
        return fallback
    return text


def _resolve_checkpoint_context(world_conditions: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Resolve module/location checkpoint metadata for one diary row."""
    payload = world_conditions if isinstance(world_conditions, dict) else {}
    tracker = safe_json_load("party_tracker.json") or {}
    tracker_world = tracker.get("worldConditions", {}) if isinstance(tracker, dict) else {}
    current_location = safe_json_load("current_location.json") or {}

    module_name = payload.get("module")
    if not module_name and isinstance(tracker, dict):
        module_name = tracker.get("module")

    location_name = payload.get("currentLocation")
    if not location_name and isinstance(tracker_world, dict):
        location_name = tracker_world.get("currentLocation")
    if not location_name and isinstance(current_location, dict):
        location_name = current_location.get("name")

    location_id = payload.get("currentLocationId")
    if not location_id and isinstance(tracker_world, dict):
        location_id = tracker_world.get("currentLocationId")
    if not location_id and isinstance(current_location, dict):
        location_id = current_location.get("locationId")

    area_name = payload.get("currentArea")
    if not area_name and isinstance(tracker_world, dict):
        area_name = tracker_world.get("currentArea")
    if not area_name and isinstance(current_location, dict):
        area_name = current_location.get("area") or current_location.get("areaName")

    area_id = payload.get("currentAreaId")
    if not area_id and isinstance(tracker_world, dict):
        area_id = tracker_world.get("currentAreaId")
    if not area_id and isinstance(current_location, dict):
        area_id = current_location.get("areaId")

    return {
        "checkpoint_module": _normalize_checkpoint_text(module_name, "Unknown Module"),
        "checkpoint_location": _normalize_checkpoint_text(location_name, "Unknown Location"),
        "checkpoint_location_id": str(location_id or "").strip(),
        "checkpoint_area": _normalize_checkpoint_text(area_name, "Unknown Area"),
        "checkpoint_area_id": str(area_id or "").strip(),
    }


def _serialize_diary_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """Serialize a diary row for API-friendly return payloads."""
    if row is None:
        return None

    checkpoint_module = row["checkpoint_module"] if "checkpoint_module" in row.keys() else None
    checkpoint_location = row["checkpoint_location"] if "checkpoint_location" in row.keys() else None
    checkpoint_location_id = row["checkpoint_location_id"] if "checkpoint_location_id" in row.keys() else None
    checkpoint_area = row["checkpoint_area"] if "checkpoint_area" in row.keys() else None
    checkpoint_area_id = row["checkpoint_area_id"] if "checkpoint_area_id" in row.keys() else None

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
        "checkpoint": {
            "module": checkpoint_module,
            "location": checkpoint_location,
            "location_id": checkpoint_location_id,
            "area": checkpoint_area,
            "area_id": checkpoint_area_id,
        },
    }


def _load_journal_entries_from_file(journal_path: str = "journal.json") -> List[Dict[str, Any]]:
    """Load journal entries list from journal.json with fail-open fallback."""
    payload = safe_json_load(_resolve_runtime_path(journal_path)) or {}
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        entries = payload.get("entries")
        if not isinstance(entries, list):
            entries = payload.get("journal_entries")
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)]
    return []


def _load_journal_payload(journal_path: str = "journal.json") -> Dict[str, Any]:
    """Load full journal payload for module-level metadata lookups."""
    payload = safe_json_load(_resolve_runtime_path(journal_path)) or {}
    if isinstance(payload, dict):
        return payload
    return {}


def _parse_source_ref_index(source_ref: Any) -> Optional[int]:
    """Parse integer index from source_ref values like journal.json:17."""
    text = str(source_ref or "").strip()
    if not text.startswith(JOURNAL_SOURCE_PREFIX):
        return None
    raw_index = text[len(JOURNAL_SOURCE_PREFIX) :].strip()
    if not raw_index:
        return None
    parsed = _safe_int(raw_index, -1)
    if parsed < 0:
        return None
    return parsed


def _split_location_label(raw_location: Any) -> Dict[str, str]:
    """Split location labels like 'Bandit Stronghold (TW05)' into name + id."""
    text = str(raw_location or "").strip()
    if not text:
        return {
            "location": "Unknown Location",
            "location_id": "",
        }

    matched = _LOCATION_ID_PATTERN.match(text)
    if matched:
        location_name = str(matched.group("name") or "").strip() or "Unknown Location"
        location_id = str(matched.group("location_id") or "").strip()
        return {
            "location": location_name,
            "location_id": location_id,
        }

    return {
        "location": text,
        "location_id": "",
    }


def _parse_journal_date_fields(
    date_text: Any,
    source_index: int,
    unknown_month_index_map: Dict[str, int],
) -> Dict[str, Any]:
    """Parse year/month/day from journal date labels with source-order fallback."""
    text = str(date_text or "").strip()
    tokens = [token for token in re.split(r"\s+", text) if token]
    year = 0
    day = 0
    month = "Unknown Month"

    numeric_tokens = [token for token in tokens if token.isdigit()]
    if numeric_tokens:
        year = _safe_int(numeric_tokens[0], 0)
        day = _safe_int(numeric_tokens[-1], 0)

    if len(tokens) >= 2:
        if tokens[0].isdigit() and len(tokens) > 2:
            month = " ".join(tokens[1:-1]).strip() or "Unknown Month"
        elif tokens[-1].isdigit() and len(tokens) > 1:
            month = " ".join(tokens[:-1]).strip() or "Unknown Month"
        else:
            month = " ".join(token for token in tokens if not token.isdigit()).strip() or "Unknown Month"

    month_key = month.lower().strip()
    month_index = _MONTH_INDEX_BY_NAME.get(month_key, 0)
    if month_index <= 0:
        existing_unknown = unknown_month_index_map.get(month_key)
        if existing_unknown is None:
            existing_unknown = REBUILD_UNKNOWN_MONTH_BASE + len(unknown_month_index_map) + 1
            unknown_month_index_map[month_key] = existing_unknown
        month_index = existing_unknown

    return {
        "world_year": year,
        "world_month": month,
        "world_month_index": month_index,
        "world_day": day,
        "source_index": source_index,
    }


def _compute_rebuild_sort_key(world_fields: Dict[str, Any], source_index: int) -> int:
    """Compute deterministic sort key for rebuilt diary rows."""
    parsed = compute_world_sort_key(
        {
            "year": world_fields.get("world_year", 0),
            "month": world_fields.get("world_month", ""),
            "month_index": world_fields.get("world_month_index", 0),
            "day": world_fields.get("world_day", 0),
            "time": world_fields.get("world_time", "00:00:00"),
        }
    )

    if parsed > 0:
        return parsed * 1000 + max(0, min(source_index, 999))

    return 10000000000000 + max(0, source_index)


def _sanitize_rebuild_summary(summary_text: Any) -> str:
    """Sanitize rebuild summary text and keep richer prose than checkpoint fallback."""
    cleaned = _ascii_normalize(str(summary_text or ""))

    lines = [line.strip() for line in cleaned.splitlines() if line and line.strip()]
    if len(lines) >= 2:
        first_line = lines[0]
        second_line = lines[1]
        heading_like = (
            len(first_line) <= 96
            and not first_line.endswith((".", "!", "?"))
            and not re.search(r"\b(?:Our|The|At|As|After|Upon|In|On|With|From|I|We|They)\b", first_line)
            and re.search(r"^(?:Our|The|At|As|After|Upon|In|On|With|From|I|We|They)\b", second_line)
        )
        if heading_like:
            lines = lines[1:]

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"^\s*journal\s+entry\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"^\s*[-*]*\s*date\s*[:\-]\s*[^.?!]{1,120}\s+(?=(?:The|Our|At|As|After|Upon|In|On|With|From|I|We|They)\b)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bdate\s*[:\-]\s*[^.?!]{1,80}[.?!]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = _strip_journal_headers(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    heading_markers = [
        " This morning",
        " Today's",
        " Today,",
        " At ",
        " As ",
        " After ",
        " Upon ",
        " In ",
        " On ",
        " With ",
        " From ",
        " Our ",
        " The ",
        " We ",
        " They ",
    ]
    marker_positions = [cleaned.find(marker) for marker in heading_markers if cleaned.find(marker) > 16]
    if marker_positions:
        split_index = min(marker_positions)
        prefix = cleaned[:split_index].strip(" ,:-")
        prefix_words = [word for word in re.split(r"\s+", prefix) if word]
        capitalized_words = [word for word in prefix_words if word[:1].isupper()]
        known_heading_start = bool(prefix_words) and prefix_words[0].lower() in {
            "arrival",
            "journey",
            "chronicle",
            "report",
            "entry",
        }
        heading_like_prefix = (
            len(prefix) <= 140
            and "." not in prefix
            and "!" not in prefix
            and "?" not in prefix
            and len(prefix_words) >= 3
            and (
                len(capitalized_words) >= max(2, len(prefix_words) - 2)
                or (known_heading_start and len(prefix_words) >= 5)
            )
        )
        if heading_like_prefix:
            cleaned = cleaned[split_index:].lstrip(" ,:-")

    cleaned = re.sub(
        r"^[A-Z][A-Za-z' -]+(?:,\s*[A-Z][A-Za-z' -]+){1,3}\s+(?=(?:Our|The|At|As|After|Upon|In|On|With|From|I|We|They)\b)",
        "",
        cleaned,
    ).strip()

    cleaned = re.sub(r"^[-*]\s*", "", cleaned).strip()

    if not cleaned:
        return ""
    if _looks_like_structured_artifact(cleaned):
        return ""
    if len(cleaned) > REBUILD_SUMMARY_MAX_CHARS:
        cleaned = cleaned[:REBUILD_SUMMARY_MAX_CHARS].rstrip(" ,;:-") + "..."
    return cleaned


def _build_rebuild_candidates(journal_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build normalized rebuild candidates from ordered journal.json entries."""
    if not journal_entries:
        return []

    unknown_month_index_map: Dict[str, int] = {}
    candidates: List[Dict[str, Any]] = []

    for source_index, entry in enumerate(journal_entries, start=1):
        if not isinstance(entry, dict):
            continue

        date_text = str(entry.get("date", "") or "").strip()
        time_text = str(entry.get("time", "") or "").strip() or "00:00:00"
        raw_location = str(entry.get("location", "") or "").strip() or "Unknown Location"
        raw_summary = str(entry.get("summary", "") or "").strip()
        if not raw_summary:
            raw_summary = str(entry.get("content", "") or "").strip()

        sanitized_summary = _sanitize_rebuild_summary(raw_summary)
        if not sanitized_summary:
            continue

        location_parts = _split_location_label(raw_location)
        world_fields = _parse_journal_date_fields(date_text, source_index, unknown_month_index_map)
        world_fields["world_time"] = time_text
        world_fields["world_sort_key"] = REBUILD_SOURCE_ORDER_SORT_BASE + source_index

        group_key = "|".join(
            [
                str(world_fields["world_year"]),
                str(world_fields["world_month"]).lower(),
                str(world_fields["world_day"]),
                str(world_fields["world_time"]),
                str(location_parts["location"]).lower(),
            ]
        )

        candidates.append(
            {
                "entry_id": source_index,
                "source_index": source_index,
                "summary": sanitized_summary,
                "raw_location": raw_location,
                "checkpoint_location": location_parts["location"],
                "checkpoint_location_id": location_parts["location_id"],
                "world_fields": world_fields,
                "group_key": group_key,
            }
        )

    candidates.sort(key=lambda item: item["source_index"])
    return candidates


def _group_rebuild_candidates(candidates: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group adjacent candidate rows that represent the same effective beat."""
    if not candidates:
        return []

    groups: List[List[Dict[str, Any]]] = []
    current_group: List[Dict[str, Any]] = [candidates[0]]

    for candidate in candidates[1:]:
        last = current_group[-1]
        is_same_group = (
            candidate["group_key"] == last["group_key"]
            and abs(candidate["source_index"] - last["source_index"]) <= 2
        )
        if is_same_group:
            current_group.append(candidate)
            continue

        groups.append(current_group)
        current_group = [candidate]

    groups.append(current_group)
    return _merge_near_duplicate_groups(groups)


def _select_best_group_candidate(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Select strongest narrative candidate from one grouped beat."""
    if not group:
        return {}
    return max(
        group,
        key=lambda item: (
            len(str(item.get("summary", ""))),
            -_safe_int(item.get("source_index"), 0),
        ),
    )


def _time_to_seconds(time_text: Any) -> int:
    """Convert HH:MM:SS into seconds from midnight."""
    hour, minute, second = _parse_time_parts(time_text)
    return (hour * 3600) + (minute * 60) + second


def _summary_tokens(summary_text: Any) -> List[str]:
    """Build normalized lexical token list for summary similarity checks."""
    text = str(summary_text or "").lower()
    tokens = _SUMMARY_TOKEN_PATTERN.findall(text)
    filtered = [token for token in tokens if token not in _SUMMARY_STOPWORDS]
    if filtered:
        return filtered
    return tokens


def _summary_similarity(a_summary: Any, b_summary: Any) -> float:
    """Compute conservative token overlap similarity between two summaries."""
    a_tokens = set(_summary_tokens(a_summary))
    b_tokens = set(_summary_tokens(b_summary))
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = len(a_tokens.intersection(b_tokens))
    union = len(a_tokens.union(b_tokens))
    if union <= 0:
        return 0.0
    return float(intersection) / float(union)


def _should_merge_group_blocks(previous_group: List[Dict[str, Any]], next_group: List[Dict[str, Any]]) -> bool:
    """Return True when adjacent groups are likely duplicate chapter variants."""
    if not previous_group or not next_group:
        return False

    previous_best = _select_best_group_candidate(previous_group)
    next_best = _select_best_group_candidate(next_group)
    if not previous_best or not next_best:
        return False

    prev_world = previous_best.get("world_fields", {})
    next_world = next_best.get("world_fields", {})

    same_day = (
        _safe_int(prev_world.get("world_year"), 0) == _safe_int(next_world.get("world_year"), 0)
        and str(prev_world.get("world_month", "")).lower() == str(next_world.get("world_month", "")).lower()
        and _safe_int(prev_world.get("world_day"), 0) == _safe_int(next_world.get("world_day"), 0)
    )
    if not same_day:
        return False

    prev_location = str(previous_best.get("checkpoint_location", "") or "").strip().lower()
    next_location = str(next_best.get("checkpoint_location", "") or "").strip().lower()
    if not prev_location or prev_location != next_location:
        return False

    prev_seconds = _time_to_seconds(prev_world.get("world_time", "00:00:00"))
    next_seconds = _time_to_seconds(next_world.get("world_time", "00:00:00"))
    time_delta = abs(next_seconds - prev_seconds)
    if time_delta <= REBUILD_STRICT_NEAR_DUP_SECONDS:
        return True

    if time_delta > REBUILD_NEAR_DUP_SECONDS:
        return False

    similarity = _summary_similarity(previous_best.get("summary", ""), next_best.get("summary", ""))
    if similarity >= REBUILD_NEAR_DUP_SIMILARITY:
        return True

    prev_location_id = str(previous_best.get("checkpoint_location_id", "") or "").strip().lower()
    next_location_id = str(next_best.get("checkpoint_location_id", "") or "").strip().lower()
    if prev_location_id and next_location_id and prev_location_id == next_location_id:
        return similarity >= 0.12

    return False


def _merge_near_duplicate_groups(groups: List[List[Dict[str, Any]]]) -> List[List[Dict[str, Any]]]:
    """Merge adjacent groups that represent near-duplicate chapter variants."""
    if not groups:
        return []

    merged: List[List[Dict[str, Any]]] = [list(groups[0])]
    for next_group in groups[1:]:
        previous_group = merged[-1]
        if _should_merge_group_blocks(previous_group, next_group):
            previous_group.extend(next_group)
            continue
        merged.append(list(next_group))

    return merged


def _build_rebuild_source_counts(group: List[Dict[str, Any]], source_start: int, source_end: int) -> str:
    """Build source-count payload for one rebuilt chapter row."""
    payload = {
        "journal_entries": len(group),
        "source_mode": "journal_chapter_rebuild",
        "beat_count": len(group),
        "source_type_counts": {"journal": len(group)},
        "source_start_event_id": source_start,
        "source_end_event_id": source_end,
        "chapter_source_start_index": source_start,
        "chapter_source_end_index": source_end,
        "chapter_source_entry_count": len(group),
    }
    return json.dumps(payload, sort_keys=True)


def _build_deterministic_chapter_summary(group: List[Dict[str, Any]]) -> str:
    """Build deterministic chapter summary from grouped journal entries."""
    if not group:
        return "The chapter advanced, but no clear beats were available for recap."

    seen: Dict[str, bool] = {}
    beats: List[str] = []
    for item in sorted(group, key=lambda row: _safe_int(row.get("source_index"), 0)):
        beat = _sanitize_rebuild_summary(item.get("summary", ""))
        if not beat:
            continue
        signature = re.sub(r"[^a-z0-9 ]", " ", beat.lower())
        signature = re.sub(r"\s+", " ", signature).strip()
        if signature and signature in seen:
            continue
        if signature:
            seen[signature] = True
        beats.append(beat)

    if not beats:
        return "The chapter advanced, but no clear beats were available for recap."

    summary_parts: List[str] = [beats[0]]
    for extra in beats[1:4]:
        candidate = " ".join(summary_parts + [extra])
        if len(candidate) > REBUILD_SUMMARY_MAX_CHARS:
            break
        summary_parts.append(extra)

    summary = " ".join(summary_parts).strip()
    if len(summary) > REBUILD_SUMMARY_MAX_CHARS:
        summary = summary[:REBUILD_SUMMARY_MAX_CHARS].rstrip(" ,;:-") + "..."
    return summary


def _sanitize_generated_chapter_summary(summary_text: str, fallback_summary: str) -> str:
    """Sanitize generated chapter summary and fail closed to fallback."""
    cleaned = _sanitize_rebuild_summary(summary_text)
    if not cleaned:
        return fallback_summary
    if _looks_like_structured_artifact(cleaned):
        return fallback_summary
    if len(cleaned) > REBUILD_SUMMARY_MAX_CHARS:
        cleaned = cleaned[:REBUILD_SUMMARY_MAX_CHARS].rstrip(" ,;:-") + "..."
    return cleaned


def _render_chapter_summary_prompt(group: List[Dict[str, Any]], chapter_index: int) -> str:
    """Render compact prompt for one chapter-summary generation."""
    if not group:
        return ""

    ordered = sorted(group, key=lambda row: _safe_int(row.get("source_index"), 0))
    first = ordered[0]
    world_fields = first.get("world_fields", {})
    month = str(world_fields.get("world_month", "") or "Unknown Month").strip() or "Unknown Month"
    day = _safe_int(world_fields.get("world_day"), 0)
    year = _safe_int(world_fields.get("world_year"), 0)
    world_time = str(world_fields.get("world_time", "00:00:00") or "00:00:00").strip() or "00:00:00"
    location = str(first.get("checkpoint_location", "") or "Unknown Location").strip() or "Unknown Location"

    beats: List[str] = []
    for item in ordered[:8]:
        beat = str(item.get("summary", "") or "").strip()
        if not beat:
            continue
        beats.append(f"- {beat}")

    if not beats:
        return ""

    return (
        f"Chapter {chapter_index} context:\n"
        f"Date: {month} {day}, {year}\n"
        f"Time: {world_time}\n"
        f"Location: {location}\n"
        "Summarize the chapter beats below into one concise diary paragraph (3-6 sentences), "
        "in-world, player-facing, no headings, no JSON, no bullet points, no system terms.\n"
        "Chapter beats:\n"
        + "\n".join(beats)
    )


def _generate_rebuild_chapter_summary(group: List[Dict[str, Any]], chapter_index: int) -> Dict[str, Any]:
    """Generate one chapter summary with optional LLM path and deterministic fallback."""
    fallback_summary = _build_deterministic_chapter_summary(group)
    fallback_payload = {
        "summary": fallback_summary,
        "generation_mode": "fallback",
        "llm_model": None,
    }

    if not ENABLE_SESSION_DIARY_LLM:
        return fallback_payload

    if not AI_CLIENTS_AVAILABLE:
        warning(
            "SESSION_DIARY: LLM-enabled checkpoint summary degraded because AI client dependencies are unavailable in this interpreter",
            category="memory_db",
        )
        return fallback_payload

    prompt = _render_chapter_summary_prompt(group, chapter_index)
    if not prompt:
        return fallback_payload

    config = get_model_config("summaries", DM_SUMMARIZATION_MODEL)
    client = create_chat_client()

    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "Write concise in-world chapter recap prose and return only the paragraph.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=config.get("temperature", 0.7),
            **config.get("extra_body", {}),
        )
        generated = ""
        if response.choices and response.choices[0].message:
            generated = str(response.choices[0].message.content or "").strip()
        sanitized = _sanitize_generated_chapter_summary(generated, fallback_summary)
        if sanitized == fallback_summary:
            return fallback_payload
        return {
            "summary": sanitized,
            "generation_mode": "llm",
            "llm_model": config["model"],
        }
    except Exception as generation_error:
        error_info = handle_provider_error(generation_error, context="session_diary_chapter_rebuild")
        if error_info.get("should_fallback"):
            try:
                fallback_client = create_chat_client(use_fallback=True)
                fallback_response = fallback_client.chat.completions.create(
                    model=DM_SUMMARIZATION_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "Write concise in-world chapter recap prose and return only the paragraph.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    temperature=config.get("temperature", 0.7),
                )
                generated = ""
                if fallback_response.choices and fallback_response.choices[0].message:
                    generated = str(fallback_response.choices[0].message.content or "").strip()
                sanitized = _sanitize_generated_chapter_summary(generated, fallback_summary)
                if sanitized != fallback_summary:
                    return {
                        "summary": sanitized,
                        "generation_mode": "llm_fallback",
                        "llm_model": DM_SUMMARIZATION_MODEL,
                    }
            except Exception as fallback_error:
                warning(
                    f"SESSION_DIARY: Rebuild chapter fallback generation failed: {fallback_error}",
                    category="memory_db",
                )

        warning(
            f"SESSION_DIARY: Rebuild chapter generation degraded: {generation_error}",
            category="memory_db",
        )
        return fallback_payload


def _resolve_rebuild_module(conn: sqlite3.Connection, journal_payload: Dict[str, Any]) -> str:
    """Resolve stable module label for rebuilt rows with conservative precedence."""
    existing_rows = conn.execute(
        """
        SELECT checkpoint_module
        FROM session_diary_entries
        WHERE checkpoint_module IS NOT NULL
          AND TRIM(checkpoint_module) != ''
        """
    ).fetchall()

    existing_modules: List[str] = []
    for row in existing_rows:
        value = str(row["checkpoint_module"] or "").strip()
        if not value:
            continue
        if value.lower() == "unknown module":
            continue
        existing_modules.append(value)

    unique_existing = sorted(set(existing_modules))
    if len(unique_existing) == 1:
        return unique_existing[0]

    tracker = safe_json_load(_resolve_runtime_path("party_tracker.json")) or {}
    if isinstance(tracker, dict):
        tracker_module = str(tracker.get("module", "") or "").strip()
        if tracker_module:
            return tracker_module

    if isinstance(journal_payload, dict):
        journal_module = str(journal_payload.get("module", "") or "").strip()
        if journal_module:
            return journal_module

    return "Unknown Module"


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
    source_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Fetch bounded journal entries for checkpoint summarization."""
    if end_event_id <= start_event_id:
        return []

    params: List[Any] = [start_event_id, end_event_id]
    where_clause = "entry_id > ? AND entry_id <= ?"
    if source_types:
        normalized_types = [str(item or "").strip() for item in source_types if str(item or "").strip()]
        if normalized_types:
            placeholders = ", ".join(["?"] * len(normalized_types))
            where_clause += f" AND source_type IN ({placeholders})"
            params.extend(normalized_types)

    params.append(max(MIN_LIST_LIMIT, min(limit, MAX_SOURCE_EVENTS)))
    query = (
        "SELECT entry_id, entry_ts, title, content, source_type "
        "FROM journal_entries "
        f"WHERE {where_clause} "
        "ORDER BY entry_id ASC "
        "LIMIT ?"
    )
    cursor = conn.execute(query, tuple(params))
    return [dict(row) for row in cursor.fetchall()]


def _build_source_counts(
    entries: List[Dict[str, Any]],
    start_event_id: int,
    end_event_id: int,
    source_mode: str = "journal",
    beat_count: int = 0,
) -> str:
    """Build deterministic source count payload for diary rows."""
    source_type_counts: Dict[str, int] = {}
    for entry in entries:
        source_type = str(entry.get("source_type", "unknown") or "unknown").strip().lower() or "unknown"
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1

    payload = {
        "journal_entries": len(entries),
        "source_mode": source_mode,
        "beat_count": beat_count,
        "source_type_counts": source_type_counts,
        "source_start_event_id": start_event_id,
        "source_end_event_id": end_event_id,
    }
    return json.dumps(payload, sort_keys=True)


def _normalize_clause(text: Any, fallback: str) -> str:
    """Normalize one fallback clause for stable sentence assembly."""
    value = str(text or "").strip()
    if not value:
        value = fallback
    value = re.sub(r"\s+", " ", value)
    return value.rstrip(".!? ")


def _looks_like_structured_artifact(text: str) -> bool:
    """Return True when text resembles out-of-world structured runtime payloads."""
    sample = str(text or "").strip()
    if not sample:
        return True

    for pattern in _DIARY_STRUCTURED_PATTERNS:
        if pattern.search(sample):
            return True

    brace_count = sample.count("{") + sample.count("}")
    bracket_count = sample.count("[") + sample.count("]")
    if (brace_count + bracket_count) >= 12:
        return True

    return False


def _ascii_normalize(text: str) -> str:
    """Normalize common punctuation variants and force ASCII-safe text."""
    normalized = str(text or "")
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "--",
        "\u2014": "--",
        "\u2026": "...",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized.encode("ascii", "replace").decode("ascii")


def _strip_journal_headers(text: str) -> str:
    """Drop common journal header lines to keep recap beats concise."""
    cleaned = str(text or "")
    for pattern in _JOURNAL_HEADER_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return cleaned


def _split_sentences(text: str) -> List[str]:
    """Split text into sentence-like chunks with conservative boundaries."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    chunks = re.split(r"(?<=[.!?])\s+", cleaned)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _build_compact_beat_text(text: str) -> str:
    """Condense one source text into a short diary-safe beat."""
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    compact = " ".join(sentences[:MAX_BEAT_SENTENCES]).strip()
    if len(compact) > MAX_BEAT_CHARS:
        compact = compact[:MAX_BEAT_CHARS].rstrip(" ,;:-") + "..."
    return compact


def _sanitize_source_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return sanitized diary beat payload for one source entry."""
    source_type = str(entry.get("source_type", "") or "").strip().lower()
    raw_title = str(entry.get("title", "") or "").strip()
    raw_text = str(entry.get("summary") or entry.get("content") or "").strip()
    if not raw_text:
        return None

    if _looks_like_structured_artifact(raw_text):
        return None

    cleaned = _ascii_normalize(raw_text)
    cleaned = _strip_journal_headers(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    beat_text = _build_compact_beat_text(cleaned)
    if not beat_text:
        return None

    if _looks_like_structured_artifact(beat_text):
        return None

    title_key = re.sub(r"\([^)]*\)", "", raw_title)
    title_key = re.sub(r"[^a-z0-9 ]", " ", title_key.lower())
    title_key = re.sub(r"\s+", " ", title_key).strip() or "unknown"

    signature = re.sub(r"[^a-z0-9 ]", " ", beat_text.lower())
    signature = re.sub(r"\s+", " ", signature).strip()
    signature = signature[:220]

    return {
        "entry_id": _safe_int(entry.get("entry_id"), 0),
        "entry_ts": str(entry.get("entry_ts", "") or "").strip(),
        "source_type": source_type,
        "title": raw_title,
        "title_key": title_key,
        "summary_text": beat_text,
        "signature": signature,
    }


def _dedupe_source_beats(beats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse duplicate or near-duplicate beats for concise diary generation."""
    if not beats:
        return []

    deduped: List[Dict[str, Any]] = []
    seen_signatures: Dict[str, int] = {}
    title_last_index: Dict[str, int] = {}

    for beat in beats:
        signature = str(beat.get("signature", "") or "").strip()
        if signature and signature in seen_signatures:
            continue

        title_key = str(beat.get("title_key", "unknown") or "unknown")
        current_entry_id = _safe_int(beat.get("entry_id"), 0)
        prev_index = title_last_index.get(title_key)

        if prev_index is not None:
            previous = deduped[prev_index]
            prev_entry_id = _safe_int(previous.get("entry_id"), 0)
            if abs(current_entry_id - prev_entry_id) <= 3:
                current_len = len(str(beat.get("summary_text", "")))
                previous_len = len(str(previous.get("summary_text", "")))
                if 0 < current_len < previous_len:
                    deduped[prev_index] = beat
                continue

        deduped.append(beat)
        title_last_index[title_key] = len(deduped) - 1
        if signature:
            seen_signatures[signature] = 1

    return deduped


def _build_checkpoint_source_packet(
    conn: sqlite3.Connection,
    start_event_id: int,
    end_event_id: int,
) -> Dict[str, Any]:
    """Build a journal-first sanitized source packet for one checkpoint window."""
    journal_rows = _fetch_source_entries_bounded(
        conn,
        start_event_id,
        end_event_id,
        source_types=["journal"],
    )

    source_mode = "journal"
    selected_rows = journal_rows
    if not journal_rows:
        source_mode = "history_fallback"
        selected_rows = _fetch_source_entries_bounded(
            conn,
            start_event_id,
            end_event_id,
            source_types=["conversation_history", "combat_history"],
        )

    beats = []
    for entry in selected_rows:
        sanitized = _sanitize_source_entry(entry)
        if sanitized is not None:
            beats.append(sanitized)

    beats = _dedupe_source_beats(beats)

    # TABLETOP MODE: if journal rows exist but were all filtered as noise,
    # allow one fallback pass from history sources to avoid empty checkpoints.
    if source_mode == "journal" and not beats:
        fallback_rows = _fetch_source_entries_bounded(
            conn,
            start_event_id,
            end_event_id,
            source_types=["conversation_history", "combat_history"],
        )
        fallback_beats = []
        for entry in fallback_rows:
            sanitized = _sanitize_source_entry(entry)
            if sanitized is not None:
                fallback_beats.append(sanitized)
        fallback_beats = _dedupe_source_beats(fallback_beats)
        if fallback_beats:
            source_mode = "history_fallback"
            selected_rows = fallback_rows
            beats = fallback_beats

    return {
        "source_mode": source_mode,
        "raw_entries": selected_rows,
        "beats": beats,
    }


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


def build_fallback_summary(
    source_events: List[Dict[str, Any]],
    checkpoint_context: Optional[Dict[str, str]] = None,
) -> str:
    """Return deterministic fallback diary text from source events."""
    context = checkpoint_context if isinstance(checkpoint_context, dict) else {}
    location = _normalize_checkpoint_text(context.get("checkpoint_location"), "Unknown Location")

    if not source_events:
        summary = f"At {location}, the party's recent travels left no clear diary beats in this checkpoint window."
        return summary[:MAX_SUMMARY_CHARS].rstrip(" ,;:-")

    first = source_events[0]
    last = source_events[-1]
    first_text = _normalize_clause(
        first.get("summary_text") or first.get("summary") or first.get("content"),
        "The journey continued",
    )
    last_text = _normalize_clause(
        last.get("summary_text") or last.get("summary") or last.get("content"),
        "the chapter closed",
    )

    if first_text == last_text:
        summary = f"At {location}, {first_text}."
    else:
        summary = f"At {location}, {first_text}. Later, {last_text}."

    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS].rstrip(" ,;:-") + "..."
    return summary


def _build_time_context(world_data: Dict[str, Any], checkpoint_context: Dict[str, str]) -> str:
    """Build compact world-line time/location context string."""
    month = str(world_data.get("world_month", "") or "").strip() or "Unknown Month"
    day = _safe_int(world_data.get("world_day"), 0)
    year = _safe_int(world_data.get("world_year"), 0)
    world_time = str(world_data.get("world_time", "00:00:00") or "00:00:00").strip() or "00:00:00"
    location = _normalize_checkpoint_text(checkpoint_context.get("checkpoint_location"), "Unknown Location")
    module_name = _normalize_checkpoint_text(checkpoint_context.get("checkpoint_module"), "Unknown Module")
    return f"{month} {day}, {year} at {world_time} in {location} ({module_name})"


def _build_source_window_summary(source_beats: List[Dict[str, Any]]) -> str:
    """Build compact source-window digest for diary prompt context."""
    if not source_beats:
        return "No clean beats were available in this checkpoint window."

    lines: List[str] = []
    for beat in source_beats[:MAX_PROMPT_BEATS]:
        beat_text = str(beat.get("summary_text", "") or "").strip()
        if not beat_text:
            continue
        if len(beat_text) > MAX_PROMPT_CHARS_PER_BEAT:
            beat_text = beat_text[:MAX_PROMPT_CHARS_PER_BEAT].rstrip(" ,;:-") + "..."
        lines.append(f"- {beat_text}")

    if not lines:
        return "No clean beats were available in this checkpoint window."
    return "\n".join(lines)


def _build_chat_excerpt(source_beats: List[Dict[str, Any]]) -> str:
    """Build compact chat-like excerpt field from sanitized beats."""
    if not source_beats:
        return "No excerpt available."

    excerpt_lines: List[str] = []
    for beat in source_beats[:3]:
        beat_text = str(beat.get("summary_text", "") or "").strip()
        if not beat_text:
            continue
        excerpt_lines.append(beat_text)

    if not excerpt_lines:
        return "No excerpt available."
    return "\n".join(excerpt_lines)


def _build_active_plot_snapshot() -> str:
    """Build compact active-plot context from tracker state."""
    tracker = safe_json_load(_resolve_runtime_path("party_tracker.json")) or {}
    if not isinstance(tracker, dict):
        return "No active plot metadata available."

    candidates = [
        tracker.get("activePlotPoint"),
        tracker.get("active_plot_point"),
        tracker.get("activePlot"),
        tracker.get("active_plot"),
        tracker.get("plotPoint"),
        tracker.get("plot_point"),
    ]
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return "No active plot metadata available."


def _build_authoritative_state_snapshot(world_data: Dict[str, Any], checkpoint_context: Dict[str, str]) -> str:
    """Build compact authoritative state snapshot JSON for prompt context."""
    payload = {
        "world": {
            "year": _safe_int(world_data.get("world_year"), 0),
            "month": str(world_data.get("world_month", "") or "").strip(),
            "day": _safe_int(world_data.get("world_day"), 0),
            "time": str(world_data.get("world_time", "00:00:00") or "00:00:00").strip(),
            "sort_key": _safe_int(world_data.get("world_sort_key"), 0),
        },
        "checkpoint": {
            "module": _normalize_checkpoint_text(checkpoint_context.get("checkpoint_module"), "Unknown Module"),
            "location": _normalize_checkpoint_text(checkpoint_context.get("checkpoint_location"), "Unknown Location"),
            "location_id": str(checkpoint_context.get("checkpoint_location_id", "") or "").strip(),
            "area": _normalize_checkpoint_text(checkpoint_context.get("checkpoint_area"), "Unknown Area"),
            "area_id": str(checkpoint_context.get("checkpoint_area_id", "") or "").strip(),
        },
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _render_diary_prompt(
    checkpoint_type: str,
    source_beats: List[Dict[str, Any]],
    checkpoint_context: Dict[str, str],
    world_data: Dict[str, Any],
) -> str:
    """Render session diary prompt with sanitized compact context."""
    template = _load_diary_template()
    if not template:
        return ""

    campaign_name = _normalize_checkpoint_text(checkpoint_context.get("checkpoint_module"), "Unknown Campaign").replace("_", " ")
    module_name = _normalize_checkpoint_text(checkpoint_context.get("checkpoint_module"), "Unknown Module")
    replacements = {
        "{campaign_name}": campaign_name,
        "{module_name}": module_name,
        "{checkpoint_type}": str(checkpoint_type or "checkpoint").strip() or "checkpoint",
        "{time_context}": _build_time_context(world_data, checkpoint_context),
        "{source_window_summary}": _build_source_window_summary(source_beats),
        "{chat_excerpt}": _build_chat_excerpt(source_beats),
        "{authoritative_state_snapshot}": _build_authoritative_state_snapshot(world_data, checkpoint_context),
        "{active_plot_snapshot}": _build_active_plot_snapshot(),
    }

    prompt = template
    for key, value in replacements.items():
        prompt = prompt.replace(key, value)
    return prompt


def _sanitize_generated_summary(summary_text: str, fallback_summary: str) -> str:
    """Normalize generated diary prose and fail closed to fallback when unsafe."""
    cleaned = _ascii_normalize(summary_text)
    cleaned = _strip_journal_headers(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return fallback_summary

    if _looks_like_structured_artifact(cleaned):
        return fallback_summary

    if len(cleaned) > MAX_SUMMARY_CHARS:
        cleaned = cleaned[:MAX_SUMMARY_CHARS].rstrip(" ,;:-") + "..."
    return cleaned


def _generate_checkpoint_summary(
    source_beats: List[Dict[str, Any]],
    checkpoint_context: Dict[str, str],
    world_data: Dict[str, Any],
    checkpoint_type: str,
) -> Dict[str, Any]:
    """Generate checkpoint summary with provider-agnostic LLM path and fail-open fallback."""
    fallback_summary = build_fallback_summary(source_beats, checkpoint_context)
    fallback_payload = {
        "summary": fallback_summary,
        "generation_mode": "fallback",
        "llm_model": None,
    }

    if not ENABLE_SESSION_DIARY_LLM:
        return fallback_payload

    if not AI_CLIENTS_AVAILABLE:
        warning(
            "SESSION_DIARY: LLM-enabled chapter rebuild degraded because AI client dependencies are unavailable in this interpreter",
            category="memory_db",
        )
        return fallback_payload

    if not source_beats:
        return fallback_payload

    prompt = _render_diary_prompt(checkpoint_type, source_beats, checkpoint_context, world_data)
    if not prompt:
        return fallback_payload

    config = get_model_config("summaries", DM_SUMMARIZATION_MODEL)
    client = create_chat_client()

    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "You write concise in-world checkpoint diary prose and return only the diary text.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=config.get("temperature", 0.7),
            **config.get("extra_body", {}),
        )
        generated = ""
        if response.choices and response.choices[0].message:
            generated = str(response.choices[0].message.content or "").strip()
        sanitized = _sanitize_generated_summary(generated, fallback_summary)
        if sanitized == fallback_summary:
            return fallback_payload
        return {
            "summary": sanitized,
            "generation_mode": "llm",
            "llm_model": config["model"],
        }
    except Exception as generation_error:
        error_info = handle_provider_error(generation_error, context="session_diary")
        if error_info.get("should_fallback"):
            try:
                fallback_client = create_chat_client(use_fallback=True)
                fallback_response = fallback_client.chat.completions.create(
                    model=DM_SUMMARIZATION_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You write concise in-world checkpoint diary prose and return only the diary text.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    temperature=config.get("temperature", 0.7),
                )
                generated = ""
                if fallback_response.choices and fallback_response.choices[0].message:
                    generated = str(fallback_response.choices[0].message.content or "").strip()
                sanitized = _sanitize_generated_summary(generated, fallback_summary)
                if sanitized != fallback_summary:
                    return {
                        "summary": sanitized,
                        "generation_mode": "llm_fallback",
                        "llm_model": DM_SUMMARIZATION_MODEL,
                    }
            except Exception as fallback_error:
                warning(
                    f"SESSION_DIARY: Fallback diary generation failed: {fallback_error}",
                    category="memory_db",
                )

        warning(
            f"SESSION_DIARY: LLM diary generation degraded: {generation_error}",
            category="memory_db",
        )
        return fallback_payload


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
    checkpoint_context = _resolve_checkpoint_context(world_conditions)

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

        source_packet = _build_checkpoint_source_packet(conn, last_draft_event_id, latest_entry_id)
        source_entries = source_packet["raw_entries"]
        source_beats = source_packet["beats"]
        source_mode = str(source_packet["source_mode"])
        summary_payload = _generate_checkpoint_summary(
            source_beats=source_beats,
            checkpoint_context=checkpoint_context,
            world_data=world_data,
            checkpoint_type="draft",
        )
        diary_summary = str(summary_payload["summary"])
        generation_mode = str(summary_payload.get("generation_mode", "fallback") or "fallback")
        llm_model = summary_payload.get("llm_model")
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
                        checkpoint_module = ?,
                        checkpoint_location = ?,
                        checkpoint_location_id = ?,
                        checkpoint_area = ?,
                        checkpoint_area_id = ?,
                        generation_mode = ?,
                        llm_model = ?,
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
                        diary_summary,
                        source_start_event_id,
                        latest_entry_id,
                        _build_source_counts(
                            source_entries,
                            last_draft_event_id,
                            latest_entry_id,
                            source_mode=source_mode,
                            beat_count=len(source_beats),
                        ),
                        checkpoint_context["checkpoint_module"],
                        checkpoint_context["checkpoint_location"],
                        checkpoint_context["checkpoint_location_id"],
                        checkpoint_context["checkpoint_area"],
                        checkpoint_context["checkpoint_area_id"],
                        generation_mode,
                        llm_model,
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
                        checkpoint_module,
                        checkpoint_location,
                        checkpoint_location_id,
                        checkpoint_area,
                        checkpoint_area_id,
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
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
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
                        diary_summary,
                        source_start_event_id,
                        latest_entry_id,
                        _build_source_counts(
                            source_entries,
                            last_draft_event_id,
                            latest_entry_id,
                            source_mode=source_mode,
                            beat_count=len(source_beats),
                        ),
                        checkpoint_context["checkpoint_module"],
                        checkpoint_context["checkpoint_location"],
                        checkpoint_context["checkpoint_location_id"],
                        checkpoint_context["checkpoint_area"],
                        checkpoint_context["checkpoint_area_id"],
                        generation_mode,
                        llm_model,
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
            "beat_count": len(source_beats),
            "source_mode": source_mode,
            "generation_mode": generation_mode,
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
    checkpoint_context = _resolve_checkpoint_context(world_conditions)

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

        source_packet = _build_checkpoint_source_packet(conn, last_confirmed_event_id, latest_entry_id)
        source_entries = source_packet["raw_entries"]
        source_beats = source_packet["beats"]
        source_mode = str(source_packet["source_mode"])
        summary_payload = _generate_checkpoint_summary(
            source_beats=source_beats,
            checkpoint_context=checkpoint_context,
            world_data=world_data,
            checkpoint_type=checkpoint_type,
        )
        diary_summary = str(summary_payload["summary"])
        generation_mode = str(summary_payload.get("generation_mode", "fallback") or "fallback")
        llm_model = summary_payload.get("llm_model")
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
                    checkpoint_module,
                    checkpoint_location,
                    checkpoint_location_id,
                    checkpoint_area,
                    checkpoint_area_id,
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
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
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
                    diary_summary,
                    source_start_event_id,
                    latest_entry_id,
                    _build_source_counts(
                        source_entries,
                        last_confirmed_event_id,
                        latest_entry_id,
                        source_mode=source_mode,
                        beat_count=len(source_beats),
                    ),
                    checkpoint_context["checkpoint_module"],
                    checkpoint_context["checkpoint_location"],
                    checkpoint_context["checkpoint_location_id"],
                    checkpoint_context["checkpoint_area"],
                    checkpoint_context["checkpoint_area_id"],
                    generation_mode,
                    llm_model,
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
            "beat_count": len(source_beats),
            "source_mode": source_mode,
            "generation_mode": generation_mode,
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
    checkpoint_context = _resolve_checkpoint_context(world_conditions)

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

        source_packet = _build_checkpoint_source_packet(conn, last_confirmed_event_id, latest_entry_id)
        source_entries = source_packet["raw_entries"]
        source_beats = source_packet["beats"]
        source_mode = str(source_packet["source_mode"])
        summary_payload = _generate_checkpoint_summary(
            source_beats=source_beats,
            checkpoint_context=checkpoint_context,
            world_data=world_data,
            checkpoint_type=checkpoint_type,
        )
        diary_summary = str(summary_payload["summary"])
        generation_mode = str(summary_payload.get("generation_mode", "fallback") or "fallback")
        llm_model = summary_payload.get("llm_model")
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
                    checkpoint_module,
                    checkpoint_location,
                    checkpoint_location_id,
                    checkpoint_area,
                    checkpoint_area_id,
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
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
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
                    diary_summary,
                    source_start_event_id,
                    latest_entry_id,
                    _build_source_counts(
                        source_entries,
                        last_confirmed_event_id,
                        latest_entry_id,
                        source_mode=source_mode,
                        beat_count=len(source_beats),
                    ),
                    checkpoint_context["checkpoint_module"],
                    checkpoint_context["checkpoint_location"],
                    checkpoint_context["checkpoint_location_id"],
                    checkpoint_context["checkpoint_area"],
                    checkpoint_context["checkpoint_area_id"],
                    generation_mode,
                    llm_model,
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
            "beat_count": len(source_beats),
            "source_mode": source_mode,
            "generation_mode": generation_mode,
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


def remediate_diary_entries(
    db_path: str,
    include_draft: bool = True,
    include_confirmed: bool = True,
    dry_run: bool = True,
    limit: int = 0,
) -> Dict[str, Any]:
    """Rebuild stored diary summaries from sanitized checkpoint source windows."""
    if not init_memory_db(db_path):
        return {
            "status": "error",
            "message": "Memory DB initialization failed",
            "db_path": db_path,
        }

    conn: Optional[sqlite3.Connection] = None
    safe_limit = max(0, _safe_int(limit, 0))
    statuses: List[str] = []
    if include_draft:
        statuses.append("draft")
    if include_confirmed:
        statuses.append("confirmed")
    if not statuses:
        return {
            "status": "success",
            "db_path": db_path,
            "scanned": 0,
            "updated": 0,
            "would_update": 0,
            "dry_run": dry_run,
            "message": "No statuses selected",
        }

    try:
        conn = _connect(db_path)
        _ensure_state_row(conn)

        placeholders = ", ".join(["?"] * len(statuses))
        query = (
            "SELECT * FROM session_diary_entries "
            f"WHERE status IN ({placeholders}) "
            "ORDER BY diary_id ASC"
        )
        params: List[Any] = list(statuses)
        if safe_limit > 0:
            query += " LIMIT ?"
            params.append(safe_limit)

        rows = conn.execute(query, tuple(params)).fetchall()
        if not rows:
            return {
                "status": "success",
                "db_path": db_path,
                "scanned": 0,
                "updated": 0,
                "would_update": 0,
                "dry_run": dry_run,
            }

        scanned = 0
        updated = 0
        would_update = 0
        changed_ids: List[int] = []
        now_iso = _utc_now_iso()
        default_context = _resolve_checkpoint_context(None)

        for row in rows:
            scanned += 1
            start_event_id = _safe_int(row["source_start_event_id"], 0)
            end_event_id = _safe_int(row["source_end_event_id"], 0)

            source_packet = _build_checkpoint_source_packet(conn, start_event_id, end_event_id)
            source_entries = source_packet["raw_entries"]
            source_beats = source_packet["beats"]
            source_mode = str(source_packet["source_mode"])

            checkpoint_context = {
                "checkpoint_module": _prefer_checkpoint_fallback(
                    row["checkpoint_module"] if "checkpoint_module" in row.keys() else None,
                    default_context.get("checkpoint_module", "Unknown Module"),
                    "Unknown Module",
                ),
                "checkpoint_location": _prefer_checkpoint_fallback(
                    row["checkpoint_location"] if "checkpoint_location" in row.keys() else None,
                    default_context.get("checkpoint_location", "Unknown Location"),
                    "Unknown Location",
                ),
                "checkpoint_location_id": str(
                    row["checkpoint_location_id"] if "checkpoint_location_id" in row.keys() else ""
                ).strip(),
                "checkpoint_area": _prefer_checkpoint_fallback(
                    row["checkpoint_area"] if "checkpoint_area" in row.keys() else None,
                    default_context.get("checkpoint_area", "Unknown Area"),
                    "Unknown Area",
                ),
                "checkpoint_area_id": str(row["checkpoint_area_id"] if "checkpoint_area_id" in row.keys() else "").strip(),
            }

            rebuilt_summary = build_fallback_summary(source_beats, checkpoint_context)
            rebuilt_source_counts = _build_source_counts(
                source_entries,
                start_event_id,
                end_event_id,
                source_mode=source_mode,
                beat_count=len(source_beats),
            )

            row_summary = str(row["summary"] or "").strip()
            row_source_counts = str(row["source_counts_json"] or "").strip()
            row_generation_mode = str(row["generation_mode"] or "").strip().lower()
            row_llm_model = row["llm_model"]

            needs_update = (
                rebuilt_summary != row_summary
                or rebuilt_source_counts != row_source_counts
                or row_generation_mode != "fallback"
                or row_llm_model is not None
                or _normalize_checkpoint_text(
                    row["checkpoint_location"] if "checkpoint_location" in row.keys() else None,
                    "Unknown Location",
                ) != checkpoint_context["checkpoint_location"]
            )

            if not needs_update:
                continue

            would_update += 1
            changed_ids.append(_safe_int(row["diary_id"], 0))
            if dry_run:
                continue

            with conn:
                conn.execute(
                    """
                    UPDATE session_diary_entries
                    SET
                        summary = ?,
                        source_counts_json = ?,
                        generation_mode = 'fallback',
                        llm_model = NULL,
                        checkpoint_module = ?,
                        checkpoint_location = ?,
                        checkpoint_location_id = ?,
                        checkpoint_area = ?,
                        checkpoint_area_id = ?,
                        updated_at = ?
                    WHERE diary_id = ?
                    """,
                    (
                        rebuilt_summary,
                        rebuilt_source_counts,
                        checkpoint_context["checkpoint_module"],
                        checkpoint_context["checkpoint_location"],
                        checkpoint_context["checkpoint_location_id"],
                        checkpoint_context["checkpoint_area"],
                        checkpoint_context["checkpoint_area_id"],
                        now_iso,
                        row["diary_id"],
                    ),
                )
            updated += 1

        return {
            "status": "success",
            "db_path": db_path,
            "scanned": scanned,
            "updated": updated,
            "would_update": would_update,
            "dry_run": dry_run,
            "changed_ids": [item for item in changed_ids if item > 0],
        }
    except Exception as remediation_error:
        error(
            f"SESSION_DIARY: Remediation failed: {remediation_error}",
            exception=remediation_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(remediation_error),
            "db_path": db_path,
            "dry_run": dry_run,
        }
    finally:
        if conn is not None:
            conn.close()


def rebuild_diary_from_journal(
    db_path: str,
    dry_run: bool = True,
    replace_existing: bool = True,
) -> Dict[str, Any]:
    """Rebuild confirmed diary entries from journal chronology in one transactional pass."""
    if not init_memory_db(db_path):
        return {
            "status": "error",
            "message": "Memory DB initialization failed",
            "db_path": db_path,
        }

    _refresh_diary_source_history(db_path)

    conn: Optional[sqlite3.Connection] = None
    now_iso = _utc_now_iso()

    try:
        conn = _connect(db_path)
        _ensure_state_row(conn)

        journal_payload = _load_journal_payload("journal.json")
        journal_entries = _load_journal_entries_from_file("journal.json")
        if not journal_entries:
            return {
                "status": "error",
                "message": "No journal entries available for rebuild",
                "db_path": db_path,
                "scanned": 0,
                "grouped": 0,
                "replaced": 0,
                "dry_run": dry_run,
            }

        candidates = _build_rebuild_candidates(journal_entries)
        if not candidates:
            return {
                "status": "error",
                "message": "No valid journal candidates available for rebuild",
                "db_path": db_path,
                "scanned": 0,
                "grouped": 0,
                "replaced": 0,
                "dry_run": dry_run,
            }

        groups = _group_rebuild_candidates(candidates)
        module_name = _resolve_rebuild_module(conn, journal_payload)
        latest_entry_id = _get_latest_journal_entry_id(conn)

        existing_row_count = _safe_int(
            conn.execute("SELECT COUNT(*) AS count FROM session_diary_entries").fetchone()["count"],
            0,
        )

        rebuilt_rows: List[Dict[str, Any]] = []
        for index, group in enumerate(groups, start=1):
            best = _select_best_group_candidate(group)
            if not best:
                continue

            world_fields = best["world_fields"]
            source_start = min(_safe_int(item.get("entry_id"), 0) for item in group)
            source_end = max(_safe_int(item.get("entry_id"), 0) for item in group)
            source_counts = _build_rebuild_source_counts(group, source_start, source_end)
            summary_payload = _generate_rebuild_chapter_summary(group, chapter_index=index)
            chapter_summary = str(summary_payload["summary"])
            generation_mode = str(summary_payload.get("generation_mode", "fallback") or "fallback")
            llm_model = summary_payload.get("llm_model")

            rebuilt_rows.append(
                {
                    "checkpoint_type": "rebuild",
                    "checkpoint_id": f"journal_chapter:{index:04d}",
                    "summary": chapter_summary,
                    "world_year": world_fields["world_year"],
                    "world_month": world_fields["world_month"],
                    "world_month_index": world_fields["world_month_index"],
                    "world_day": world_fields["world_day"],
                    "world_time": world_fields["world_time"],
                    "world_sort_key": world_fields["world_sort_key"],
                    "source_start_event_id": source_start,
                    "source_end_event_id": source_end,
                    "source_counts_json": source_counts,
                    "checkpoint_module": module_name,
                    "checkpoint_location": best["checkpoint_location"],
                    "checkpoint_location_id": best["checkpoint_location_id"],
                    "checkpoint_area": best["checkpoint_location"],
                    "checkpoint_area_id": "",
                    "generation_mode": generation_mode,
                    "llm_model": llm_model,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
            )

        if not rebuilt_rows:
            return {
                "status": "error",
                "message": "No grouped diary rows generated for rebuild",
                "db_path": db_path,
                "scanned": len(candidates),
                "grouped": 0,
                "replaced": 0,
                "dry_run": dry_run,
            }

        earliest_meta = {
            "world_month": rebuilt_rows[0]["world_month"],
            "world_day": rebuilt_rows[0]["world_day"],
            "world_time": rebuilt_rows[0]["world_time"],
            "checkpoint_location": rebuilt_rows[0]["checkpoint_location"],
            "checkpoint_module": rebuilt_rows[0]["checkpoint_module"],
        }
        latest_meta = {
            "world_month": rebuilt_rows[-1]["world_month"],
            "world_day": rebuilt_rows[-1]["world_day"],
            "world_time": rebuilt_rows[-1]["world_time"],
            "checkpoint_location": rebuilt_rows[-1]["checkpoint_location"],
            "checkpoint_module": rebuilt_rows[-1]["checkpoint_module"],
        }

        if dry_run:
            return {
                "status": "success",
                "action": "preview",
                "db_path": db_path,
                "scanned": len(candidates),
                "grouped": len(groups),
                "replaced": 0,
                "existing_row_count": existing_row_count,
                "rebuilt_row_count": len(rebuilt_rows),
                "duplicate_collapsed": max(0, len(candidates) - len(groups)),
                "dry_run": True,
                "earliest": earliest_meta,
                "latest": latest_meta,
            }

        if replace_existing:
            with conn:
                conn.execute("DELETE FROM session_diary_entries")

                for row in rebuilt_rows:
                    conn.execute(
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
                            checkpoint_module,
                            checkpoint_location,
                            checkpoint_location_id,
                            checkpoint_area,
                            checkpoint_area_id,
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
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?,
                            ?
                        )
                        """,
                        (
                            row["checkpoint_type"],
                            row["checkpoint_id"],
                            row["world_year"],
                            row["world_month"],
                            row["world_month_index"],
                            row["world_day"],
                            row["world_time"],
                            row["world_sort_key"],
                            row["summary"],
                            row["source_start_event_id"],
                            row["source_end_event_id"],
                            row["source_counts_json"],
                            row["checkpoint_module"],
                            row["checkpoint_location"],
                            row["checkpoint_location_id"],
                            row["checkpoint_area"],
                            row["checkpoint_area_id"],
                            row["generation_mode"],
                            row["llm_model"],
                            row["created_at"],
                            row["updated_at"],
                        ),
                    )

                conn.execute(
                    """
                    UPDATE session_diary_state
                    SET
                        last_draft_event_id = ?,
                        last_confirmed_event_id = ?,
                        last_confirmed_save_id = NULL,
                        last_draft_key = NULL,
                        updated_at = ?
                    WHERE state_id = 1
                    """,
                    (latest_entry_id, latest_entry_id, now_iso),
                )

        return {
            "status": "success",
            "action": "applied",
            "db_path": db_path,
            "scanned": len(candidates),
            "grouped": len(groups),
            "replaced": len(rebuilt_rows),
            "existing_row_count": existing_row_count,
            "rebuilt_row_count": len(rebuilt_rows),
            "duplicate_collapsed": max(0, len(candidates) - len(groups)),
            "dry_run": False,
            "earliest": earliest_meta,
            "latest": latest_meta,
        }
    except Exception as rebuild_error:
        error(
            f"SESSION_DIARY: Rebuild failed: {rebuild_error}",
            exception=rebuild_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(rebuild_error),
            "db_path": db_path,
            "dry_run": dry_run,
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
    "confirm_diary_for_exit",
    "remediate_diary_entries",
    "rebuild_diary_from_journal",
    "list_diary_entries",
]
