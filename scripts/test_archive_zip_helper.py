#!/usr/bin/env python3
"""Smoke tests for archive zip helper (PR2 Step 1.1)"""

import os
import sys
import tempfile
import shutil
import zipfile
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updates.save_game_manager import SaveGameManager

def test_valid_save_path():
    """Test: Valid save path -> helper returns success, zip_path exists, bytes > 0"""
    print("\n[Test 1] Valid save path generates archive zip...")
    
    manager = SaveGameManager()
    
    # Create temporary save folder with sample files
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_test")
        os.makedirs(save_path)
        
        # Create sample files
        with open(os.path.join(save_path, "test_file.json"), "w") as f:
            f.write('{"test": "data"}')
        
        subdir = os.path.join(save_path, "subdir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "nested.txt"), "w") as f:
            f.write("nested content")
        
        # Metadata with timestamp
        metadata = {
            "save_timestamp": datetime.now().isoformat(),
            "save_id": "test-uuid-123"
        }
        
        # Call helper
        success, result = manager._generate_archive_zip(save_path, metadata)
        
        # Verify success
        assert success is True, f"Expected success=True, got {success}"
        assert result["status"] == "success", f"Expected status=success, got {result['status']}"
        assert "zip_path" in result, "Missing zip_path in result"
        assert "zip_name" in result, "Missing zip_name in result"
        assert "bytes" in result, "Missing bytes in result"
        assert result["bytes"] > 0, f"Expected bytes > 0, got {result['bytes']}"
        assert os.path.exists(result["zip_path"]), f"Zip file does not exist: {result['zip_path']}"
        
        print(f"  [OK] Success: zip_path={result['zip_path']}")
        print(f"  [OK] Bytes: {result['bytes']}")
        
        return result["zip_path"]

def test_invalid_save_path():
    """Test: Invalid save path -> helper returns clean error result"""
    print("\n[Test 2] Invalid save path returns clean error...")
    
    manager = SaveGameManager()
    
    # Non-existent path
    success, result = manager._generate_archive_zip("/nonexistent/path/save_123", {})
    
    assert success is False, f"Expected success=False, got {success}"
    assert result["status"] == "error", f"Expected status=error, got {result['status']}"
    assert "message" in result, "Missing message in error result"
    assert "does not exist" in result["message"].lower() or "not exist" in result["message"].lower(), \
        f"Expected 'does not exist' in message, got: {result['message']}"
    
    print(f"  [OK] Error returned: {result['message']}")

def test_zip_integrity():
    """Test: Zip integrity check - open with zipfile and run testzip() == None"""
    print("\n[Test 3] Zip integrity verification...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_integrity")
        os.makedirs(save_path)
        
        # Create various file types
        with open(os.path.join(save_path, "data.json"), "w") as f:
            f.write('{"key": "value"}')
        
        nested_dir = os.path.join(save_path, "nested", "deep")
        os.makedirs(nested_dir)
        with open(os.path.join(nested_dir, "file.txt"), "w") as f:
            f.write("deep nested content")
        
        metadata = {
            "save_timestamp": datetime.now().isoformat()
        }
        
        success, result = manager._generate_archive_zip(save_path, metadata)
        
        assert success is True, f"Zip generation failed: {result}"
        
        # Verify with zipfile
        with zipfile.ZipFile(result["zip_path"], 'r') as zf:
            integrity_result = zf.testzip()
            assert integrity_result is None, f"Zip integrity check failed: {integrity_result}"
            
            # Verify contents preserved structure
            namelist = zf.namelist()
            print(f"  [OK] Zip contents: {namelist}")
            
            # Check files exist in zip
            assert any("data.json" in name for name in namelist), "data.json not in zip"
            assert any("file.txt" in name for name in namelist), "file.txt not in zip"
        
        print(f"  [OK] Zip integrity verified (testzip() == None)")

def test_deterministic_naming():
    """Test: Zip name is deterministic from timestamp"""
    print("\n[Test 4] Deterministic zip naming...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_deterministic")
        os.makedirs(save_path)
        
        with open(os.path.join(save_path, "file.txt"), "w") as f:
            f.write("content")
        
        # Fixed timestamp
        fixed_timestamp = "2024-03-15T14:30:45.123456"
        metadata = {"save_timestamp": fixed_timestamp}
        
        success, result = manager._generate_archive_zip(save_path, metadata)
        
        assert success is True
        # Should create archive_20240315_143045.zip
        expected_name = "archive_20240315_143045.zip"
        assert result["zip_name"] == expected_name, \
            f"Expected zip_name={expected_name}, got {result['zip_name']}"
        
        print(f"  [OK] Deterministic name: {result['zip_name']}")

def test_no_mutation():
    """Test: Helper does not mutate save folder contents (zip is sibling artifact)"""
    print("\n[Test 5] Save folder not mutated...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_no_mutate")
        os.makedirs(save_path)
        
        # Create original file
        original_file = os.path.join(save_path, "original.txt")
        with open(original_file, "w") as f:
            f.write("original content")
        
        # Record original state
        original_files = set(os.listdir(save_path))
        original_mtime = os.path.getmtime(original_file)
        original_filename = os.path.basename(original_file)
        
        metadata = {"save_timestamp": datetime.now().isoformat()}
        success, result = manager._generate_archive_zip(save_path, metadata)
        
        assert success is True
        
        # Verify no mutation
        final_files = set(os.listdir(save_path))
        assert original_filename in final_files, "Original file was removed"
        assert os.path.getmtime(original_file) == original_mtime, "Original file was modified"
        
        # Zip is sibling artifact, so save folder should be unchanged
        assert final_files == original_files, f"Save folder was mutated: {final_files - original_files}"
        
        # Zip should be in parent directory
        zip_in_parent = os.path.exists(os.path.join(tmpdir, result["zip_name"]))
        assert zip_in_parent, "Zip not found in parent directory"
        
        print(f"  [OK] No mutation: original preserved, zip is sibling artifact")

if __name__ == "__main__":
    print("=" * 60)
    print("Archive Zip Helper Smoke Tests (PR2 Step 1.1)")
    print("=" * 60)
    
    try:
        test_valid_save_path()
        test_invalid_save_path()
        test_zip_integrity()
        test_deterministic_naming()
        test_no_mutation()
        
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
