# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Memory - Story so far compiler.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

TABLETOP MODE: Confirmed-only story compilation and PDF cache helpers.
"""

import hashlib
import json
import os
import sqlite3
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH, init_memory_db
from model_config import DM_SUMMARIZATION_MODEL
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, error, warning

try:
    from utils.ai_client_factory import (
        create_chat_client,
        get_model_config,
        handle_provider_error,
    )

    AI_CLIENTS_AVAILABLE = True
except ImportError:
    AI_CLIENTS_AVAILABLE = False


STORY_CACHE_DIR = "data/story_so_far_cache"
STORY_TEMPLATE_PATH = "prompts/tabletop/storyteller_campaign_chronicle.txt"
PDF_DOWNLOAD_NAME = "Story_So_Far.pdf"
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
PAGE_MARGIN_X = 72
PAGE_MARGIN_TOP = 740
PAGE_MARGIN_BOTTOM = 72
LINE_HEIGHT = 14
CHARS_PER_LINE = 92


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[1]


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _resolve_runtime_path(relative_path: str) -> str:
    """Resolve runtime paths against cwd first, then project root."""
    cwd_path = Path(relative_path)
    if cwd_path.exists():
        return str(cwd_path)

    return str((PROJECT_ROOT / relative_path).resolve())


def _sanitize_story_text(story_text: str) -> str:
    """Strip prompt leakage and normalize story text to ASCII-safe prose."""
    text = str(story_text or "")

    leakage_markers = [
        "<system-reminder>",
        "# Plan Mode - System Reminder",
        "CRITICAL: Plan mode ACTIVE",
    ]
    for marker in leakage_markers:
        marker_index = text.find(marker)
        if marker_index >= 0:
            text = text[:marker_index]
            break

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
        text = text.replace(old, new)

    text = text.encode("ascii", "replace").decode("ascii")
    text = text.replace("?", "'") if "?s" in text or "?d" in text else text
    return text.strip()


def _connect(db_path: str) -> sqlite3.Connection:
    """Create SQLite connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _load_confirmed_entries(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Load confirmed diary entries in chronological order."""
    rows = conn.execute(
        """
        SELECT *
        FROM session_diary_entries
        WHERE status = 'confirmed'
        ORDER BY world_sort_key ASC, diary_id ASC
        """
    ).fetchall()

    entries: List[Dict[str, Any]] = []
    for row in rows:
        entries.append(
            {
                "diary_id": row["diary_id"],
                "save_id": row["save_id"],
                "summary": row["summary"],
                "generation_mode": row["generation_mode"],
                "llm_model": row["llm_model"],
                "checkpoint": {
                    "module": row["checkpoint_module"]
                    if "checkpoint_module" in row.keys()
                    else None,
                    "location": row["checkpoint_location"]
                    if "checkpoint_location" in row.keys()
                    else None,
                    "location_id": row["checkpoint_location_id"]
                    if "checkpoint_location_id" in row.keys()
                    else None,
                    "area": row["checkpoint_area"]
                    if "checkpoint_area" in row.keys()
                    else None,
                    "area_id": row["checkpoint_area_id"]
                    if "checkpoint_area_id" in row.keys()
                    else None,
                },
                "world": {
                    "year": row["world_year"],
                    "month": row["world_month"],
                    "month_index": row["world_month_index"],
                    "day": row["world_day"],
                    "time": row["world_time"],
                    "sort_key": row["world_sort_key"],
                },
            }
        )
    return entries


def _compute_confirmed_fingerprint(entries: List[Dict[str, Any]]) -> str:
    """Compute deterministic fingerprint for confirmed diary entries."""
    payload = json.dumps(entries, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_story_template() -> str:
    """Load storyteller prompt template from disk."""
    template_path = _resolve_runtime_path(STORY_TEMPLATE_PATH)
    if not os.path.exists(template_path):
        return ""
    with open(template_path, "r", encoding="utf-8") as handle:
        return handle.read()


def _get_current_campaign_context() -> Dict[str, Any]:
    """Load compact current campaign context for ending-state grounding."""
    party_tracker = safe_json_load(_resolve_runtime_path("party_tracker.json")) or {}
    current_location = (
        safe_json_load(_resolve_runtime_path("current_location.json")) or {}
    )

    module_name = str(party_tracker.get("module", "Unknown")).strip() or "Unknown"
    module_plot = {}
    if module_name and module_name.lower() != "unknown":
        module_plot = (
            safe_json_load(
                _resolve_runtime_path(f"modules/{module_name}/module_plot.json")
            )
            or {}
        )

    return {
        "campaign_name": module_name.replace("_", " "),
        "module_name": module_name,
        "party_tracker_json": party_tracker,
        "location_context_json": current_location,
        "plot_json": module_plot,
    }


def _render_story_prompt(entries: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
    """Render storyteller prompt with confirmed diary and campaign context."""
    template = _load_story_template()
    if not template:
        return ""

    replacements = {
        "{campaign_name}": str(context.get("campaign_name", "Unknown Campaign")),
        "{module_name}": str(context.get("module_name", "Unknown Module")),
        "{narrative_scope}": "Confirmed diary timeline only",
        "{target_length}": "Short chapter",
        "{chat_log}": "Confirmed diary entries already distilled the relevant source scenes.",
        "{party_tracker_json}": json.dumps(
            context.get("party_tracker_json", {}), ensure_ascii=True, indent=2
        ),
        "{authoritative_state_packet_json}": json.dumps(
            context.get("party_tracker_json", {}), ensure_ascii=True, indent=2
        ),
        "{module_context_json}": json.dumps(
            {"module": context.get("module_name", "Unknown Module")},
            ensure_ascii=True,
            indent=2,
        ),
        "{location_context_json}": json.dumps(
            context.get("location_context_json", {}), ensure_ascii=True, indent=2
        ),
        "{plot_json}": json.dumps(
            context.get("plot_json", {}), ensure_ascii=True, indent=2
        ),
        "{journal_entries_json}": json.dumps(entries, ensure_ascii=True, indent=2),
        "{memory_events_json}": "[]",
        "{confirmed_diary_entries_json}": json.dumps(
            entries, ensure_ascii=True, indent=2
        ),
        "{campaign_history_blocks}": "",
        "{additional_context_json}": json.dumps({}, ensure_ascii=True, indent=2),
    }

    prompt = template
    for key, value in replacements.items():
        prompt = prompt.replace(key, value)
    return prompt


def _generate_story_text_with_llm(
    entries: List[Dict[str, Any]], context: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate story text with the storyteller prompt and fallback handling."""
    if not AI_CLIENTS_AVAILABLE:
        return {
            "status": "error",
            "message": "AI client factory unavailable",
        }

    prompt = _render_story_prompt(entries, context)
    if not prompt:
        return {
            "status": "error",
            "message": "Story template missing",
        }

    config = get_model_config("summaries", DM_SUMMARIZATION_MODEL)
    client = create_chat_client()

    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "You produce grounded campaign chronicle prose and return only the requested narrative.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=config.get("temperature", 0.7),
            **config.get("extra_body", {}),
        )
        story_text = ""
        if response.choices and response.choices[0].message:
            story_text = str(response.choices[0].message.content or "").strip()
        story_text = _sanitize_story_text(story_text)
        if not story_text:
            return {
                "status": "error",
                "message": "Model returned empty story text",
            }
        return {
            "status": "success",
            "story_text": story_text,
            "generation_mode": "llm",
            "llm_model": config["model"],
        }
    except Exception as llm_error:
        error_info = handle_provider_error(llm_error, context="story_so_far_compiler")
        if error_info.get("should_fallback"):
            try:
                fallback_client = create_chat_client(use_fallback=True)
                fallback_response = fallback_client.chat.completions.create(
                    model=DM_SUMMARIZATION_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You produce grounded campaign chronicle prose and return only the requested narrative.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    temperature=config.get("temperature", 0.7),
                )
                story_text = ""
                if fallback_response.choices and fallback_response.choices[0].message:
                    story_text = str(
                        fallback_response.choices[0].message.content or ""
                    ).strip()
                story_text = _sanitize_story_text(story_text)
                if story_text:
                    return {
                        "status": "success",
                        "story_text": story_text,
                        "generation_mode": "llm_fallback",
                        "llm_model": DM_SUMMARIZATION_MODEL,
                    }
            except Exception as fallback_error:
                warning(
                    f"STORY_SO_FAR: Fallback generation failed: {fallback_error}",
                    category="memory_db",
                )

        warning(
            f"STORY_SO_FAR: LLM generation degraded: {llm_error}",
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(llm_error),
        }


