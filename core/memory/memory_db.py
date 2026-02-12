# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Memory DB - SQLite schema and migrations.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Provides idempotent initialization and migration helpers for the
long-term memory foundation.
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from utils.enhanced_logger import debug, error, info, warning


DEFAULT_MEMORY_DB_PATH = "data/memory.db"


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_parent_dir(db_path: str) -> None:
    """Ensure parent directory exists for DB path."""
    parent_dir = os.path.dirname(db_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def _connect(db_path: str) -> sqlite3.Connection:
    """Create SQLite connection with sane defaults."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _create_schema_migrations_table(conn: sqlite3.Connection) -> None:
    """Create migration bookkeeping table."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def _apply_migration(conn: sqlite3.Connection, migration_id: str, sql: str) -> bool:
    """Apply one migration if it has not already been applied."""
    row = conn.execute(
        "SELECT migration_id FROM schema_migrations WHERE migration_id = ?",
        (migration_id,),
    ).fetchone()
    if row:
        return False

    conn.executescript(sql)
    conn.execute(
        "INSERT INTO schema_migrations (migration_id, applied_at) VALUES (?, ?)",
        (migration_id, _utc_now_iso()),
    )
    return True


MIGRATION_001_INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    entity_kind TEXT NOT NULL,
    is_retired INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_entities_kind_name
    ON entities(entity_kind, display_name);

CREATE TABLE IF NOT EXISTS entity_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    alias_name TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'name',
    source TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL,
    UNIQUE(entity_id, alias_name),
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entity_alias_name
    ON entity_aliases(alias_name);

CREATE TABLE IF NOT EXISTS entity_roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    role TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT,
    source TEXT NOT NULL DEFAULT 'system',
    reason TEXT,
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_roles_active
    ON entity_roles(entity_id, end_ts);

CREATE INDEX IF NOT EXISTS idx_roles_timeline
    ON entity_roles(entity_id, start_ts DESC);

CREATE TABLE IF NOT EXISTS journal_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_ts TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    checksum TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(source_type, checksum)
);

CREATE INDEX IF NOT EXISTS idx_journal_entry_ts
    ON journal_entries(entry_ts DESC);

