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
import os
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


def _connect_readonly(db_path: str) -> Optional[sqlite3.Connection]:
    """Open database in read-only mode; return None if DB does not exist.
    
    TABLETOP MODE: Prevents implicit DB creation during retrieval operations.
    """
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        return None


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
    """Get deterministic ranked timeline for one entity with bounded candidate pre-selection."""
    if not entity_id:
        return []

    safe_limit = _clamp_limit(limit)
    started = time.perf_counter()
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect_readonly(db_path)
        if conn is None:
            debug(f"MEMORY_RETRIEVAL: DB not found at {db_path}, returning empty timeline", category="memory_retrieval")
            return []

        bounded_candidate_limit = min(MAX_LIMIT, safe_limit * 3)

        sql = """
        WITH ranked_candidates AS (
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
                CAST((julianday('now') - julianday(me.event_ts)) AS REAL) AS age_days,
                (
                    CASE WHEN me.pinned = 1 THEN 100 ELSE 0 END +
                    CASE WHEN me.priority_active_pc = 1 THEN 25 ELSE 0 END +
                    (me.importance * 0.35) +
                    CASE me.persistence_class
                        WHEN 'identity_core' THEN 30
                        WHEN 'campaign_major' THEN 24
                        WHEN 'relationship_core' THEN 20
                        WHEN 'procedural' THEN 14
                        ELSE 4
                    END
                ) AS prelim_score
            FROM memory_events me
            WHERE me.event_id IN (
                SELECT DISTINCT ml.event_id
                FROM memory_links ml
                WHERE ml.entity_id = :entity_id
            )
            ORDER BY prelim_score DESC, me.event_ts DESC, me.event_id ASC
            LIMIT :candidate_limit
        ),
        scored AS (
            SELECT
                rc.*,
                (
                    rc.prelim_score +
                    CASE
                        WHEN rc.decay_profile = 'none' THEN 20
                        WHEN rc.decay_profile = 'slow' THEN
                            CASE
                                WHEN rc.age_days <= 30 THEN 20
                                WHEN rc.age_days <= 90 THEN 16
                                WHEN rc.age_days <= 180 THEN 12
                                WHEN rc.age_days <= 365 THEN 8
                                ELSE 4
                            END
                        WHEN rc.decay_profile = 'medium' THEN
                            CASE
                                WHEN rc.age_days <= 7 THEN 20
                                WHEN rc.age_days <= 30 THEN 14
                                WHEN rc.age_days <= 90 THEN 8
                                WHEN rc.age_days <= 180 THEN 4
                                ELSE 1
                            END
                        ELSE
                            CASE
                                WHEN rc.age_days <= 3 THEN 20
                                WHEN rc.age_days <= 7 THEN 10
                                WHEN rc.age_days <= 30 THEN 4
                                ELSE 1
                            END
                    END +
                    MIN(18, rc.reinforcement_count * 2)
                ) AS retrieval_score
            FROM ranked_candidates rc
        )
        SELECT DISTINCT
            event_id,
            event_ts,
            event_type,
            summary,
            priority_active_pc,
            pinned,
            retrieval_score
        FROM scored
        ORDER BY retrieval_score DESC, event_ts DESC, event_id ASC
        LIMIT :limit;
        """

        cursor = conn.execute(sql, {"entity_id": entity_id, "candidate_limit": bounded_candidate_limit, "limit": safe_limit})
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]

        pre_candidate_count = conn.execute(
            "SELECT COUNT(DISTINCT event_id) FROM memory_links WHERE entity_id = :entity_id",
            {"entity_id": entity_id}
        ).fetchone()[0]

        if enable_audit and result:
            # Best-effort audit logging with separate write connection
            audit_conn = None
            try:
                audit_conn = _connect(db_path)
                _log_retrieval_audit(
                    audit_conn,
                    request_type="timeline",
                    entity_scope={"entity_id": entity_id},
                    rows=result,
                    candidate_count=pre_candidate_count,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                audit_conn.commit()
            except Exception as audit_error:
                debug(f"MEMORY_RETRIEVAL: Audit logging failed (non-critical): {audit_error}", category="memory_retrieval")
            finally:
                if audit_conn is not None:
                    audit_conn.close()

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
        # Use read-only connection for query (TABLETOP MODE: prevents DB creation)
        conn = _connect_readonly(db_path)
        if conn is None:
            debug(f"MEMORY_RETRIEVAL: DB not found at {db_path}, returning empty context", category="memory_retrieval")
            return []

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

        # Count pre-limit candidates (distinct events linked to active entities)
        pre_candidate_count = conn.execute(
            """
            SELECT COUNT(DISTINCT me.event_id)
            FROM memory_events me
            JOIN memory_links ml ON ml.event_id = me.event_id
            WHERE ml.entity_id IN ({})
            """.format(",".join(["?" for _ in active_entities])),
            active_entities,
        ).fetchone()[0]

        if enable_audit and result:
            # Best-effort audit logging with separate write connection
            audit_conn = None
            try:
                audit_conn = _connect(db_path)
                _log_retrieval_audit(
                    audit_conn,
                    request_type="scene_pack",
                    scene_type=scene_type,
                    entity_scope={"active_entities": active_entities},
                    rows=result,
                    candidate_count=pre_candidate_count,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                audit_conn.commit()
            except Exception as audit_error:
                debug(f"MEMORY_RETRIEVAL: Audit logging failed (non-critical): {audit_error}", category="memory_retrieval")
            finally:
                if audit_conn is not None:
                    audit_conn.close()

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
        # Use read-only connection for query (TABLETOP MODE: prevents DB creation)
        conn = _connect_readonly(db_path)
        if conn is None:
            debug(f"MEMORY_RETRIEVAL: DB not found at {db_path}, returning empty retirement/return", category="memory_retrieval")
            return []

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

        # Count pre-limit candidates (retirement/return events for this entity)
        pre_candidate_count = conn.execute(
            """
            SELECT COUNT(DISTINCT me.event_id)
            FROM memory_events me
            JOIN memory_links ml ON ml.event_id = me.event_id
            WHERE ml.entity_id = :entity_id
              AND me.event_type IN ('role_transition', 'milestone')
              AND (
                  me.summary LIKE '%retire%'
                  OR me.summary LIKE '%return%'
                  OR me.persistence_class IN ('identity_core', 'campaign_major')
              )
            """,
            {"entity_id": entity_id},
        ).fetchone()[0]

        if enable_audit and result:
            # Best-effort audit logging with separate write connection
            audit_conn = None
            try:
                audit_conn = _connect(db_path)
                _log_retrieval_audit(
                    audit_conn,
                    request_type="retirement_return",
                    entity_scope={"entity_id": entity_id},
                    rows=result,
                    candidate_count=pre_candidate_count,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                audit_conn.commit()
            except Exception as audit_error:
                debug(f"MEMORY_RETRIEVAL: Audit logging failed (non-critical): {audit_error}", category="memory_retrieval")
            finally:
                if audit_conn is not None:
                    audit_conn.close()

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
