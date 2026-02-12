# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Memory Retrieval - Deterministic ranking queries.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.enhanced_logger import debug, error

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH


MIN_LIMIT = 1
MAX_LIMIT = 100


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clamp_limit(limit: int, default: int = 25) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = default
    return max(MIN_LIMIT, min(MAX_LIMIT, parsed))


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _log_retrieval_audit(
    conn: sqlite3.Connection,
    request_type: str,
    entity_scope: Dict[str, Any],
    rows: List[Dict[str, Any]],
    candidate_count: int,
    latency_ms: int,
    scene_type: Optional[str] = None,
) -> None:
    """Best-effort audit logging; safely no-ops if table missing."""
    score_breakdown = {}
    for row in rows:
        score_breakdown[row.get("event_id", "unknown")] = {
            "retrieval_score": row.get("retrieval_score", 0),
            "priority_active_pc": row.get("priority_active_pc", 0),
            "pinned": row.get("pinned", 0),
        }

    try:
        conn.execute(
            """
            INSERT INTO retrieval_audit_log (
                request_ts, request_type, scene_type, entity_scope_json,
                policy_id, candidate_count, result_count, result_event_ids_json,
                score_breakdown_json, token_estimate, latency_ms, mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now_iso(),
                request_type,
                scene_type,
                json.dumps(entity_scope),
                None,
                int(candidate_count),
                len(rows),
                json.dumps([row.get("event_id") for row in rows]),
                json.dumps(score_breakdown),
                0,
                int(latency_ms),
                "live",
            ),
        )
    except sqlite3.OperationalError:
        return


def get_entity_timeline(
    entity_id: str,
    limit: int = 25,
    db_path: str = DEFAULT_MEMORY_DB_PATH,
    enable_audit: bool = False,
) -> List[Dict[str, Any]]:
    """Get deterministic ranked timeline for one entity."""
    if not entity_id:
        return []

    safe_limit = _clamp_limit(limit)
    started = time.perf_counter()
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)
        sql = """
        WITH candidate_events AS (
            SELECT
                me.event_id,
                me.event_ts,
                me.event_type,
                me.summary,
                me.importance,
                me.persistence_class,
                me.decay_profile,
                me.modality_tags_json,
                me.reinforcement_count,
                me.priority_active_pc,
                me.pinned,
                ml.link_role,
                CAST((julianday('now') - julianday(me.event_ts)) AS REAL) AS age_days
            FROM memory_events me
            JOIN memory_links ml ON ml.event_id = me.event_id
            WHERE ml.entity_id = :entity_id
        ),
        scored AS (
            SELECT
                ce.*,
                (
                    CASE WHEN ce.pinned = 1 THEN 100 ELSE 0 END +
                    CASE WHEN ce.priority_active_pc = 1 THEN 25 ELSE 0 END +
                    (ce.importance * 0.35) +
                    CASE ce.persistence_class
                        WHEN 'identity_core' THEN 30
                        WHEN 'campaign_major' THEN 24
                        WHEN 'relationship_core' THEN 20
                        WHEN 'procedural' THEN 14
                        ELSE 4
                    END +
                    CASE
                        WHEN ce.decay_profile = 'none' THEN 20
                        WHEN ce.decay_profile = 'slow' THEN
                            CASE
                                WHEN ce.age_days <= 30 THEN 20
                                WHEN ce.age_days <= 90 THEN 16
                                WHEN ce.age_days <= 180 THEN 12
                                WHEN ce.age_days <= 365 THEN 8
                                ELSE 4
                            END
                        WHEN ce.decay_profile = 'medium' THEN
                            CASE
                                WHEN ce.age_days <= 7 THEN 20
                                WHEN ce.age_days <= 30 THEN 14
                                WHEN ce.age_days <= 90 THEN 8
                                WHEN ce.age_days <= 180 THEN 4
                                ELSE 1
                            END
                        ELSE
                            CASE
                                WHEN ce.age_days <= 3 THEN 20
                                WHEN ce.age_days <= 7 THEN 10
                                WHEN ce.age_days <= 30 THEN 4
                                ELSE 1
                            END
                    END +
                    MIN(18, ce.reinforcement_count * 2)
                ) AS retrieval_score
            FROM candidate_events ce
        )
        SELECT
            event_id,
            event_ts,
            event_type,
            summary,
            priority_active_pc,
            pinned,
            link_role,
            retrieval_score
        FROM scored
        ORDER BY retrieval_score DESC, event_ts DESC, event_id ASC
        LIMIT :limit;
        """

        rows = conn.execute(sql, {"entity_id": entity_id, "limit": safe_limit}).fetchall()
        result = [dict(row) for row in rows]

        if enable_audit:
            _log_retrieval_audit(
                conn,
                request_type="timeline",
                entity_scope={"entity_id": entity_id},
                rows=result,
                candidate_count=len(result),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            conn.commit()

        return result
    except Exception as retrieval_error:
        error(
            f"MEMORY_RETRIEVAL: Timeline query failed for {entity_id}: {retrieval_error}",
            exception=retrieval_error,
            category="memory_retrieval",
        )
        return []
    finally:
        if conn is not None:
            conn.close()


def get_context_memories(
    scene_type: str,
    active_entities: List[str],
    limit: int = 12,
    db_path: str = DEFAULT_MEMORY_DB_PATH,
    enable_audit: bool = False,
) -> List[Dict[str, Any]]:
    """Get scene-aware memory pack for active entities."""
    if not active_entities:
        return []

    safe_limit = _clamp_limit(limit, default=12)
    placeholders = ", ".join(["(?)" for _ in active_entities])
    started = time.perf_counter()
    conn: Optional[sqlite3.Connection] = None

    try:
        conn = _connect(db_path)
        sql = f"""
        WITH active_entities(entity_id) AS (
            VALUES {placeholders}
        ),
        candidate AS (
            SELECT DISTINCT
                me.event_id,
                me.event_ts,
                me.event_type,
                me.summary,
                me.persistence_class,
                me.priority_active_pc,
                me.pinned,
                me.modality_tags_json
            FROM memory_events me
            JOIN memory_links ml ON ml.event_id = me.event_id
            JOIN active_entities ae ON ae.entity_id = ml.entity_id
        ),
        scored AS (
            SELECT
                c.*,
                (
                    CASE WHEN c.pinned = 1 THEN 100 ELSE 0 END +
                    CASE WHEN c.priority_active_pc = 1 THEN 25 ELSE 0 END +
                    CASE c.persistence_class
                        WHEN 'identity_core' THEN 30
                        WHEN 'campaign_major' THEN 24
                        WHEN 'relationship_core' THEN 20
                        WHEN 'procedural' THEN 14
                        ELSE 4
                    END +
                    CASE
                        WHEN ? = 'combat' AND EXISTS (
                            SELECT 1 FROM json_each(c.modality_tags_json)
                            WHERE value IN ('procedural','episodic')
                        ) THEN 10
                        WHEN ? = 'social' AND EXISTS (
                            SELECT 1 FROM json_each(c.modality_tags_json)
                            WHERE value IN ('social','relationship')
                        ) THEN 10
                        WHEN ? IN ('travel','rest','planning') AND EXISTS (
                            SELECT 1 FROM json_each(c.modality_tags_json)
                            WHERE value IN ('plot_state','episodic','sensory_symbolic')
                        ) THEN 10
                        ELSE 0
                    END
                ) AS retrieval_score
            FROM candidate c
        )
        SELECT
            event_id,
            event_ts,
            event_type,
            summary,
            retrieval_score,
            priority_active_pc,
            pinned
        FROM scored
        ORDER BY retrieval_score DESC, event_ts DESC, event_id ASC
        LIMIT ?
        """

        params = [*active_entities, scene_type, scene_type, scene_type, safe_limit]
        rows = conn.execute(sql, params).fetchall()
        result = [dict(row) for row in rows]

        if enable_audit:
            _log_retrieval_audit(
                conn,
                request_type="scene_pack",
                scene_type=scene_type,
                entity_scope={"active_entities": active_entities},
                rows=result,
                candidate_count=len(result),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            conn.commit()

        return result
    except Exception as retrieval_error:
        error(
            f"MEMORY_RETRIEVAL: Context query failed for scene {scene_type}: {retrieval_error}",
            exception=retrieval_error,
            category="memory_retrieval",
        )
        return []
    finally:
        if conn is not None:
            conn.close()


def get_retirement_return_memories(
    entity_id: str,
    limit: int = 20,
    db_path: str = DEFAULT_MEMORY_DB_PATH,
    enable_audit: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch retirement and return milestones for one entity."""
    if not entity_id:
        return []

    safe_limit = _clamp_limit(limit, default=20)
    started = time.perf_counter()
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect(db_path)
        sql = """
        SELECT
            me.event_id,
            me.event_ts,
            me.event_type,
            me.summary,
            me.pinned,
            me.importance,
            ml.link_role
        FROM memory_events me
        JOIN memory_links ml ON ml.event_id = me.event_id
        WHERE ml.entity_id = :entity_id
          AND me.event_type IN ('role_transition', 'milestone')
          AND (
              me.summary LIKE '%retire%'
              OR me.summary LIKE '%return%'
              OR me.persistence_class IN ('identity_core', 'campaign_major')
          )
        ORDER BY me.pinned DESC, me.importance DESC, me.event_ts DESC, me.event_id ASC
        LIMIT :limit
        """

        rows = conn.execute(sql, {"entity_id": entity_id, "limit": safe_limit}).fetchall()
        result = [dict(row) for row in rows]

        if enable_audit:
            _log_retrieval_audit(
                conn,
                request_type="retirement_return",
                entity_scope={"entity_id": entity_id},
                rows=result,
                candidate_count=len(result),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            conn.commit()

        return result
    except Exception as retrieval_error:
        error(
            f"MEMORY_RETRIEVAL: Retirement/return query failed for {entity_id}: {retrieval_error}",
            exception=retrieval_error,
            category="memory_retrieval",
        )
        return []
    finally:
        if conn is not None:
            conn.close()