def _build_fallback_story(
    entries: List[Dict[str, Any]], context: Dict[str, Any]
) -> str:
    """Build deterministic fallback story text from confirmed diary summaries."""
    campaign_name = (
        str(context.get("campaign_name", "the campaign")).strip() or "the campaign"
    )
    if not entries:
        return f"No confirmed chapters had yet been recorded for {campaign_name}."

    paragraphs = [
        f"The story so far in {campaign_name} unfolded across these remembered chapters."
    ]
    for entry in entries:
        world = entry.get("world", {})
        checkpoint = (
            entry.get("checkpoint", {})
            if isinstance(entry.get("checkpoint"), dict)
            else {}
        )
        time_text = f"{world.get('month', '')} {world.get('day', 0)}, {world.get('year', 0)} at {world.get('time', '00:00:00')}"
        location = (
            str(checkpoint.get("location", "") or "Unknown Location").strip()
            or "Unknown Location"
        )
        module = str(checkpoint.get("module", "") or "").strip()
        if module:
            location_text = f"{location} ({module})"
        else:
            location_text = location
        summary = str(entry.get("summary", "")).strip()
        if summary:
            paragraphs.append(f"On {time_text} at {location_text}, {summary}")
    return _sanitize_story_text("\n\n".join(paragraphs))


