# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Memory Ingest - Journal and summary ingestion helpers.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from utils.enhanced_logger import error, info, warning
from utils.file_operations import safe_read_json

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _build_entry_checksum(entry: Dict[str, Any], source_type: str) -> str:
    """Build deterministic checksum for one source entry."""
    checksum_payload = {
        "source_type": source_type,
        "entry_ts": str(entry.get("entry_ts", "")),
        "title": str(entry.get("title", "")),
        "content": str(entry.get("content", "")),
        "source_ref": str(entry.get("source_ref", "")),
    }
    encoded = json.dumps(checksum_payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _resolve_entry_timestamp(entry: Dict[str, Any]) -> str:
    """Resolve entry timestamp with precedence: entry_ts > timestamp > source_ts > now."""
    for key in ("entry_ts", "timestamp", "source_ts", "created_at"):
        value = entry.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return _utc_now_iso()


def ingest_journal_entry(
    entry: Dict[str, Any],
    db_path: str = DEFAULT_MEMORY_DB_PATH,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """Idempotently insert one journal entry by (source_type, checksum).
    
    Args:
        entry: The journal entry to ingest
        db_path: Database path (used only if conn is None)
        conn: Optional shared connection for batch operations
    """
    source_type = str(entry.get("source_type", "journal")).strip() or "journal"
    content = str(entry.get("content", "")).strip()
    if not content:
        return {
            "status": "error",
            "message": "Journal entry content is required",
        }

    checksum = str(entry.get("checksum", "")).strip() or _build_entry_checksum(entry, source_type)
    payload = {
        "entry_ts": _resolve_entry_timestamp(entry),
        "title": str(entry.get("title", "")).strip() or None,
        "content": content,
        "source_type": source_type,
        "source_ref": str(entry.get("source_ref", "")).strip() or None,
        "checksum": checksum,
        "metadata_json": entry.get("metadata_json") if isinstance(entry.get("metadata_json"), str) else json.dumps(entry.get("metadata", {})),
        "created_at": _resolve_entry_timestamp(entry),
    }

    should_close_conn = conn is None
    try:
        if conn is None:
            conn = _connect(db_path)
        
        # Use transaction context for standalone connections
        if should_close_conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO journal_entries (
                        entry_ts, title, content, source_type, source_ref,
                        checksum, metadata_json, created_at
                    ) VALUES (
                        :entry_ts, :title, :content, :source_type, :source_ref,
                        :checksum, :metadata_json, :created_at
                    )
                    ON CONFLICT(source_type, checksum) DO NOTHING
                    """,
                    payload,
                )

                row = conn.execute(
                    """
                    SELECT entry_id
                    FROM journal_entries
                    WHERE source_type = :source_type
                      AND checksum = :checksum
                    """,
                    {"source_type": source_type, "checksum": checksum},
                ).fetchone()

                entry_id = int(row[0]) if row else 0
                return {
                    "status": "success",
                    "entry_id": entry_id,
                    "checksum": checksum,
                    "source_type": source_type,
                }
        else:
            # Shared connection: caller controls transaction
            cursor = conn.execute(
                """
                INSERT INTO journal_entries (
                    entry_ts, title, content, source_type, source_ref,
                    checksum, metadata_json, created_at
                ) VALUES (
                    :entry_ts, :title, :content, :source_type, :source_ref,
                    :checksum, :metadata_json, :created_at
                )
                ON CONFLICT(source_type, checksum) DO NOTHING
                """,
                payload,
            )

            row = conn.execute(
                """
                SELECT entry_id
                FROM journal_entries
                WHERE source_type = :source_type
                  AND checksum = :checksum
                """,
                {"source_type": source_type, "checksum": checksum},
            ).fetchone()

            entry_id = int(row[0]) if row else 0
            return {
                "status": "success",
                "entry_id": entry_id,
                "checksum": checksum,
                "source_type": source_type,
            }
    except Exception as ingest_error:
        error(
            f"MEMORY_INGEST: Failed to ingest journal entry: {ingest_error}",
            exception=ingest_error,
            category="memory_ingest",
        )
        return {
            "status": "error",
            "message": str(ingest_error),
            "checksum": checksum,
            "source_type": source_type,
        }
    finally:
        if should_close_conn and conn is not None:
            conn.close()


def _to_journal_entries(source_data: Any) -> List[Dict[str, Any]]:
    """Normalize journal file into a list of entry dictionaries."""
    if isinstance(source_data, list):
        return [entry for entry in source_data if isinstance(entry, dict)]
    if isinstance(source_data, dict):
        entries = source_data.get("journal_entries") or source_data.get("entries") or []
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    return []


def ingest_journal_entries_batch(
    entries: List[Dict[str, Any]],
    db_path: str = DEFAULT_MEMORY_DB_PATH,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """Ingest multiple journal entries using shared connection with batched transactions.
    
    Args:
        entries: List of journal entries to ingest
        db_path: Database path
        batch_size: Number of entries per transaction batch
    
    Returns:
        Dict with status, counts, and error details
    """
    if not entries:
        return {
            "status": "success",
            "total": 0,
            "ingested": 0,
            "skipped": 0,
            "errors": 0,
        }

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)
        ingested = 0
        skipped = 0
        errors = 0
        error_items: List[Dict[str, Any]] = []

        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            try:
                with conn:
                    for idx, entry in enumerate(batch):
                        result = _ingest_journal_entry_internal(
                            entry, db_path=db_path, conn=conn
                        )
                        if result.get("status") == "success":
                            # rowcount == 1 means new insert, 0 means conflict/duplicate
                            if result.get("inserted", False):
                                ingested += 1
                            else:
                                skipped += 1
                        else:
                            errors += 1
                            error_items.append({
                                "batch_index": i + idx,
                                "message": result.get("message", "unknown"),
                            })
            except Exception as batch_error:
                error(
                    f"MEMORY_INGEST: Batch {i//batch_size} failed: {batch_error}",
                    exception=batch_error,
                    category="memory_ingest",
                )
                errors += len(batch)
                for idx in range(len(batch)):
                    error_items.append({
                        "batch_index": i + idx,
                        "message": f"batch failure: {batch_error}",
                    })

        return {
            "status": "success" if errors == 0 else "partial",
            "total": len(entries),
            "ingested": ingested,
            "skipped": skipped,
            "errors": errors,
            "error_items": error_items[:10],
        }
    except Exception as conn_error:
        error(
            f"MEMORY_INGEST: Batch ingest failed: {conn_error}",
            exception=conn_error,
            category="memory_ingest",
        )
        return {
            "status": "error",
            "message": str(conn_error),
            "total": len(entries),
            "ingested": 0,
            "skipped": 0,
            "errors": len(entries),
        }
    finally:
        if conn is not None:
            conn.close()


def _ingest_journal_entry_internal(
    entry: Dict[str, Any],
    db_path: str = DEFAULT_MEMORY_DB_PATH,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """Internal variant that tracks whether row was actually inserted vs duplicate.
    
    Returns result with 'inserted' boolean to distinguish new rows from conflicts.
    """
    source_type = str(entry.get("source_type", "journal")).strip() or "journal"
    content = str(entry.get("content", "")).strip()
    if not content:
        return {
            "status": "error",
            "message": "Journal entry content is required",
        }

    checksum = str(entry.get("checksum", "")).strip() or _build_entry_checksum(entry, source_type)
    payload = {
        "entry_ts": _resolve_entry_timestamp(entry),
        "title": str(entry.get("title", "")).strip() or None,
        "content": content,
        "source_type": source_type,
        "source_ref": str(entry.get("source_ref", "")).strip() or None,
        "checksum": checksum,
        "metadata_json": entry.get("metadata_json") if isinstance(entry.get("metadata_json"), str) else json.dumps(entry.get("metadata", {})),
        "created_at": _resolve_entry_timestamp(entry),
    }

    try:
        cursor = conn.execute(
            """
            INSERT INTO journal_entries (
                entry_ts, title, content, source_type, source_ref,
                checksum, metadata_json, created_at
            ) VALUES (
                :entry_ts, :title, :content, :source_type, :source_ref,
                :checksum, :metadata_json, :created_at
            )
            ON CONFLICT(source_type, checksum) DO NOTHING
            """,
            payload,
        )

        # rowcount == 1 means new insert, 0 means conflict/duplicate
        was_inserted = cursor.rowcount == 1

        row = conn.execute(
            """
            SELECT entry_id
            FROM journal_entries
            WHERE source_type = :source_type
              AND checksum = :checksum
            """,
            {"source_type": source_type, "checksum": checksum},
        ).fetchone()

        entry_id = int(row[0]) if row else 0
        return {
            "status": "success",
            "entry_id": entry_id,
            "checksum": checksum,
            "source_type": source_type,
            "inserted": was_inserted,
        }
    except Exception as ingest_error:
        return {
            "status": "error",
            "message": str(ingest_error),
            "checksum": checksum,
            "source_type": source_type,
        }


def ingest_journal_file(
    journal_path: str = "journal.json",
    db_path: str = DEFAULT_MEMORY_DB_PATH,
    min_link_confidence: float = 0.8,
) -> Dict[str, Any]:
    """Ingest full journal file with malformed entry tolerance.

    Deferred-link behavior:
    - If entry-level `entity_link_confidence` is below threshold, store entry but
      mark metadata for deferred linking.
    """
    source_data = safe_read_json(journal_path)
    entries = _to_journal_entries(source_data)

    if not entries:
        warning(f"MEMORY_INGEST: No journal entries found in {journal_path}", category="memory_ingest")
        return {
            "status": "success",
            "journal_path": journal_path,
            "total": 0,
            "ingested": 0,
            "errors": 0,
            "deferred_linking": 0,
        }

    ingested = 0
    errors = 0
    deferred_linking = 0
    error_items: List[Dict[str, Any]] = []

    for index, raw_entry in enumerate(entries):
        try:
            metadata = raw_entry.get("metadata", {}) if isinstance(raw_entry.get("metadata"), dict) else {}
            link_confidence = float(raw_entry.get("entity_link_confidence", metadata.get("entity_link_confidence", 1.0)))

            entry_payload = {
                "entry_ts": raw_entry.get("entry_ts") or raw_entry.get("timestamp") or _utc_now_iso(),
                "title": raw_entry.get("title") or raw_entry.get("location") or "Journal Entry",
                "content": raw_entry.get("content") or raw_entry.get("entry") or raw_entry.get("summary") or "",
                "source_type": "journal",
                "source_ref": f"{journal_path}:{index}",
                "metadata": metadata,
            }

            if link_confidence < min_link_confidence:
                deferred_linking += 1
                entry_payload["metadata"] = {
                    **metadata,
                    "deferred_linking": True,
                    "entity_link_confidence": link_confidence,
                }

            result = ingest_journal_entry(entry_payload, db_path=db_path)
            if result.get("status") == "success":
                ingested += 1
            else:
                errors += 1
                error_items.append({"index": index, "message": result.get("message", "unknown")})
        except Exception as entry_error:
            errors += 1
            error_items.append({"index": index, "message": str(entry_error)})
            error(
                f"MEMORY_INGEST: Malformed journal entry at index {index}: {entry_error}",
                exception=entry_error,
                category="memory_ingest",
            )
            continue

    info(
        f"MEMORY_INGEST: journal import complete total={len(entries)} ingested={ingested} errors={errors}",
        category="memory_ingest",
    )

    return {
        "status": "success",
        "journal_path": journal_path,
        "total": len(entries),
        "ingested": ingested,
        "errors": errors,
        "deferred_linking": deferred_linking,
        "error_items": error_items,
    }


def _normalize_name(value: str) -> str:
    """Normalize a character/entity name for IDs and matching."""
    try:
        from updates.update_character_info import normalize_character_name

        return normalize_character_name(value)
    except Exception:
        lowered = str(value).strip().lower()
        return re.sub(r"[^a-z0-9_]+", "_", lowered).strip("_")


def _extract_party_entities() -> Dict[str, Dict[str, str]]:
    """Load known party entities from party tracker."""
    tracker = safe_read_json("party_tracker.json") or {}
    entity_map: Dict[str, Dict[str, str]] = {}

    for member_name in tracker.get("partyMembers", []) or []:
        normalized = _normalize_name(str(member_name))
        if normalized:
            entity_map[normalized] = {
                "entity_id": normalized,
                "display_name": str(member_name),
                "role": "player",
            }

    npc_entries = tracker.get("partyNPCs", []) or []
    for npc_entry in npc_entries:
        npc_name = ""
        if isinstance(npc_entry, dict):
            npc_name = str(npc_entry.get("name", "")).strip()
        else:
            npc_name = str(npc_entry).strip()

        normalized = _normalize_name(npc_name)
        if normalized:
            entity_map[normalized] = {
                "entity_id": normalized,
                "display_name": npc_name,
                "role": "npc_companion",
            }

    return entity_map


def _upsert_entity(conn: sqlite3.Connection, entity_id: str, display_name: str, role: str) -> None:
    """Create/update one entity and its active role."""
    now_ts = _utc_now_iso()
    conn.execute(
        """
        INSERT INTO entities (entity_id, display_name, entity_kind, is_retired, created_at, updated_at, metadata_json)
        VALUES (?, ?, 'character', 0, ?, ?, ?)
        ON CONFLICT(entity_id) DO UPDATE SET
            display_name = excluded.display_name,
            updated_at = excluded.updated_at
        """,
        (entity_id, display_name, now_ts, now_ts, json.dumps({"backfill": True})),
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO entity_aliases (entity_id, alias_name, alias_type, source, created_at)
        VALUES (?, ?, 'name', 'backfill', ?)
        """,
        (entity_id, display_name, now_ts),
    )

    conn.execute(
        """
        UPDATE entity_roles
        SET end_ts = ?
        WHERE entity_id = ? AND end_ts IS NULL AND role != ?
        """,
        (now_ts, entity_id, role),
    )

    active_role = conn.execute(
        "SELECT role_id FROM entity_roles WHERE entity_id = ? AND role = ? AND end_ts IS NULL",
        (entity_id, role),
    ).fetchone()
    if not active_role:
        conn.execute(
            """
            INSERT INTO entity_roles (entity_id, role, start_ts, end_ts, source, reason)
            VALUES (?, ?, ?, NULL, 'backfill', 'current party state')
            """,
            (entity_id, role, now_ts),
        )


def _extract_linked_entity_ids(text: str, entity_map: Dict[str, Dict[str, str]]) -> List[str]:
    """Find known entity names in text using case-insensitive whole-term matching."""
    content = str(text or "")
    if not content:
        return []

    lowered = content.lower()
    matches: List[str] = []
    for entity_id, details in entity_map.items():
        display_name = str(details.get("display_name", "")).strip()
        if not display_name:
            continue

        pattern = r"\b" + re.escape(display_name.lower()) + r"\b"
        if re.search(pattern, lowered):
            matches.append(entity_id)

    return matches


def _create_event_for_entry(
    conn: sqlite3.Connection,
    entry_id: int,
    entry_ts: str,
    source_type: str,
    summary: str,
    source_ref: str,
    checksum: str,
    linked_entities: List[str],
    active_entity_ids: List[str],
) -> str:
    """Create one memory event from one ingested source entry."""
    event_fingerprint = f"{source_type}:{source_ref}:{checksum}"
    event_id = "evt_" + hashlib.sha256(event_fingerprint.encode("utf-8")).hexdigest()[:24]

    if source_type == "journal":
        event_type = "milestone"
        persistence_class = "campaign_major"
        decay_profile = "slow"
        importance = 70
        modality_tags = ["episodic", "plot_state"]
    elif source_type == "combat_history":
        event_type = "combat"
        persistence_class = "procedural"
        decay_profile = "medium"
        importance = 55
        modality_tags = ["episodic", "procedural"]
    else:
        event_type = "dialogue"
        persistence_class = "ambient"
        decay_profile = "fast"
        importance = 40
        modality_tags = ["episodic", "social"]

    priority_active_pc = 1 if any(entity_id in active_entity_ids for entity_id in linked_entities) else 0

    conn.execute(
        """
        INSERT INTO memory_events (
            event_id, entry_id, event_ts, event_type, summary, detail_json,
            importance, persistence_class, decay_profile, modality_tags_json,
            reinforcement_count, last_reinforced_ts, priority_active_pc,
            pinned, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, 0, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            summary = excluded.summary,
            importance = excluded.importance,
            persistence_class = excluded.persistence_class,
            decay_profile = excluded.decay_profile,
            modality_tags_json = excluded.modality_tags_json,
            priority_active_pc = excluded.priority_active_pc
        """,
        (
            event_id,
            entry_id,
            entry_ts,
            event_type,
            summary,
            json.dumps({"source_ref": source_ref, "source_type": source_type}),
            importance,
            persistence_class,
            decay_profile,
            json.dumps(modality_tags),
            priority_active_pc,
            _utc_now_iso(),
        ),
    )

    return event_id


def _link_event_entities(
    conn: sqlite3.Connection,
    event_id: str,
    linked_entities: List[str],
    fallback_entity_id: Optional[str],
) -> int:
    """Link entities to an event, with witness fallback when no names matched."""
    linked_count = 0
    if linked_entities:
        for entity_id in linked_entities:
            conn.execute(
                """
                INSERT OR IGNORE INTO memory_links (event_id, entity_id, link_role, link_salience, metadata_json)
                VALUES (?, ?, 'actor', 0.7, ?)
                """,
                (event_id, entity_id, json.dumps({"backfill": True, "inferred": False})),
            )
            linked_count += 1
        return linked_count

    if fallback_entity_id:
        conn.execute(
            """
            INSERT OR IGNORE INTO memory_links (event_id, entity_id, link_role, link_salience, metadata_json)
            VALUES (?, ?, 'witness', 0.2, ?)
            """,
            (event_id, fallback_entity_id, json.dumps({"backfill": True, "inferred": True, "deferred_linking": True})),
        )
        return 1

    return 0


def _build_history_entries(
    history_data: Any,
    source_path: str,
    source_type: str,
    include_system: bool = False,
) -> List[Dict[str, Any]]:
    """Normalize conversation/combat history arrays into ingest entries."""
    if not isinstance(history_data, list):
        return []

    entries: List[Dict[str, Any]] = []
    for index, item in enumerate(history_data):
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        # Skip bulky system prompt scaffolding by default for backfill signal quality.
        if role == "system" and not include_system:
            continue

        entries.append(
            {
                "entry_ts": _utc_now_iso(),
                "title": f"{source_type}:{role}",
                "content": content,
                "source_type": source_type,
                "source_ref": f"{source_path}:{index}",
                "metadata": {"role": role},
            }
        )

    return entries


def backfill_memory_db_from_histories(
    db_path: str = DEFAULT_MEMORY_DB_PATH,
    journal_path: str = "journal.json",
    conversation_path: str = "modules/conversation_history/conversation_history.json",
    combat_history_path: str = "modules/conversation_history/combat_conversation_history.json",
    include_system_messages: bool = False,
    sources: Optional[List[str]] = None,
    batch_size: int = 50,
) -> Dict[str, Any]:
    """Backfill memory DB from current journal and conversation histories using shared connection and batched transactions.
    
    Args:
        db_path: Path to the memory database
        journal_path: Path to journal.json
        conversation_path: Path to conversation history
        combat_history_path: Path to combat conversation history
        include_system_messages: Whether to include system messages in history ingestion
        sources: List of sources to ingest ("journal", "conversation", "combat")
        batch_size: Number of entries per transaction batch
    """
    from core.memory.memory_db import init_memory_db

    init_ok = init_memory_db(db_path)
    if not init_ok:
        return {
            "status": "error",
            "message": "Memory DB init failed",
            "db_path": db_path,
        }

    selected_sources: Set[str]
    if sources:
        selected_sources = {str(item).strip().lower() for item in sources if str(item).strip()}
    else:
        selected_sources = {"journal", "conversation", "combat"}

    entity_map = _extract_party_entities()
    active_entity_ids = [entity_id for entity_id, details in entity_map.items() if details.get("role") == "player"]
    fallback_entity_id = active_entity_ids[0] if active_entity_ids else None

    conn: Optional[sqlite3.Connection] = None
    created_events = 0
    created_links = 0
    source_totals = {
        "journal": 0,
        "conversation_history": 0,
        "combat_history": 0,
    }
    source_errors = {
        "journal": 0,
        "conversation_history": 0,
        "combat_history": 0,
    }

    try:
        conn = _connect(db_path)
        
        # Upsert all entities in initial transaction
        with conn:
            for details in entity_map.values():
                _upsert_entity(conn, details["entity_id"], details["display_name"], details["role"])

        # Source 1: journal
        if "journal" in selected_sources:
            journal_data = safe_read_json(journal_path)
            journal_entries = _to_journal_entries(journal_data)
            
            for i in range(0, len(journal_entries), batch_size):
                batch = journal_entries[i:i + batch_size]
                try:
                    with conn:
                        for index, raw_entry in enumerate(batch):
                            try:
                                entry_payload = {
                                    "entry_ts": _resolve_entry_timestamp(raw_entry),
                                    "title": raw_entry.get("title") or raw_entry.get("location") or "Journal Entry",
                                    "content": raw_entry.get("content") or raw_entry.get("entry") or raw_entry.get("summary") or "",
                                    "source_type": "journal",
                                    "source_ref": f"{journal_path}:{i + index}",
                                    "metadata": raw_entry.get("metadata", {}),
                                }
                                ingest_result = ingest_journal_entry(entry_payload, db_path=db_path, conn=conn)
                                if ingest_result.get("status") != "success":
                                    source_errors["journal"] += 1
                                    continue

                                source_totals["journal"] += 1
                                linked_entities = _extract_linked_entity_ids(entry_payload["content"], entity_map)

                                event_id = _create_event_for_entry(
                                    conn,
                                    entry_id=int(ingest_result["entry_id"]),
                                    entry_ts=entry_payload["entry_ts"],
                                    source_type="journal",
                                    summary=entry_payload["content"],
                                    source_ref=entry_payload["source_ref"],
                                    checksum=str(ingest_result.get("checksum", "")),
                                    linked_entities=linked_entities,
                                    active_entity_ids=active_entity_ids,
                                )
                                created_events += 1
                                created_links += _link_event_entities(conn, event_id, linked_entities, fallback_entity_id)
                            except Exception as entry_error:
                                source_errors["journal"] += 1
                                error(f"MEMORY_INGEST: Journal backfill failure at index {i + index}: {entry_error}", category="memory_ingest")
                except Exception as batch_error:
                    error(f"MEMORY_INGEST: Journal batch failed: {batch_error}", category="memory_ingest")
                    for _ in batch:
                        source_errors["journal"] += 1

        # Source 2 and 3: conversation histories
        source_definitions = [
            (conversation_path, "conversation_history", "conversation_history"),
            (combat_history_path, "combat_history", "conversation_history"),
        ]
        for source_path, source_type, history_key in source_definitions:
            if source_type == "conversation_history" and "conversation" not in selected_sources:
                continue
            if source_type == "combat_history" and "combat" not in selected_sources:
                continue

            history_payload = safe_read_json(source_path)
            history_items = []
            if isinstance(history_payload, dict):
                history_items = history_payload.get(history_key, [])
            elif isinstance(history_payload, list):
                history_items = history_payload

            entries = _build_history_entries(
                history_items,
                source_path,
                source_type,
                include_system=include_system_messages,
            )
            
            for i in range(0, len(entries), batch_size):
                batch = entries[i:i + batch_size]
                try:
                    with conn:
                        for entry in batch:
                            try:
                                ingest_result = ingest_journal_entry(entry, db_path=db_path, conn=conn)
                                if ingest_result.get("status") != "success":
                                    source_errors[source_type] += 1
                                    continue

                                source_totals[source_type] += 1
                                linked_entities = _extract_linked_entity_ids(entry["content"], entity_map)
                                event_id = _create_event_for_entry(
                                    conn,
                                    entry_id=int(ingest_result["entry_id"]),
                                    entry_ts=entry["entry_ts"],
                                    source_type=source_type,
                                    summary=entry["content"],
                                    source_ref=entry["source_ref"],
                                    checksum=str(ingest_result.get("checksum", "")),
                                    linked_entities=linked_entities,
                                    active_entity_ids=active_entity_ids,
                                )
                                created_events += 1
                                created_links += _link_event_entities(conn, event_id, linked_entities, fallback_entity_id)
                            except Exception as entry_error:
                                source_errors[source_type] += 1
                                error(
                                    f"MEMORY_INGEST: {source_type} backfill failure at {entry.get('source_ref', 'unknown')}: {entry_error}",
                                    category="memory_ingest",
                                )
                except Exception as batch_error:
                    error(f"MEMORY_INGEST: {source_type} batch failed: {batch_error}", category="memory_ingest")
                    for _ in batch:
                        source_errors[source_type] += 1

        result = {
            "status": "success",
            "db_path": db_path,
            "include_system_messages": include_system_messages,
            "selected_sources": sorted(selected_sources),
            "sources_ingested": source_totals,
            "source_errors": source_errors,
            "entity_count": len(entity_map),
            "events_created": created_events,
            "links_created": created_links,
        }
        info(
            f"MEMORY_INGEST: Backfill complete events={created_events} links={created_links}",
            category="memory_ingest",
        )
        return result
    except Exception as backfill_error:
        error(
            f"MEMORY_INGEST: Backfill failed: {backfill_error}",
            exception=backfill_error,
            category="memory_ingest",
        )
        return {
            "status": "error",
            "message": str(backfill_error),
            "db_path": db_path,
        }
    finally:
        if conn is not None:
            conn.close()
