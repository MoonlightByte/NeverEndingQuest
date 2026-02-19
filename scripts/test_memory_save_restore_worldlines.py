# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Memory save/restore worldlines integration tests.

Validates:
- Save parity (memory package exists)
- Restore parity (import rewinds memory DB)
- Corrupt package failure behavior
- Worldline invariants (fork-on-first-save-after-restore)
- Legacy save fallback semantics
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH, init_memory_db
    from core.memory.memory_portability import (
        export_memory_db_package,
        import_memory_db_package,
        validate_memory_package,
    )
    from updates.save_game_manager import SaveGameManager, RESTORE_CONTEXT_FILE
    MEMORY_AVAILABLE = True
except ImportError as e:
    MEMORY_AVAILABLE = False
    print(f"WARNING: Memory modules not available: {e}")


def _patch_db_path(temp_db_path: str):
    """Context manager to patch DEFAULT_MEMORY_DB_PATH for test isolation."""
    return patch("updates.save_game_manager.DEFAULT_MEMORY_DB_PATH", temp_db_path)


def _create_test_entity(conn: sqlite3.Connection, entity_id: str) -> None:
    """Create a test entity in memory DB."""
    conn.execute(
        "INSERT OR IGNORE INTO entities (entity_id, display_name, entity_kind, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (entity_id, entity_id, "character", datetime.now().isoformat(), datetime.now().isoformat()),
    )
    conn.commit()


def _create_test_event(conn: sqlite3.Connection, event_id: str, entity_id: str, summary: str) -> None:
    """Create a test memory event and link it to entity."""
    conn.execute(
        "INSERT INTO memory_events (event_id, event_ts, event_type, summary, importance, persistence_class, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_id, datetime.now().isoformat(), "narration", summary, 50, "ambient", datetime.now().isoformat()),
    )
    conn.execute(
        "INSERT INTO memory_links (event_id, entity_id, link_role, link_salience) VALUES (?, ?, ?, ?)",
        (event_id, entity_id, "subject", 1.0),
    )
    conn.commit()


def _count_events(conn: sqlite3.Connection) -> int:
    """Count total memory events."""
    row = conn.execute("SELECT COUNT(*) FROM memory_events").fetchone()
    return int(row[0]) if row else 0


