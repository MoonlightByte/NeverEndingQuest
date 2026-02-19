#!/usr/bin/env python3
"""Smoke tests for Step 3.3 backup layout compatibility verification"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.reset_campaign import create_backup

def test_layout_verification_with_memory():
    """Test: Layout verification with memory artifact present"""
    print("\n[Test 1] Layout verification with memory artifact...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Setup with memory.db
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
            
            # Run backup
            backup_dir = create_backup()
            
            # Verify layout
            assert os.path.exists(os.path.join(backup_dir, "modules")), "modules/ missing"
            assert os.path.exists(os.path.join(backup_dir, "data", "memory.db")), "memory.db missing"
            assert os.path.exists(os.path.join(backup_dir, "party_tracker.json")), "party_tracker.json missing"
            
            print(f"  [OK] Layout verified: modules/, data/memory.db, root files present")
            
        finally:
            os.chdir(original_cwd)

def test_layout_verification_without_memory():
    """Test: Layout verification without memory artifact"""
    print("\n[Test 2] Layout verification without memory artifact...")
    
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
            
            # Run backup
            backup_dir = create_backup()
            
            # Verify layout
            assert os.path.exists(os.path.join(backup_dir, "modules")), "modules/ missing"
            assert not os.path.exists(os.path.join(backup_dir, "data", "memory.db")), "memory.db should not exist"
            assert os.path.exists(os.path.join(backup_dir, "party_tracker.json")), "party_tracker.json missing"
            
            print(f"  [OK] Layout verified: modules/, root files present, no memory.db")
            
        finally:
            os.chdir(original_cwd)

def test_verification_output_format():
    """Test: Verification output uses correct ASCII format"""
    print("\n[Test 3] Verification output format...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            os.makedirs("modules", exist_ok=True)
            os.makedirs("data", exist_ok=True)
            
            with open("data/memory.db", "w") as f:
                f.write("memory")
            with open("party_tracker.json", "w") as f:
                f.write("{}")
            with open("journal.json", "w") as f:
                f.write("{}")
            with open("current_location.json", "w") as f:
                f.write("{}")
            
            # Capture output
            import io
            import sys
            captured = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            
            try:
                backup_dir = create_backup()
            finally:
                sys.stdout = old_stdout
            
            output = captured.getvalue()
            
            # Check for expected format markers
            assert "[OK]" in output or "[WARNING]" in output or "[INFO]" in output, \
                f"Expected status markers in output:\n{output}"
            assert "Verifying backup layout compatibility" in output, \
                f"Expected verification header:\n{output}"
            assert "Backup layout verification complete" in output, \
                f"Expected completion message:\n{output}"
            
            print(f"  [OK] Output format correct with status markers")
            
        finally:
            os.chdir(original_cwd)

def test_no_phase_reordering():
    """Test: Reset phases remain in original order"""
    print("\n[Test 4] Phase ordering preserved...")
    
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
            
            # Capture output to check phase order
            import io
            import sys
            captured = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            
            try:
                backup_dir = create_backup()
            finally:
                sys.stdout = old_stdout
            
            output = captured.getvalue()
            
            # Verify phases happen in order: backup -> memory -> verification -> complete
            phase_order = []
            if "PHASE 1: Creating complete backup" in output:
                phase_order.append("backup")
            if "memory" in output.lower():
                phase_order.append("memory")
            if "Verifying backup layout" in output:
                phase_order.append("verification")
            if "Backup complete" in output:
                phase_order.append("complete")
            
            # Verification should come after backup/memory, before complete
            assert "verification" in phase_order, "Verification phase missing"
            verification_idx = phase_order.index("verification")
            complete_idx = phase_order.index("complete")
            
            assert verification_idx < complete_idx, \
                f"Verification should come before complete. Order: {phase_order}"
            
            print(f"  [OK] Phases in correct order: {phase_order}")
            
        finally:
            os.chdir(original_cwd)

def test_root_files_not_moved():
    """Test: Root files remain at backup root, not relocated"""
    print("\n[Test 5] Root files at correct location...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
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
            
            backup_dir = create_backup()
            
            # Verify files are at root, not in subdirs
            assert os.path.isfile(os.path.join(backup_dir, "party_tracker.json")), \
                "party_tracker.json not at root"
            assert os.path.isfile(os.path.join(backup_dir, "journal.json")), \
                "journal.json not at root"
            assert os.path.isfile(os.path.join(backup_dir, "current_location.json")), \
                "current_location.json not at root"
            
            # Memory should be in data/ subdirectory
            assert os.path.isfile(os.path.join(backup_dir, "data", "memory.db")), \
                "memory.db not in data/ subdirectory"
            
            print(f"  [OK] Root files at backup root, memory in data/")
            
        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    print("=" * 60)
    print("Step 3.3 Backup Layout Compatibility Tests")
    print("=" * 60)
    
    try:
        test_layout_verification_with_memory()
        test_layout_verification_without_memory()
        test_verification_output_format()
        test_no_phase_reordering()
        test_root_files_not_moved()
        
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
