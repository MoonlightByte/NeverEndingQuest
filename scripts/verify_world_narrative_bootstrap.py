# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""World narrative seed bootstrap tests."""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import bootstrap_memory_db_from_seed, init_memory_db


class TestWorldNarrativeBootstrap(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_world_bootstrap_test_")
        self.seed_path = os.path.join(self.temp_dir, "world_narrative_seed.db")
        self.runtime_path = os.path.join(self.temp_dir, "memory.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _table_exists(self, db_path: str, table_name: str) -> bool:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            return bool(row)
        finally:
            conn.close()

    def test_bootstrap_copies_seed_when_runtime_missing(self) -> None:
        # Create a tiny seed DB with one marker table.
        conn = sqlite3.connect(self.seed_path)
        conn.execute("CREATE TABLE seed_marker (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO seed_marker (id) VALUES (1)")
        conn.commit()
        conn.close()

        result = bootstrap_memory_db_from_seed(
            runtime_db_path=self.runtime_path,
            seed_db_path=self.seed_path,
        )
        self.assertTrue(init_memory_db(self.runtime_path))

        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("reason"), "bootstrapped_from_seed")
        self.assertTrue(os.path.exists(self.runtime_path))
        self.assertTrue(self._table_exists(self.runtime_path, "seed_marker"))
        # Migrations should still run after copy.
        self.assertTrue(self._table_exists(self.runtime_path, "inspiration_atoms"))

    def test_bootstrap_initializes_empty_when_seed_missing(self) -> None:
        result = bootstrap_memory_db_from_seed(
            runtime_db_path=self.runtime_path,
            seed_db_path=self.seed_path,
        )
        self.assertEqual(result.get("status"), "skipped")
        self.assertEqual(result.get("reason"), "seed_missing")
        self.assertTrue(init_memory_db(self.runtime_path))
        self.assertTrue(os.path.exists(self.runtime_path))
        self.assertTrue(self._table_exists(self.runtime_path, "inspiration_profiles"))


if __name__ == "__main__":
    unittest.main()
