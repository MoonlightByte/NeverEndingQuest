# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Memory retrieval plan validation tests.

This test module validates the retrieval behavior drafted in plans/memory.md
before full schema and service scaffolding is implemented.

Usage:
    python3 scripts/test_memory_retrieval_plan.py
    python3 scripts/test_memory_retrieval_plan.py -v
"""

import json
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def create_test_schema(conn: sqlite3.Connection) -> None:
    """Create minimal retrieval-focused schema for plan validation."""
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE entities (
            entity_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            entity_kind TEXT NOT NULL,
            is_retired INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT
        );

        CREATE TABLE journal_entries (
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

        CREATE TABLE memory_events (
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
            FOREIGN KEY(entry_id) REFERENCES journal_entries(entry_id)
        );

        CREATE TABLE memory_links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            link_role TEXT NOT NULL,
            link_salience REAL NOT NULL DEFAULT 0.5,
            metadata_json TEXT,
            UNIQUE(event_id, entity_id, link_role),
            FOREIGN KEY(event_id) REFERENCES memory_events(event_id),
            FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
        );

        CREATE INDEX idx_events_priority
            ON memory_events(pinned DESC, priority_active_pc DESC, importance DESC, event_ts DESC);
        CREATE INDEX idx_links_entity ON memory_links(entity_id, link_role);
        """
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def days_ago_iso(days: int) -> str:
    ts = datetime.now(timezone.utc) - timedelta(days=days)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_entity_timeline(conn: sqlite3.Connection, entity_id: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Plan query implementation for deterministic timeline ranking."""
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
    ORDER BY retrieval_score DESC, event_ts DESC
    LIMIT :limit;
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, {"entity_id": entity_id, "limit": limit}).fetchall()
    return [dict(row) for row in rows]


def get_context_memories(
    conn: sqlite3.Connection,
    scene_type: str,
    active_entities: List[str],
    limit: int = 12,
) -> List[Dict[str, Any]]:
    """Plan-level scene retrieval function for matrix checks."""
    if not active_entities:
        return []

    values_clause = ", ".join(["(?)" for _ in active_entities])
    sql = f"""
    WITH active_entities(entity_id) AS (
        VALUES {values_clause}
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
        retrieval_score
    FROM scored
    ORDER BY retrieval_score DESC, event_ts DESC
    LIMIT ?;
    """

    params = [*active_entities, scene_type, scene_type, scene_type, limit]
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_retirement_return_memories(conn: sqlite3.Connection, entity_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch role-transition milestones for an entity."""
    sql = """
    SELECT
        me.event_id,
        me.event_ts,
        me.event_type,
        me.summary,
        me.pinned,
        me.importance
    FROM memory_events me
    JOIN memory_links ml ON ml.event_id = me.event_id
    WHERE ml.entity_id = :entity_id
      AND me.event_type IN ('role_transition', 'milestone')
      AND (
          me.summary LIKE '%retire%'
          OR me.summary LIKE '%return%'
          OR me.persistence_class IN ('identity_core', 'campaign_major')
      )
    ORDER BY me.pinned DESC, me.importance DESC, me.event_ts DESC
    LIMIT :limit;
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, {"entity_id": entity_id, "limit": limit}).fetchall()
    return [dict(row) for row in rows]


def ingest_journal_entry(conn: sqlite3.Connection, payload: Dict[str, Any]) -> int:
    """Idempotent journal ingest used by matrix checks."""
    insert_sql = """
    INSERT INTO journal_entries (
        entry_ts,
        title,
        content,
        source_type,
        source_ref,
        checksum,
        metadata_json,
        created_at
    ) VALUES (
        :entry_ts,
        :title,
        :content,
        :source_type,
        :source_ref,
        :checksum,
        :metadata_json,
        :created_at
    )
    ON CONFLICT(source_type, checksum) DO NOTHING;
    """

    with conn:
        conn.execute(insert_sql, payload)
        row = conn.execute(
            """
            SELECT entry_id
            FROM journal_entries
            WHERE source_type = :source_type
              AND checksum = :checksum
            """,
            {"source_type": payload["source_type"], "checksum": payload["checksum"]},
        ).fetchone()
    return int(row[0])


class TestMemoryRetrievalPlan(unittest.TestCase):
    """Deterministic retrieval checks from plans/memory.md test matrix."""

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        create_test_schema(self.conn)
        self.seed_entities()
        self.seed_events_for_acheron()

    def tearDown(self) -> None:
        self.conn.close()

    def seed_entities(self) -> None:
        ts = now_iso()
        rows = [
            ("acheron", "Acheron", "character", ts, ts),
            ("merisiel", "Merisiel", "character", ts, ts),
            ("kira", "Scout Kira", "character", ts, ts),
        ]
        self.conn.executemany(
            """
            INSERT INTO entities (entity_id, display_name, entity_kind, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    def insert_event(
        self,
        event_id: str,
        event_ts: str,
        event_type: str,
        summary: str,
        importance: int,
        persistence_class: str,
        decay_profile: str,
        modality_tags: List[str],
        reinforcement_count: int,
        priority_active_pc: int,
        pinned: int,
        entity_id: str = "acheron",
    ) -> None:
        created_at = now_iso()
        self.conn.execute(
            """
            INSERT INTO memory_events (
                event_id, event_ts, event_type, summary, importance,
                persistence_class, decay_profile, modality_tags_json,
                reinforcement_count, priority_active_pc, pinned, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_ts,
                event_type,
                summary,
                importance,
                persistence_class,
                decay_profile,
                json.dumps(modality_tags),
                reinforcement_count,
                priority_active_pc,
                pinned,
                created_at,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO memory_links (event_id, entity_id, link_role)
            VALUES (?, ?, ?)
            """,
            (event_id, entity_id, "actor"),
        )

    def seed_events_for_acheron(self) -> None:
        # 1) identity_core, pinned=1, old timestamp
        self.insert_event(
            event_id="evt_identity_pinned_old",
            event_ts=days_ago_iso(220),
            event_type="milestone",
            summary="Acheron swore the Keep Oath before the old banners.",
            importance=90,
            persistence_class="identity_core",
            decay_profile="none",
            modality_tags=["episodic", "plot_state"],
            reinforcement_count=1,
            priority_active_pc=0,
            pinned=1,
        )

        # 2) campaign_major, pinned=0, medium recency
        self.insert_event(
            event_id="evt_campaign_major_mid",
            event_ts=days_ago_iso(40),
            event_type="milestone",
            summary="The bridge to Stonepass fell during the siege.",
            importance=75,
            persistence_class="campaign_major",
            decay_profile="slow",
            modality_tags=["episodic", "plot_state"],
            reinforcement_count=0,
            priority_active_pc=0,
            pinned=0,
        )

        # 3) relationship_core, active_pc=1, recent
        self.insert_event(
            event_id="evt_relationship_recent",
            event_ts=days_ago_iso(6),
            event_type="relationship",
            summary="Acheron and Merisiel reconciled after the harbor dispute.",
            importance=70,
            persistence_class="relationship_core",
            decay_profile="medium",
            modality_tags=["social", "relationship", "episodic"],
            reinforcement_count=1,
            priority_active_pc=1,
            pinned=0,
        )

        # 4) procedural, active_pc=1, very recent, reinforcement=4
        self.insert_event(
            event_id="evt_procedural_recent_reinforced",
            event_ts=days_ago_iso(2),
            event_type="combat",
            summary="Acheron uses shield press then flank cut in close quarters.",
            importance=60,
            persistence_class="procedural",
            decay_profile="fast",
            modality_tags=["procedural", "episodic"],
            reinforcement_count=4,
            priority_active_pc=1,
            pinned=0,
        )

        # 5) ambient, active_pc=0, very recent
        self.insert_event(
            event_id="evt_ambient_recent",
            event_ts=days_ago_iso(1),
            event_type="other",
            summary="The market smelled of pears and lamp oil.",
            importance=30,
            persistence_class="ambient",
            decay_profile="fast",
            modality_tags=["sensory_symbolic"],
            reinforcement_count=0,
            priority_active_pc=0,
            pinned=0,
        )

        # 6) campaign_major, active_pc=1, old but reinforced
        self.insert_event(
            event_id="evt_campaign_old_reinforced",
            event_ts=days_ago_iso(180),
            event_type="milestone",
            summary="The pact with Riverwatch was renewed under witness.",
            importance=65,
            persistence_class="campaign_major",
            decay_profile="slow",
            modality_tags=["plot_state", "social"],
            reinforcement_count=6,
            priority_active_pc=1,
            pinned=0,
        )

    def test_pinned_identity_ranks_above_recent_ambient(self) -> None:
        timeline = get_entity_timeline(self.conn, "acheron", limit=10)
        order = [row["event_id"] for row in timeline]
        self.assertLess(order.index("evt_identity_pinned_old"), order.index("evt_ambient_recent"))

    def test_active_pc_events_outrank_recent_ambient(self) -> None:
        timeline = get_entity_timeline(self.conn, "acheron", limit=10)
        order = [row["event_id"] for row in timeline]
        self.assertLess(order.index("evt_relationship_recent"), order.index("evt_ambient_recent"))
        self.assertLess(order.index("evt_procedural_recent_reinforced"), order.index("evt_ambient_recent"))

    def test_reinforced_old_campaign_can_beat_ambient_recent(self) -> None:
        timeline = get_entity_timeline(self.conn, "acheron", limit=10)
        order = [row["event_id"] for row in timeline]
        self.assertLess(order.index("evt_campaign_old_reinforced"), order.index("evt_ambient_recent"))

    def test_limit_three_is_deterministic(self) -> None:
        first = get_entity_timeline(self.conn, "acheron", limit=3)
        second = get_entity_timeline(self.conn, "acheron", limit=3)
        first_ids = [row["event_id"] for row in first]
        second_ids = [row["event_id"] for row in second]
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(first_ids), 3)

    def test_scene_combat_prefers_procedural_or_episodic(self) -> None:
        rows = get_context_memories(self.conn, scene_type="combat", active_entities=["acheron"], limit=5)
        event_ids = [row["event_id"] for row in rows]
        self.assertIn("evt_procedural_recent_reinforced", event_ids)

    def test_scene_social_prefers_relationship(self) -> None:
        rows = get_context_memories(self.conn, scene_type="social", active_entities=["acheron"], limit=5)
        event_ids = [row["event_id"] for row in rows]
        self.assertIn("evt_relationship_recent", event_ids)

    def test_scene_empty_active_entities_returns_empty(self) -> None:
        rows = get_context_memories(self.conn, scene_type="social", active_entities=[], limit=5)
        self.assertEqual(rows, [])

    def test_retirement_return_memory_query(self) -> None:
        self.insert_event(
            event_id="evt_retirement",
            event_ts=days_ago_iso(15),
            event_type="role_transition",
            summary="Acheron retires to steward the Keep.",
            importance=85,
            persistence_class="identity_core",
            decay_profile="none",
            modality_tags=["plot_state", "social"],
            reinforcement_count=1,
            priority_active_pc=1,
            pinned=1,
        )
        self.insert_event(
            event_id="evt_return",
            event_ts=days_ago_iso(3),
            event_type="role_transition",
            summary="Acheron returns from retirement to defend Riverwatch.",
            importance=85,
            persistence_class="identity_core",
            decay_profile="none",
            modality_tags=["plot_state", "episodic"],
            reinforcement_count=1,
            priority_active_pc=1,
            pinned=1,
        )

        rows = get_retirement_return_memories(self.conn, "acheron", limit=10)
        ids = [row["event_id"] for row in rows]
        self.assertIn("evt_retirement", ids)
        self.assertIn("evt_return", ids)

    def test_journal_ingest_is_idempotent(self) -> None:
        payload = {
            "entry_ts": now_iso(),
            "title": "Test Entry",
            "content": "Acheron records the watch schedule.",
            "source_type": "journal",
            "source_ref": "journal.json:1",
            "checksum": "abc123checksum",
            "metadata_json": "{}",
            "created_at": now_iso(),
        }

        first_id = ingest_journal_entry(self.conn, payload)
        second_id = ingest_journal_entry(self.conn, payload)
        self.assertEqual(first_id, second_id)

        count = self.conn.execute(
            "SELECT COUNT(*) FROM journal_entries WHERE source_type = ? AND checksum = ?",
            ("journal", "abc123checksum"),
        ).fetchone()[0]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
