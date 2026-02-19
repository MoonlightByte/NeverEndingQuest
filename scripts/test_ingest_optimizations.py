#!/usr/bin/env python3
"""Quick verification test for ingest optimizations (Section 2)."""

import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_ingest import (
    ingest_journal_entry,
    ingest_journal_entries_batch,
    _resolve_entry_timestamp,
    backfill_memory_db_from_histories,
)
from core.memory.memory_db import init_memory_db

def test_timestamp_precedence():
    """Test 2.3: Timestamp precedence logic."""
    print("Test 2.3: Timestamp precedence logic...")
    
    # Test entry_ts takes precedence
    entry = {"entry_ts": "2024-01-15T10:00:00Z", "timestamp": "2024-02-01T00:00:00Z"}
    result = _resolve_entry_timestamp(entry)
    assert result == "2024-01-15T10:00:00Z", f"entry_ts should win, got {result}"
    
    # Test timestamp used when entry_ts missing
    entry = {"timestamp": "2024-03-01T00:00:00Z", "content": "test"}
    result = _resolve_entry_timestamp(entry)
    assert result == "2024-03-01T00:00:00Z", f"timestamp should be used, got {result}"
    
    # Test fallback to now when no timestamps
    entry = {"content": "test"}
    result = _resolve_entry_timestamp(entry)
    assert len(result) > 0, "Should return a valid ISO timestamp"
    assert "T" in result, "Should be ISO format"
    
    print("  ✓ Timestamp precedence working correctly")
    print("Test 2.3 PASSED\n")

def test_shared_connection():
    """Test 2.1: Shared connection reuse."""
    print("Test 2.1: Shared DB connection reuse...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_memory_db(db_path)
        
        # Open shared connection
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Ingest multiple entries using shared connection
        entries = [
            {"entry_ts": f"2024-01-{i:02d}T10:00:00Z", "content": f"Entry {i}"}
            for i in range(1, 6)
        ]
        
        for entry in entries:
            result = ingest_journal_entry(entry, db_path=db_path, conn=conn)
            assert result["status"] == "success", f"Ingest failed: {result}"
        
        # Verify all entries in DB
        cursor = conn.execute("SELECT COUNT(*) FROM journal_entries")
        count = cursor.fetchone()[0]
        assert count == 5, f"Expected 5 entries, got {count}"
        
        conn.close()
        print("  ✓ Shared connection reused successfully")
    
    print("Test 2.1 PASSED\n")

def test_batched_transactions():
    """Test 2.2: Batched transaction boundaries."""
    print("Test 2.2: Batched transaction boundaries...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_memory_db(db_path)
        
        # Create many entries
        entries = [
            {"entry_ts": f"2024-01-{i:02d}T10:00:00Z", "content": f"Batch entry {i}"}
            for i in range(1, 21)
        ]
        
        # Ingest with small batch size
        result = ingest_journal_entries_batch(entries, db_path=db_path, batch_size=5)
        
        assert result["status"] == "success", f"Batch ingest failed: {result}"
        assert result["total"] == 20, f"Expected 20 total, got {result['total']}"
        assert result["ingested"] == 20, f"Expected 20 ingested, got {result['ingested']}"
        assert result["errors"] == 0, f"Expected 0 errors, got {result['errors']}"
        
        # Verify in DB
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM journal_entries")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 20, f"Expected 20 entries in DB, got {count}"
        print("  ✓ Batched transactions working (20 entries in batches of 5)")
    
    print("Test 2.2 PASSED\n")

def test_malformed_entry_tolerance():
    """Test that malformed entries don't break batch."""
    print("Test: Malformed entry tolerance in batches...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_memory_db(db_path)
        
        # Mix valid and invalid entries
        entries = [
            {"entry_ts": "2024-01-01T10:00:00Z", "content": "Valid 1"},
            {"entry_ts": "2024-01-02T10:00:00Z", "content": ""},  # Invalid - empty content
            {"entry_ts": "2024-01-03T10:00:00Z", "content": "Valid 2"},
        ]
        
        result = ingest_journal_entries_batch(entries, db_path=db_path, batch_size=10)
        
        assert result["status"] == "partial", "Should be partial due to error"
        assert result["errors"] >= 1, "Should have at least 1 error"
        assert result["ingested"] >= 2, "Should have at least 2 successful"
        
        print("  ✓ Malformed entries tolerated, batch continued")
    
    print("Test PASSED\n")

def test_backfill_batch_integration():
    """Test 2.4: Backfill with batching integration."""
    print("Test 2.4: Backfill batch integration...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        
        # Create minimal test files
        journal_path = os.path.join(tmpdir, "journal.json")
        with open(journal_path, "w") as f:
            import json
            json.dump([
                {"entry_ts": "2024-01-01T10:00:00Z", "content": f"Journal entry {i}"}
                for i in range(10)
            ], f)
        
        # Create empty conversation files
        conv_path = os.path.join(tmpdir, "conversation.json")
        with open(conv_path, "w") as f:
            json.dump({"conversation_history": []}, f)
        
        combat_path = os.path.join(tmpdir, "combat.json")
        with open(combat_path, "w") as f:
            json.dump({"conversation_history": []}, f)
        
        # Run backfill with small batch size
        result = backfill_memory_db_from_histories(
            db_path=db_path,
            journal_path=journal_path,
            conversation_path=conv_path,
            combat_history_path=combat_path,
            sources=["journal"],
            batch_size=3,  # Small batch to test batching
        )
        
        assert result["status"] == "success", f"Backfill failed: {result}"
        assert result["sources_ingested"]["journal"] == 10, "Should ingest 10 journal entries"
        assert result["events_created"] == 10, "Should create 10 events"
        
        print(f"  ✓ Backfill with batch_size=3: {result['events_created']} events created")
    
    print("Test 2.4 PASSED\n")

def main():
    print("=" * 60)
    print("Memory Ingest/Backfill Optimizations - Section 2 Verification")
    print("=" * 60 + "\n")
    
    test_timestamp_precedence()
    test_shared_connection()
    test_batched_transactions()
    test_malformed_entry_tolerance()
    test_backfill_batch_integration()
    
    print("=" * 60)
    print("ALL SECTION 2 TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()