CREATE TABLE IF NOT EXISTS memory_events (
    event_id TEXT PRIMARY KEY,
    entry_id INTEGER,
    event_ts TEXT NOT NULL,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail_json TEXT,
    importance INTEGER NOT NULL DEFAULT 50,
    persistence_class TEXT NOT NULL DEFAULT 'ambient',
    decay_profile TEXT NOT NULL DEFAULT 'medium',
    modality_tags_json TEXT NOT NULL DEFAULT '[]',
    reinforcement_count INTEGER NOT NULL DEFAULT 0,
    last_reinforced_ts TEXT,
    priority_active_pc INTEGER NOT NULL DEFAULT 0,
    pinned INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(entry_id) REFERENCES journal_entries(entry_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_events_ts
    ON memory_events(event_ts DESC);

CREATE INDEX IF NOT EXISTS idx_events_priority
    ON memory_events(pinned DESC, priority_active_pc DESC, importance DESC, event_ts DESC);

CREATE INDEX IF NOT EXISTS idx_events_persistence
    ON memory_events(persistence_class, decay_profile, event_ts DESC);

CREATE TABLE IF NOT EXISTS memory_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    link_role TEXT NOT NULL,
    link_salience REAL NOT NULL DEFAULT 0.5,
    metadata_json TEXT,
    UNIQUE(event_id, entity_id, link_role),
    FOREIGN KEY(event_id) REFERENCES memory_events(event_id) ON DELETE CASCADE,
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_links_entity
    ON memory_links(entity_id, link_role);

CREATE INDEX IF NOT EXISTS idx_links_event
    ON memory_links(event_id);

CREATE TABLE IF NOT EXISTS companion_memory_state (
    entity_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS retrieval_snippets (
    snippet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT,
    event_id TEXT,
    scene_type TEXT NOT NULL,
    snippet_text TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES memory_events(event_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_snippets_lookup
    ON retrieval_snippets(entity_id, scene_type, score DESC);
"""


MIGRATION_002_READINESS_TABLES = """
CREATE TABLE IF NOT EXISTS memory_policy_profiles (
    policy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    scope TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system'
);

CREATE TABLE IF NOT EXISTS memory_policy_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_key TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    effective_from_ts TEXT NOT NULL,
    effective_to_ts TEXT,
    FOREIGN KEY(policy_id) REFERENCES memory_policy_profiles(policy_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policy_assignments_context
    ON memory_policy_assignments(context_key, effective_from_ts DESC);

CREATE TABLE IF NOT EXISTS retrieval_audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_ts TEXT NOT NULL,
    request_type TEXT NOT NULL,
    scene_type TEXT,
    entity_scope_json TEXT NOT NULL,
    policy_id TEXT,
    candidate_count INTEGER NOT NULL,
    result_count INTEGER NOT NULL,
    result_event_ids_json TEXT NOT NULL,
    score_breakdown_json TEXT NOT NULL,
    token_estimate INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    mode TEXT NOT NULL DEFAULT 'live'
);

CREATE INDEX IF NOT EXISTS idx_retrieval_audit_ts
    ON retrieval_audit_log(request_ts DESC);

CREATE INDEX IF NOT EXISTS idx_retrieval_audit_type
    ON retrieval_audit_log(request_type, request_ts DESC);

CREATE TABLE IF NOT EXISTS controller_change_log (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_key TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT NOT NULL,
    reason TEXT,
    rollback_of_change_id INTEGER
);

CREATE TABLE IF NOT EXISTS memory_event_provenance (
    event_id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    source_ref TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    verification_state TEXT NOT NULL DEFAULT 'unverified',
    last_verified_ts TEXT,
    FOREIGN KEY(event_id) REFERENCES memory_events(event_id) ON DELETE CASCADE
);
"""


def run_memory_migrations(db_path: str = DEFAULT_MEMORY_DB_PATH) -> Dict[str, Any]:
    """Run all pending memory DB migrations and return summary."""
    _ensure_parent_dir(db_path)

    migrations = [
        ("001_initial_schema", MIGRATION_001_INITIAL_SCHEMA),
        ("002_readiness_tables", MIGRATION_002_READINESS_TABLES),
    ]

    applied_count = 0
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)
        _create_schema_migrations_table(conn)

        with conn:
            for migration_id, migration_sql in migrations:
                if _apply_migration(conn, migration_id, migration_sql):
                    applied_count += 1
                    info(f"MEMORY_DB: Applied migration {migration_id}", category="memory_db")

        debug(
            f"MEMORY_DB: Migration pass complete ({applied_count} applied)",
            category="memory_db",
        )
        return {
            "status": "success",
            "db_path": db_path,
            "migrations_applied": applied_count,
        }
    except Exception as migration_error:
        error(
            f"MEMORY_DB: Migration failure for {db_path}: {migration_error}",
            exception=migration_error,
            category="memory_db",
        )
        return {
            "status": "error",
            "db_path": db_path,
            "message": str(migration_error),
            "migrations_applied": applied_count,
        }
    finally:
        if conn is not None:
            conn.close()


def init_memory_db(db_path: str = DEFAULT_MEMORY_DB_PATH) -> bool:
    """Initialize memory DB and run migrations."""
    result = run_memory_migrations(db_path)
    if result.get("status") == "success":
        return True

    warning(
        f"MEMORY_DB: Initialization failed, continuing without DB ({result.get('message', 'unknown error')})",
        category="memory_db",
    )
    return False


def create_memory_event(db_path: str, event: Dict[str, Any]) -> str:
    """Insert or update a memory event and return event_id."""
    required_fields = ["event_id", "event_ts", "event_type", "summary"]
    for field_name in required_fields:
        if not event.get(field_name):
            raise ValueError(f"Missing required event field: {field_name}")

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)
        with conn:
            conn.execute(
                """
                INSERT INTO memory_events (
                    event_id, entry_id, event_ts, event_type, summary, detail_json,
                    importance, persistence_class, decay_profile, modality_tags_json,
                    reinforcement_count, last_reinforced_ts, priority_active_pc,
                    pinned, created_at
                ) VALUES (
                    :event_id, :entry_id, :event_ts, :event_type, :summary, :detail_json,
                    :importance, :persistence_class, :decay_profile, :modality_tags_json,
                    :reinforcement_count, :last_reinforced_ts, :priority_active_pc,
                    :pinned, :created_at
                )
                ON CONFLICT(event_id) DO UPDATE SET
                    event_ts = excluded.event_ts,
                    event_type = excluded.event_type,
                    summary = excluded.summary,
                    detail_json = excluded.detail_json,
                    importance = excluded.importance,
                    persistence_class = excluded.persistence_class,
                    decay_profile = excluded.decay_profile,
                    modality_tags_json = excluded.modality_tags_json,
                    reinforcement_count = excluded.reinforcement_count,
                    last_reinforced_ts = excluded.last_reinforced_ts,
                    priority_active_pc = excluded.priority_active_pc,
                    pinned = excluded.pinned
                """,
                {
                    "event_id": event["event_id"],
                    "entry_id": event.get("entry_id"),
                    "event_ts": event["event_ts"],
                    "event_type": event["event_type"],
                    "summary": event["summary"],
                    "detail_json": event.get("detail_json"),
                    "importance": int(event.get("importance", 50)),
                    "persistence_class": event.get("persistence_class", "ambient"),
                    "decay_profile": event.get("decay_profile", "medium"),
                    "modality_tags_json": event.get("modality_tags_json", "[]"),
                    "reinforcement_count": int(event.get("reinforcement_count", 0)),
                    "last_reinforced_ts": event.get("last_reinforced_ts"),
                    "priority_active_pc": 1 if event.get("priority_active_pc") else 0,
                    "pinned": 1 if event.get("pinned") else 0,
                    "created_at": event.get("created_at", _utc_now_iso()),
                },
            )
        return str(event["event_id"])
    finally:
        if conn is not None:
            conn.close()


def create_memory_link(db_path: str, link: Dict[str, Any]) -> int:
    """Insert or update one memory link and return row id."""
    required_fields = ["event_id", "entity_id", "link_role"]
    for field_name in required_fields:
        if not link.get(field_name):
            raise ValueError(f"Missing required link field: {field_name}")

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)
        with conn:
            conn.execute(
                """
                INSERT INTO memory_links (event_id, entity_id, link_role, link_salience, metadata_json)
                VALUES (:event_id, :entity_id, :link_role, :link_salience, :metadata_json)
                ON CONFLICT(event_id, entity_id, link_role) DO UPDATE SET
                    link_salience = excluded.link_salience,
                    metadata_json = excluded.metadata_json
                """,
                {
                    "event_id": link["event_id"],
                    "entity_id": link["entity_id"],
                    "link_role": link["link_role"],
                    "link_salience": float(link.get("link_salience", 0.5)),
                    "metadata_json": link.get("metadata_json"),
                },
            )
            row = conn.execute(
                """
                SELECT link_id FROM memory_links
                WHERE event_id = :event_id AND entity_id = :entity_id AND link_role = :link_role
                """,
                {
                    "event_id": link["event_id"],
                    "entity_id": link["entity_id"],
                    "link_role": link["link_role"],
                },
            ).fetchone()
        return int(row[0]) if row else 0
    finally:
        if conn is not None:
            conn.close()