def _ensure_cache_dir() -> None:
    """Ensure story cache directory exists."""
    os.makedirs(_resolve_runtime_path(STORY_CACHE_DIR), exist_ok=True)


def _escape_pdf_text(text: str) -> str:
    """Escape text for a literal PDF text object."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf_pages(story_text: str) -> List[List[str]]:
    """Wrap story text into page-sized line buckets."""
    paragraphs = story_text.split("\n")
    pages: List[List[str]] = []
    current_page: List[str] = []
    max_lines_per_page = max(
        1, int((PAGE_MARGIN_TOP - PAGE_MARGIN_BOTTOM) / LINE_HEIGHT)
    )

    for paragraph in paragraphs:
        clean = paragraph.strip()
        if not clean:
            wrapped_lines = [""]
        else:
            wrapped_lines = textwrap.wrap(clean, width=CHARS_PER_LINE) or [clean]

        for line in wrapped_lines:
            if len(current_page) >= max_lines_per_page:
                pages.append(current_page)
                current_page = []
            current_page.append(line)

        if len(current_page) >= max_lines_per_page:
            pages.append(current_page)
            current_page = []
        current_page.append("")

    if current_page:
        pages.append(current_page)
    if not pages:
        pages.append([""])
    return pages


def _build_pdf_bytes(story_text: str) -> bytes:
    """Build a simple multi-page PDF from story text."""
    pages = _build_pdf_pages(story_text)
    objects: List[bytes] = []

    page_object_numbers: List[int] = []
    content_object_numbers: List[int] = []
    next_object = 4
    for _ in pages:
        page_object_numbers.append(next_object)
        content_object_numbers.append(next_object + 1)
        next_object += 2

    kids_refs = " ".join(f"{page_num} 0 R" for page_num in page_object_numbers)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(
        f"<< /Type /Pages /Kids [{kids_refs}] /Count {len(page_object_numbers)} >>".encode(
            "ascii"
        )
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_index, lines in enumerate(pages):
        content_lines = [
            "BT",
            f"/F1 12 Tf",
            f"{LINE_HEIGHT} TL",
            f"{PAGE_MARGIN_X} {PAGE_MARGIN_TOP} Td",
        ]
        first_line_written = False
        for line in lines:
            if line:
                escaped = _escape_pdf_text(line)
                if not first_line_written:
                    content_lines.append(f"({escaped}) Tj")
                    first_line_written = True
                else:
                    content_lines.append("T*")
                    content_lines.append(f"({escaped}) Tj")
            else:
                if first_line_written:
                    content_lines.append("T*")
        content_lines.append("ET")
        stream_data = "\n".join(content_lines).encode("latin-1", errors="replace")

        page_object = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_object_numbers[page_index]} 0 R >>"
        ).encode("ascii")
        content_object = (
            f"<< /Length {len(stream_data)} >>\nstream\n".encode("ascii")
            + stream_data
            + b"\nendstream"
        )
        objects.append(page_object)
        objects.append(content_object)

    pdf_parts: List[bytes] = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in pdf_parts))
        pdf_parts.append(f"{index} 0 obj\n".encode("ascii"))
        pdf_parts.append(obj)
        pdf_parts.append(b"\nendobj\n")

    xref_offset = sum(len(part) for part in pdf_parts)
    pdf_parts.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf_parts.append(b"0000000000 65535 f \n")
    for object_index in range(1, len(objects) + 1):
        pdf_parts.append(f"{offsets[object_index]:010d} 00000 n \n".encode("ascii"))
    pdf_parts.append(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return b"".join(pdf_parts)


def build_confirmed_story_text(db_path: str = DEFAULT_MEMORY_DB_PATH) -> Dict[str, Any]:
    """Build confirmed-only story text, using LLM when available."""
    if not init_memory_db(db_path):
        return {
            "status": "error",
            "message": "Memory DB initialization failed",
            "db_path": db_path,
        }

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)
        entries = _load_confirmed_entries(conn)
        if not entries:
            return {
                "status": "error",
                "message": "No confirmed diary entries available",
                "db_path": db_path,
                "confirmed_count": 0,
            }

        fingerprint = _compute_confirmed_fingerprint(entries)
        context = _get_current_campaign_context()
        llm_result = _generate_story_text_with_llm(entries, context)

        if llm_result.get("status") == "success":
            story_text = _sanitize_story_text(
                str(llm_result.get("story_text", "")).strip()
            )
            generation_mode = str(llm_result.get("generation_mode", "llm"))
            llm_model = llm_result.get("llm_model")
            if not story_text:
                story_text = _build_fallback_story(entries, context)
                generation_mode = "fallback"
                llm_model = None
        else:
            story_text = _build_fallback_story(entries, context)
            generation_mode = "fallback"
            llm_model = None

        if generation_mode == "fallback":
            warning(
                "STORY_SO_FAR: Story generation used deterministic fallback output; verify interpreter and AI dependencies if LLM output was expected.",
                category="memory_db",
            )

        return {
            "status": "success",
            "db_path": db_path,
            "story_text": story_text,
            "confirmed_count": len(entries),
            "fingerprint": fingerprint,
            "generation_mode": generation_mode,
            "llm_model": llm_model,
        }
    except Exception as compile_error:
        error(
            f"STORY_SO_FAR: Build failed: {compile_error}",
            exception=compile_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(compile_error),
            "db_path": db_path,
        }
    finally:
        if conn is not None:
            conn.close()


def render_story_pdf(story_text: str, output_path: str) -> Dict[str, Any]:
    """Render story text to a simple PDF file."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pdf_bytes = _build_pdf_bytes(story_text or "")
        with open(output_path, "wb") as handle:
            handle.write(pdf_bytes)
        return {
            "status": "success",
            "output_path": output_path,
            "bytes": len(pdf_bytes),
            "story_chars": len(story_text or ""),
        }
    except Exception as render_error:
        error(
            f"STORY_SO_FAR: PDF render failed: {render_error}",
            exception=render_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(render_error),
            "output_path": output_path,
            "bytes": 0,
        }


