#!/usr/bin/env python3
"""Smoke tests for Step 3.1 memory state artifact backup"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import after adding to path
from utils.reset_campaign import create_backup

def test_memory_db_backup_when_present():
    """Test: Memory DB is backed up when present"""
    print("\n[Test 1] Memory DB backup when present...")
    
    # Create temp directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Create required directories and files
            os.makedirs("modules", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            
            # Create a mock memory.db
            with open("data/memory.db", "w") as f:
                f.write("mock memory database content")
            
            # Create required files for backup
            with open("party_tracker.json", "w") as f:
                f.write("{}")
            with open("journal.json", "w") as f:
                f.write("{}")
            with open("current_location.json", "w") as f:
                f.write("{}")
            
            # Run backup
            backup_dir = create_backup()
            
            # Verify memory.db was backed up
            memory_backup_path = os.path.join(backup_dir, "data", "memory.db")
            assert os.path.exists(memory_backup_path), f"Memory DB not found at {memory_backup_path}"
            
            # Verify content was preserved
            with open(memory_backup_path, "r") as f:
                content = f.read()
            assert content == "mock memory database content", "Memory DB content mismatch"
            
            print(f"  [OK] Memory DB backed up to {memory_backup_path}")
            
        finally:
            os.chdir(original_cwd)

def test_no_memory_db_backup_when_absent():
    """Test: Backup succeeds when memory DB is absent"""
    print("\n[Test 2] Backup succeeds without memory DB...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Create required directories (but NOT data/memory.db)
            os.makedirs("modules", exist_ok=True)
            
            # Create required files
            with open("party_tracker.json", "w") as f:
                f.write("{}")
            with open("journal.json", "w") as f:
                f.write("{}")
            with open("current_location.json", "w") as f:
                f.write("{}")
            
            # Verify memory.db does NOT exist
            assert not os.path.exists("data/memory.db"), "Memory DB should not exist for this test"
            
            # Run backup - should succeed even without memory.db
            backup_dir = create_backup()
            
            # Verify backup succeeded
            assert os.path.exists(backup_dir), "Backup directory not created"
            
            # Verify no memory.db in backup
            memory_backup_path = os.path.join(backup_dir, "data", "memory.db")
            assert not os.path.exists(memory_backup_path), "Memory DB should not exist in backup"
            
            print(f"  [OK] Backup succeeded without memory DB")
            
        finally:
            os.chdir(original_cwd)

def test_backup_directory_structure():
    """Test: Memory DB is backed up to correct location"""
    print("\n[Test 3] Memory DB backup location...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Setup
            os.makedirs("modules", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            
            with open("data/memory.db", "w") as f:
                f.write("test")
            with open("party_tracker.json", "w") as f:
                f.write("{}")
            with open("journal.json", "w") as f:
                f.write("{}")
            with open("current_location.json", "w") as f:
                f.write("{}")
            
            # Run backup
            backup_dir = create_backup()
            
            # Verify exact path
            expected_path = os.path.join(backup_dir, "data", "memory.db")
            assert os.path.exists(expected_path), f"Expected {expected_path} to exist"
            
            print(f"  [OK] Memory DB at correct path: {expected_path}")
            
        finally:
            os.chdir(original_cwd)

def test_other_files_still_backed_up():
    """Test: Existing backup items are still copied"""
    print("\n[Test 4] Existing backup items preserved...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Setup with memory.db and other files
            os.makedirs("modules", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            
            with open("data/memory.db", "w") as f:
                f.write("memory")
            with open("party_tracker.json", "w") as f:
                f.write('{"party": "test"}')
            with open("journal.json", "w") as f:
                f.write('{"entries": []}')
            with open("current_location.json", "w") as f:
                f.write('{"location": "test"}')
            
            # Run backup
            backup_dir = create_backup()
            
            # Verify all expected files exist
            assert os.path.exists(os.path.join(backup_dir, "data", "memory.db")), "Memory DB missing"
            assert os.path.exists(os.path.join(backup_dir, "party_tracker.json")), "party_tracker.json missing"
            assert os.path.exists(os.path.join(backup_dir, "journal.json")), "journal.json missing"
            assert os.path.exists(os.path.join(backup_dir, "current_location.json")), "current_location.json missing"
            
            print(f"  [OK] All files backed up including memory DB")
            
        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    print("=" * 60)
    print("Step 3.1 Memory State Artifact Backup Tests")
    print("=" * 60)
    
    try:
        test_memory_db_backup_when_present()
        test_no_memory_db_backup_when_absent()
        test_backup_directory_structure()
        test_other_files_still_backed_up()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[FAIL] Test assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