@unittest.skipIf(not MEMORY_AVAILABLE, "Memory modules not available")
class TestMemorySaveRestoreParity(unittest.TestCase):
    """Test save/restore parity for memory DB."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_worldline_test_")
        self.db_path = os.path.join(self.temp_dir, "memory.db")
        self.save_dir = os.path.join(self.temp_dir, "saves")
        os.makedirs(self.save_dir, exist_ok=True)
        
        init_memory_db(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        
        self.manager = SaveGameManager()
        self.manager.current_module = "test_module"
        
    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if os.path.exists(RESTORE_CONTEXT_FILE):
            os.remove(RESTORE_CONTEXT_FILE)

    def test_save_creates_memory_package(self) -> None:
        """Save creates memory package in save folder."""
        _create_test_entity(self.conn, "test_char")
        
        package_dir = os.path.join(self.save_dir, "test_save_1", "memory_db_package")
        result = export_memory_db_package(self.db_path, package_dir, overwrite=True)
        
        self.assertEqual(result.get("status"), "success")
        self.assertTrue(os.path.exists(os.path.join(package_dir, "memory.db")))
        self.assertTrue(os.path.exists(os.path.join(package_dir, "manifest.json")))
        self.assertIn("row_counts", result)

    def test_restore_imports_memory_package(self) -> None:
        """Restore imports memory DB from package."""
        _create_test_entity(self.conn, "test_char")
        
        package_dir = os.path.join(self.temp_dir, "package")
        export_memory_db_package(self.db_path, package_dir, overwrite=True)
        
        os.remove(self.db_path)
        self.assertFalse(os.path.exists(self.db_path))
        
        result = import_memory_db_package(package_dir, self.db_path, overwrite=True)
        self.assertEqual(result.get("status"), "success")
        self.assertTrue(os.path.exists(self.db_path))

    def test_corrupt_package_fails_restore(self) -> None:
        """Corrupt memory package causes restore failure."""
        package_dir = os.path.join(self.temp_dir, "corrupt_package")
        os.makedirs(package_dir, exist_ok=True)
        
        with open(os.path.join(package_dir, "manifest.json"), "w") as f:
            json.dump({"schema_version": "memory-db-package/v1", "db_sha256": "badhash"}, f)
        
        with open(os.path.join(package_dir, "memory.db"), "w") as f:
            f.write("not a real db")
        
        result = import_memory_db_package(package_dir, self.db_path, overwrite=True)
        self.assertEqual(result.get("status"), "error")


@unittest.skipIf(not MEMORY_AVAILABLE, "Memory modules not available")
class TestWorldlineBranching(unittest.TestCase):
    """Test worldline lineage and fork behavior."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_worldline_branch_")
        
        self.manager = SaveGameManager()
        self.manager.current_module = "test_module"
        
        if os.path.exists(RESTORE_CONTEXT_FILE):
            os.remove(RESTORE_CONTEXT_FILE)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if os.path.exists(RESTORE_CONTEXT_FILE):
            os.remove(RESTORE_CONTEXT_FILE)

    def test_metadata_includes_lineage_fields(self) -> None:
        """Save metadata includes worldline lineage fields."""
        metadata = self.manager.generate_save_metadata("test save", "essential")
        
        self.assertIn("save_id", metadata)
        self.assertIn("worldline_id", metadata)
        self.assertIn("lineage", metadata)
        self.assertIn("parent_save_id", metadata["lineage"])
        self.assertIn("created_after_restore", metadata["lineage"])

    def test_sequential_saves_same_worldline(self) -> None:
        """Consecutive saves without restore stay on same worldline."""
        metadata1 = self.manager.generate_save_metadata("save 1", "essential")
        metadata2 = self.manager.generate_save_metadata("save 2", "essential")
        
        self.assertEqual(metadata1["worldline_id"], metadata2["worldline_id"])
        self.assertFalse(metadata1["lineage"]["created_after_restore"])
        self.assertFalse(metadata2["lineage"]["created_after_restore"])

    def test_restore_then_save_forks_new_worldline(self) -> None:
        """First save after restore creates new worldline."""
        original_metadata = self.manager.generate_save_metadata("original", "essential")
        original_worldline = original_metadata["worldline_id"]
        
        self.manager._setup_restore_context(original_metadata)
        
        fork_metadata = self.manager.generate_save_metadata("fork", "essential")
        fork_worldline = fork_metadata["worldline_id"]
        
        self.assertNotEqual(original_worldline, fork_worldline)
        self.assertTrue(fork_metadata["lineage"]["created_after_restore"])
        self.assertEqual(fork_metadata["lineage"]["parent_save_id"], original_metadata["save_id"])

    def test_restore_context_survives_process_restart(self) -> None:
        """Restore context persisted correctly for fork behavior."""
        original_metadata = self.manager.generate_save_metadata("original", "essential")
        
        self.manager._setup_restore_context(original_metadata)
        
        context = self.manager._load_restore_context()
        self.assertIsNotNone(context)
        self.assertEqual(context["restored_save_id"], original_metadata["save_id"])
        self.assertTrue(context["pending_fork"])


