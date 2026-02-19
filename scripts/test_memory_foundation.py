# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Memory foundation integration tests.

Validates migration idempotency, retrieval ordering, retirement/return coverage,
ingestion dedupe, and route smoke behavior for the new memory layer.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    Flask = None
    FLASK_AVAILABLE = False

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import init_memory_db
from core.memory.memory_ingest import ingest_journal_entry
from core.memory.memory_retrieval import get_entity_timeline, get_retirement_return_memories


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _days_ago_iso(days: int) -> str:
    ts = datetime.now(timezone.utc) - timedelta(days=days)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TestMemoryFoundation(unittest.TestCase):
    """Integration coverage for memory foundation requirements."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_memory_test_")
        self.db_path = os.path.join(self.temp_dir, "memory_test.db")

    def tearDown(self) -> None:
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _seed_entity_and_events(self) -> None:
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(
                """
                INSERT INTO entities (entity_id, display_name, entity_kind, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("acheron", "Acheron", "character", _utc_now_iso(), _utc_now_iso()),
            )

            events = [
                (
                    "evt_pinned_old",
                    _days_ago_iso(200),
                    "milestone",
                    "Old oath at the keep.",
                    85,
                    "identity_core",
                    "none",
                    json.dumps(["episodic"]),
                    1,
                    0,
                    1,
                    _utc_now_iso(),
                ),
                (
                    "evt_ambient_recent",
                    _days_ago_iso(1),
                    "other",
                    "Street chatter in the market.",
                    20,
                    "ambient",
                    "fast",
                    json.dumps(["sensory_symbolic"]),
                    0,
                    0,
                    0,
                    _utc_now_iso(),
                ),
                (
                    "evt_retirement",
                    _days_ago_iso(9),
                    "role_transition",
                    "Acheron retires to steward the Keep.",
                    90,
                    "identity_core",
                    "none",
                    json.dumps(["plot_state"]),
                    0,
                    1,
                    1,
                    _utc_now_iso(),
                ),
                (
                    "evt_return",
                    _days_ago_iso(2),
                    "role_transition",
                    "Acheron returns from retirement.",
                    90,
                    "identity_core",
                    "none",
                    json.dumps(["plot_state"]),
                    0,
                    1,
                    1,
                    _utc_now_iso(),
                ),
            ]

            conn.executemany(
                """
                INSERT INTO memory_events (
                    event_id, event_ts, event_type, summary, importance,
                    persistence_class, decay_profile, modality_tags_json,
                    reinforcement_count, priority_active_pc, pinned, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                events,
            )

            conn.executemany(
                """
                INSERT INTO memory_links (event_id, entity_id, link_role)
                VALUES (?, ?, ?)
                """,
                [
                    ("evt_pinned_old", "acheron", "actor"),
                    ("evt_ambient_recent", "acheron", "witness"),
                    ("evt_retirement", "acheron", "actor"),
                    ("evt_return", "acheron", "actor"),
                ],
            )
        conn.close()

    def test_migrations_are_idempotent(self) -> None:
        self.assertTrue(init_memory_db(self.db_path))
        self.assertTrue(init_memory_db(self.db_path))

        conn = sqlite3.connect(self.db_path)
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()

        self.assertIn("entities", table_names)
        self.assertIn("memory_events", table_names)
        self.assertIn("retrieval_audit_log", table_names)

    def test_retrieval_ordering_high_signal_over_ambient(self) -> None:
        self.assertTrue(init_memory_db(self.db_path))
        self._seed_entity_and_events()

        rows = get_entity_timeline("acheron", limit=10, db_path=self.db_path)
        event_ids = [row["event_id"] for row in rows]
        self.assertLess(event_ids.index("evt_pinned_old"), event_ids.index("evt_ambient_recent"))

    def test_retirement_return_query_coverage(self) -> None:
        self.assertTrue(init_memory_db(self.db_path))
        self._seed_entity_and_events()

        rows = get_retirement_return_memories("acheron", limit=10, db_path=self.db_path)
        event_ids = [row["event_id"] for row in rows]
        self.assertIn("evt_retirement", event_ids)
        self.assertIn("evt_return", event_ids)

    def test_ingest_dedupe_by_source_and_checksum(self) -> None:
        self.assertTrue(init_memory_db(self.db_path))

        payload = {
            "entry_ts": _utc_now_iso(),
            "title": "Night Watch",
            "content": "Acheron records guard rotations.",
            "source_type": "journal",
            "source_ref": "journal.json:12",
            "checksum": "fixed_checksum_001",
            "metadata_json": "{}",
            "created_at": _utc_now_iso(),
        }

        first = ingest_journal_entry(payload, db_path=self.db_path)
        second = ingest_journal_entry(payload, db_path=self.db_path)
        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "success")
        self.assertEqual(first["entry_id"], second["entry_id"])

        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM journal_entries WHERE source_type = ? AND checksum = ?",
            ("journal", "fixed_checksum_001"),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_route_smoke_success_and_fallback(self) -> None:
        if not FLASK_AVAILABLE:
            self.skipTest("Flask not installed in current environment")

        import web.routes.memory_routes as memory_routes

        # Success path
        self.assertTrue(init_memory_db(self.db_path))
        self._seed_entity_and_events()

        app = Flask(__name__)
        memory_routes.DEFAULT_MEMORY_DB_PATH = self.db_path
        memory_routes.register_memory_routes(app)
        client = app.test_client()

        success_response = client.get("/api/memory/entity/acheron?limit=5")
        self.assertEqual(success_response.status_code, 200)
        success_payload = success_response.get_json()
        self.assertEqual(success_payload.get("status"), "success")
        self.assertGreaterEqual(success_payload.get("count", 0), 1)

        # Fallback path: point route to missing DB path
        missing_db = os.path.join(self.temp_dir, "missing", "memory.db")
        memory_routes.DEFAULT_MEMORY_DB_PATH = missing_db
        app_fallback = Flask(__name__ + "_fallback")
        memory_routes.register_memory_routes(app_fallback)
        fallback_client = app_fallback.test_client()
        fallback_response = fallback_client.get("/api/memory/entity/acheron?limit=5")
        self.assertEqual(fallback_response.status_code, 200)
        fallback_payload = fallback_response.get_json()
        self.assertEqual(fallback_payload.get("status"), "success")
        self.assertEqual(fallback_payload.get("count"), 0)


if __name__ == "__main__":
    unittest.main()
