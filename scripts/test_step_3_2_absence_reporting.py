#!/usr/bin/env python3
"""Smoke tests for Step 3.2 memory artifact absence reporting"""

import os
import sys
import tempfile
import shutil
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.reset_campaign import create_backup

def test_memory_absence_reporting():
    """Test: Absence of memory DB is reported but non-fatal"""
    print("\n[Test 1] Memory absence reporting...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Setup without memory.db
            os.makedirs("modules", exist_ok=True)
            
            with open("party_tracker.json", "w") as f:
                f.write("{}")
            with open("journal.json", "w") as f:
                f.write("{}")
            with open("current_location.json", "w") as f:
                f.write("{}")
            
            # Verify memory.db does NOT exist
            assert not os.path.exists("data/memory.db"), "Memory DB should not exist for this test"
            
            # Capture stdout to check for absence message
            import io
            import sys
            captured_output = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured_output
            
            try:
                # Run backup
                backup_dir = create_backup()
            finally:
                sys.stdout = old_stdout
            
            output = captured_output.getvalue()
            
            # Verify backup succeeded
            assert os.path.exists(backup_dir), "Backup directory not created"
            
            # Verify absence message appears
            assert "not present" in output.lower() or "memory state artifact" in output.lower(), \
                f"Expected absence reporting in output, got:\n{output}"
            
            # Verify backup completed message
            assert "[OK] Backup complete" in output, f"Expected backup completion message, got:\n{output}"
            
            print(f"  [OK] Absence reported and backup completed")
            print(f"  Output snippet: ...{output.split('Memory state')[1][:80]}...")
            
        finally:
            os.chdir(original_cwd)

def test_memory_presence_with_absence():
    """Test: When present, backup occurs; when absent, reported"""
    print("\n[Test 2] Memory presence vs absence behavior...")
    
    # Test 2a: With memory.db
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            os.makedirs("modules", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            
            with open("data/memory.db", "w") as f:
                f.write("memory content")
            with open("party_tracker.json", "w") as f:
                f.write("{}")
            with open("journal.json", "w") as f:
                f.write("{}")
            with open("current_location.json", "w") as f:
                f.write("{}")
            
            import io
            import sys
            captured_output = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured_output
            
            try:
                backup_dir = create_backup()
            finally:
                sys.stdout = old_stdout
            
            output = captured_output.getvalue()
            
            # Verify backed up
            assert os.path.exists(os.path.join(backup_dir, "data", "memory.db")), "Memory DB not backed up"
            assert "backed up" in output.lower(), f"Expected backup message, got:\n{output}"
            
            print(f"  [OK] With memory.db: backed up successfully")
            
        finally:
            os.chdir(original_cwd)
    
    # Test 2b: Without memory.db
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            os.makedirs("modules", exist_ok=True)
            
            with open("party_tracker.json", "w") as f:
                f.write("{}")
            with open("journal.json", "w") as f:
                f.write("{}")
            with open("current_location.json", "w") as f:
                f.write("{}")
            
            import io
            import sys
            captured_output = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured_output
            
            try:
                backup_dir = create_backup()
            finally:
                sys.stdout = old_stdout
            
            output = captured_output.getvalue()
            
            # Verify NOT backed up but reported
            assert not os.path.exists(os.path.join(backup_dir, "data", "memory.db")), "Memory DB should not exist"
            assert "not present" in output.lower(), f"Expected absence message, got:\n{output}"
            
            print(f"  [OK] Without memory.db: absence reported, backup succeeded")
            
        finally:
            os.chdir(original_cwd)

def test_exact_absence_message():
    """Test: Exact message text for absence reporting"""
    print("\n[Test 3] Exact absence message text...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            os.makedirs("modules", exist_ok=True)
            
            with open("party_tracker.json", "w") as f:
                f.write("{}")
            with open("journal.json", "w") as f:
                f.write("{}")
            with open("current_location.json", "w") as f:
                f.write("{}")
            
            import io
            import sys
            captured_output = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured_output
            
            try:
                backup_dir = create_backup()
            finally:
                sys.stdout = old_stdout
            
            output = captured_output.getvalue()
            
            # Verify exact message format
            expected_fragment = "Memory state artifact not present"
            assert expected_fragment in output, f"Expected '{expected_fragment}' in output, got:\n{output}"
            
            # Verify non-fatal continuation
            assert "continuing backup" in output.lower() or "Backup complete" in output, \
                f"Expected continuation indication, got:\n{output}"
            
            print(f"  [OK] Exact message: '{expected_fragment}'")
            
        finally:
            os.chdir(original_cwd)

def test_backup_completes_without_memory():
    """Test: Backup completes successfully even without memory DB"""
    print("\n[Test 4] Backup completion without memory DB...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            os.makedirs("modules", exist_ok=True)
            
            with open("party_tracker.json", "w") as f:
                f.write('{"test": "data"}')
            with open("journal.json", "w") as f:
                f.write('{"entries": []}')
            with open("current_location.json", "w") as f:
                f.write('{"location": "test"}')
            
            # Run backup
            backup_dir = create_backup()
            
            # Verify backup dir and key files exist
            assert os.path.exists(backup_dir), "Backup directory not created"
            assert os.path.exists(os.path.join(backup_dir, "party_tracker.json")), "party_tracker.json missing"
            assert os.path.exists(os.path.join(backup_dir, "journal.json")), "journal.json missing"
            
            # Verify memory db NOT present
            assert not os.path.exists(os.path.join(backup_dir, "data", "memory.db")), "Memory DB should not exist"
            
            print(f"  [OK] Backup completed without memory DB")
            
        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    print("=" * 60)
    print("Step 3.2 Memory Artifact Absence Reporting Tests")
    print("=" * 60)
    
    try:
        test_memory_absence_reporting()
        test_memory_presence_with_absence()
        test_exact_absence_message()
        test_backup_completes_without_memory()
        
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