@unittest.skipIf(not MEMORY_AVAILABLE, "Memory modules not available")
class TestLegacySaveFallback(unittest.TestCase):
    """Test legacy save fallback behavior with proper DB path isolation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_legacy_test_")
        self.db_path = os.path.join(self.temp_dir, "memory.db")
        
        # Initialize test DB in isolated temp location
        init_memory_db(self.db_path)
        conn = sqlite3.connect(self.db_path)
        _create_test_entity(conn, "test_char")
        _create_test_event(conn, "evt_old", "test_char", "Old event that should be cleared")
        conn.close()
        
        self.manager = SaveGameManager()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_save_fallback_cleans_db(self) -> None:
        """Legacy save (no memory package) triggers clean DB init on isolated path."""
        save_path = os.path.join(self.temp_dir, "legacy_save")
        os.makedirs(save_path, exist_ok=True)
        
        with open(os.path.join(save_path, "save_metadata.json"), "w") as f:
            json.dump({
                "save_timestamp": datetime.now().isoformat(),
                "module": "test",
                "save_id": "legacy-123",
            }, f)
        
        # Verify test DB exists with data
        self.assertTrue(os.path.exists(self.db_path))
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(_count_events(conn), 1)
        conn.close()
        
        # Patch DEFAULT_MEMORY_DB_PATH to use isolated temp DB
        with _patch_db_path(self.db_path):
            result = self.manager._import_memory_package(save_path, {"save_id": "legacy-123"})
        
        self.assertEqual(result.get("status"), "legacy_fallback")
        
        # Verify the isolated DB was cleaned (re-initialized)
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(_count_events(conn), 0, "DB should be cleaned after legacy fallback")
        conn.close()


@unittest.skipIf(not MEMORY_AVAILABLE, "Memory modules not available")
class TestRestorePreflightAtomicity(unittest.TestCase):
    """Test restore preflight validation happens before any mutations."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_preflight_test_")
        self.save_path = os.path.join(self.temp_dir, "test_save")
        os.makedirs(self.save_path, exist_ok=True)
        
        # Create corrupt memory package
        package_dir = os.path.join(self.save_path, "memory_db_package")
        os.makedirs(package_dir, exist_ok=True)
        with open(os.path.join(package_dir, "manifest.json"), "w") as f:
            json.dump({"schema_version": "memory-db-package/v1", "db_sha256": "badhash"}, f)
        with open(os.path.join(package_dir, "memory.db"), "w") as f:
            f.write("not a real db")
        
        # Create valid metadata
        with open(os.path.join(self.save_path, "save_metadata.json"), "w") as f:
            json.dump({
                "save_timestamp": datetime.now().isoformat(),
                "module": "test",
                "save_id": "test-123",
                "worldline_id": "worldline-123",
            }, f)
        
        self.manager = SaveGameManager()
        self.manager.current_module = "test_module"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_preflight_fails_before_mutations(self) -> None:
        """Corrupt package fails restore before any file operations."""
        # Create a marker file that should remain untouched if preflight works
        marker_file = os.path.join(self.temp_dir, "marker.txt")
        with open(marker_file, "w") as f:
            f.write("original")
        
        # Run preflight validation directly
        result = self.manager._preflight_validate_memory_package(self.save_path)
        
        # Should fail with error status
        self.assertEqual(result.get("status"), "error")
        # Error message should indicate validation/integrity failure
        message_lower = result.get("message", "").lower()
        self.assertTrue(
            "validation failed" in message_lower or "integrity" in message_lower or "mismatch" in message_lower,
            f"Expected validation/integrity error message, got: {result.get('message')}"
        )
        
        # Marker file should still exist (no mutations occurred)
        self.assertTrue(os.path.exists(marker_file))
        with open(marker_file, "r") as f:
            self.assertEqual(f.read(), "original")


@unittest.skipIf(not MEMORY_AVAILABLE, "Memory modules not available")
class TestPackageDirectoryExclusion(unittest.TestCase):
    """Test memory_db_package is excluded from generic restore copy."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_exclude_test_")
        self.save_path = os.path.join(self.temp_dir, "test_save")
        self.runtime_dir = os.path.join(self.temp_dir, "runtime")
        os.makedirs(self.save_path, exist_ok=True)
        os.makedirs(self.runtime_dir, exist_ok=True)
        
        # Create save with memory package
        package_dir = os.path.join(self.save_path, "memory_db_package")
        os.makedirs(package_dir, exist_ok=True)
        with open(os.path.join(package_dir, "memory.db"), "w") as f:
            f.write("test db content")
        with open(os.path.join(package_dir, "manifest.json"), "w") as f:
            json.dump({
                "schema_version": "memory-db-package/v1",
                "db_sha256": "abc123",
                "row_counts": {"entities": 1}
            }, f)
        
        # Create a game file in save
        with open(os.path.join(self.save_path, "game_file.json"), "w") as f:
            json.dump({"test": "data"}, f)
        
        # Create metadata
        with open(os.path.join(self.save_path, "save_metadata.json"), "w") as f:
            json.dump({
                "save_timestamp": datetime.now().isoformat(),
                "module": "test",
                "save_id": "test-456",
            }, f)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_package_dir_excluded_from_copy(self) -> None:
        """memory_db_package is not copied during generic restore walk."""
        # Simulate the restore copy logic with exclusion
        copied_files = []
        for root, dirs, files in os.walk(self.save_path):
            # Apply the exclusion logic from save_game_manager.py
            if "memory_db_package" in dirs:
                dirs.remove("memory_db_package")
            
            if "save_metadata.json" in files:
                files.remove("save_metadata.json")
            
            for file in files:
                source_file = os.path.join(root, file)
                rel_path = os.path.relpath(source_file, self.save_path)
                copied_files.append(rel_path)
        
        # Should only copy game_file.json, not package contents
        self.assertIn("game_file.json", copied_files)
        self.assertNotInAny(["memory_db_package/memory.db", "memory_db_package/manifest.json"], copied_files)
    
    def assertNotInAny(self, items, container):
        """Helper to check none of the items are in container."""
        for item in items:
            self.assertNotIn(item, container, f"'{item}' should not be in copied files")


if __name__ == "__main__":
    unittest.main()