def get_or_build_story_pdf(db_path: str = DEFAULT_MEMORY_DB_PATH) -> Dict[str, Any]:
    """Reuse cached story PDF when fingerprint matches, else rebuild it."""
    story_result = build_confirmed_story_text(db_path)
    if story_result.get("status") != "success":
        return story_result

    fingerprint = str(story_result.get("fingerprint", "")).strip()
    if not fingerprint:
        return {
            "status": "error",
            "message": "Missing confirmed fingerprint",
            "db_path": db_path,
        }

    _ensure_cache_dir()
    cache_path = os.path.join(
        _resolve_runtime_path(STORY_CACHE_DIR), f"story_so_far_{fingerprint}.pdf"
    )
    conn: Optional[sqlite3.Connection] = None

    try:
        conn = _connect(db_path)
        cache_row = conn.execute(
            """
            SELECT pdf_path, confirmed_count
            FROM story_so_far_cache
            WHERE confirmed_fingerprint = ?
            LIMIT 1
            """,
            (fingerprint,),
        ).fetchone()

        if cache_row is not None:
            cached_path = str(cache_row["pdf_path"] or "")
            if cached_path and os.path.exists(cached_path):
                return {
                    "status": "success",
                    "cache_hit": True,
                    "pdf_path": cached_path,
                    "download_name": PDF_DOWNLOAD_NAME,
                    "confirmed_count": cache_row["confirmed_count"],
                    "fingerprint": fingerprint,
                    "generation_mode": story_result.get("generation_mode", "fallback"),
                }

        render_result = render_story_pdf(
            str(story_result.get("story_text", "")), cache_path
        )
        if render_result.get("status") != "success":
            return render_result

        with conn:
            conn.execute(
                """
                INSERT INTO story_so_far_cache (
                    confirmed_fingerprint,
                    pdf_path,
                    created_at,
                    confirmed_count
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(confirmed_fingerprint) DO UPDATE SET
                    pdf_path = excluded.pdf_path,
                    created_at = excluded.created_at,
                    confirmed_count = excluded.confirmed_count
                """,
                (
                    fingerprint,
                    cache_path,
                    _utc_now_iso(),
                    int(story_result.get("confirmed_count", 0)),
                ),
            )

        return {
            "status": "success",
            "cache_hit": False,
            "pdf_path": cache_path,
            "download_name": PDF_DOWNLOAD_NAME,
            "confirmed_count": story_result.get("confirmed_count", 0),
            "fingerprint": fingerprint,
            "generation_mode": story_result.get("generation_mode", "fallback"),
            "llm_model": story_result.get("llm_model"),
        }
    except Exception as cache_error:
        error(
            f"STORY_SO_FAR: Cache/build failed: {cache_error}",
            exception=cache_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "message": str(cache_error),
            "db_path": db_path,
        }
    finally:
        if conn is not None:
            conn.close()


__all__ = [
    "build_confirmed_story_text",
    "render_story_pdf",
    "get_or_build_story_pdf",
]
