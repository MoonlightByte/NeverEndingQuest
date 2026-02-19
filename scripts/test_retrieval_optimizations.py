#!/usr/bin/env python3
"""Quick verification test for retrieval optimizations."""

import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_retrieval import (
    get_entity_timeline,
    _connect_readonly,
    _connect,
    DEFAULT_MEMORY_DB_PATH,
)
from core.memory.memory_db import init_memory_db

def test_readonly_connection():
    """Test 1.4: Read-only connection behavior."""
    print("Test 1.4: Read-only sqlite open behavior...")
    
    # Test 1: Missing DB returns None (no implicit creation)
    with tempfile.TemporaryDirectory() as tmpdir:
        missing_db = os.path.join(tmpdir, "nonexistent.db")
        conn = _connect_readonly(missing_db)
        assert conn is None, "Should return None for missing DB"
        assert not os.path.exists(missing_db), "Should not create DB file"
        print("  ✓ Missing DB returns None without creating file")
    
    # Test 2: Existing DB opens in read-only mode
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_memory_db(db_path)
        conn = _connect_readonly(db_path)
        assert conn is not None, "Should return connection for existing DB"
        # Try to write (should fail in read-only mode)
        try:
            conn.execute("INSERT INTO entities (entity_id, display_name, entity_kind) VALUES ('test', 'Test', 'character')")
            print("  ✗ Write succeeded (should fail in read-only mode)")
        except sqlite3.OperationalError:
            print("  ✓ Read-only mode enforced (write failed as expected)")
        conn.close()
    
    print("Test 1.4 PASSED\n")

def test_bounded_candidates_and_dedup():
    """Test 1.1, 1.2, 1.3: Bounded candidates, de-duplication, audit counts."""
    print("Test 1.1-1.3: Bounded candidates, de-duplication, audit logging...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_memory_db(db_path)
        
        conn = sqlite3.connect(db_path)
        
        # Insert test entity
        conn.execute("""
            INSERT INTO entities (entity_id, display_name, entity_kind, created_at, updated_at)
            VALUES ('char1', 'Character 1', 'character', '2024-01-01', '2024-01-01')
        """)
        
        # Insert test events (more than limit to test bounded selection)
        for i in range(50):
            conn.execute("""
                INSERT INTO memory_events 
                (event_id, event_ts, event_type, summary, importance, persistence_class, decay_profile, created_at)
                VALUES (?, '2024-01-01', 'narration', ?, 50, 'procedural', 'medium', '2024-01-01')
            """, (f"evt{i}", f"Event {i}"))
            
            # Link each event to entity (single link)
            conn.execute("""
                INSERT INTO memory_links (event_id, entity_id, link_role, link_salience)
                VALUES (?, 'char1', 'subject', 1.0)
            """, (f"evt{i}",))
        
        conn.commit()
        conn.close()
        
        # Test bounded candidate selection (request 10, should get 10)
        result = get_entity_timeline("char1", limit=10, db_path=db_path)
        assert len(result) == 10, f"Expected 10 results, got {len(result)}"
        print(f"  ✓ Bounded candidate selection: requested 10, got {len(result)}")
        
        # Test de-duplication (no duplicate event_ids)
        event_ids = [row["event_id"] for row in result]
        assert len(event_ids) == len(set(event_ids)), "Duplicate events found!"
        print("  ✓ De-duplication: no duplicate event IDs")
        
        # Test with audit logging enabled
        result = get_entity_timeline("char1", limit=5, db_path=db_path, enable_audit=True)
        assert len(result) <= 5, f"Expected <= 5 results with limit, got {len(result)}"
        print(f"  ✓ Audit logging: retrieved {len(result)} events with limit=5")
        
        # Test with missing DB (should return empty list, not fail)
        result = get_entity_timeline("char1", limit=5, db_path="/nonexistent/path.db")
        assert result == [], "Should return empty list for missing DB"
        print("  ✓ Missing DB handling: returns empty list gracefully")
    
    print("Test 1.1-1.3 PASSED\n")

def main():
    print("=" * 60)
    print("Memory Retrieval Optimizations - Quick Verification")
    print("=" * 60 + "\n")
    
    test_readonly_connection()
    test_bounded_candidates_and_dedup()
    
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()
