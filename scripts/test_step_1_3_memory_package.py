#!/usr/bin/env python3
"""Smoke tests for Step 1.3 memory_db_package inclusion and fail-closed behavior"""

import os
import sys
import tempfile
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updates.save_game_manager import SaveGameManager

def test_memory_package_inclusion():
    """Test: memory_db_package is included in archive when present"""
    print("\n[Test 1] memory_db_package inclusion...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup save folder with memory_db_package
        save_path = os.path.join(tmpdir, "save_with_memory")
        os.makedirs(save_path)
        
        # Create regular save file
        with open(os.path.join(save_path, "save_data.json"), "w") as f:
            f.write('{"save": "data"}')
        
        # Create memory_db_package subdirectory
        memory_package = os.path.join(save_path, "memory_db_package")
        os.makedirs(memory_package)
        with open(os.path.join(memory_package, "manifest.json"), "w") as f:
            f.write('{"manifest": "data"}')
        
        # Create nested structure in memory package
        memory_subdir = os.path.join(memory_package, "entities")
        os.makedirs(memory_subdir)
        with open(os.path.join(memory_subdir, "data.json"), "w") as f:
            f.write('{"entity": "data"}')
        
        metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
        success, result = manager._generate_archive_zip(save_path, metadata)
        
        assert success is True, f"Expected success, got: {result}"
        
        # Verify memory_db_package in archive
        with zipfile.ZipFile(result["zip_path"], 'r') as zf:
            namelist = zf.namelist()
            print(f"  Archive contents: {namelist}")
            
            # Check memory_db_package entries exist
            memory_entries = [n for n in namelist if "memory_db_package" in n]
            assert len(memory_entries) > 0, "memory_db_package entries missing from archive"
            
            # Check specific files
            assert any("manifest.json" in n for n in memory_entries), "manifest.json missing"
            assert any("entities/data.json" in n for n in memory_entries), "entities/data.json missing"
            
            # Verify path structure: save_with_memory/memory_db_package/...
            assert any(n.startswith("save_with_memory/memory_db_package/") for n in namelist), \
                "memory_db_package not under save folder envelope"
        
        print(f"  [OK] memory_db_package included with {len(memory_entries)} entries")

def test_memory_package_absence_allowed():
    """Test: Archive succeeds when memory_db_package is absent"""
    print("\n[Test 2] memory_db_package absence allowed...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup save folder WITHOUT memory_db_package
        save_path = os.path.join(tmpdir, "save_no_memory")
        os.makedirs(save_path)
        
        with open(os.path.join(save_path, "data.json"), "w") as f:
            f.write('{"test": "data"}')
        
        metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
        success, result = manager._generate_archive_zip(save_path, metadata)
        
        assert success is True, f"Expected success when memory package absent, got: {result}"
        assert result["bytes"] > 0, "Expected non-empty archive"
        
        # Verify no memory entries in archive
        with zipfile.ZipFile(result["zip_path"], 'r') as zf:
            namelist = zf.namelist()
            memory_entries = [n for n in namelist if "memory_db_package" in n]
            assert len(memory_entries) == 0, f"Unexpected memory entries: {memory_entries}"
        
        print(f"  [OK] Archive succeeds without memory_db_package")

def test_fail_closed_on_zip_failure():
    """Test: Helper returns error status on zip creation failure (fail-closed)"""
    print("\n[Test 3] Fail-closed behavior on zip failure...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_fail_test")
        os.makedirs(save_path)
        
        with open(os.path.join(save_path, "data.json"), "w") as f:
            f.write('{"test": "data"}')
        
        metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
        
        # First, test that normal operation works
        success, result = manager._generate_archive_zip(save_path, metadata)
        assert success is True, "Normal operation should succeed"
        
        # Verify the error contract format when we simulate an invalid path
        success2, result2 = manager._generate_archive_zip("/nonexistent/path", metadata)
        assert success2 is False, "Should return False on failure"
        assert result2["status"] == "error", f"Status should be 'error', got: {result2.get('status')}"
        assert "message" in result2, "Error result should have 'message' field"
        
        print(f"  [OK] Fail-closed contract verified: status={result2['status']}")

def test_memory_package_deterministic_ordering():
    """Test: memory_db_package entries are deterministically ordered"""
    print("\n[Test 4] memory_db_package deterministic ordering...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_memory_order")
        os.makedirs(save_path)
        
        with open(os.path.join(save_path, "save.json"), "w") as f:
            f.write('{"save": "data"}')
        
        # Create memory package with files in non-alphabetical order
        memory_package = os.path.join(save_path, "memory_db_package")
        os.makedirs(memory_package)
        
        for filename in ["zebra.json", "alpha.json", "beta.json"]:
            with open(os.path.join(memory_package, filename), "w") as f:
                f.write(f'"{filename}"')
        
        metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
        
        # Generate twice
        success1, result1 = manager._generate_archive_zip(save_path, metadata)
        success2, result2 = manager._generate_archive_zip(save_path, metadata)
        
        assert success1 and success2, "Both archives should succeed"
        
        with zipfile.ZipFile(result1["zip_path"], 'r') as zf1:
            namelist1 = zf1.namelist()
        
        with zipfile.ZipFile(result2["zip_path"], 'r') as zf2:
            namelist2 = zf2.namelist()
        
        # Compare memory entries
        memory1 = [n for n in namelist1 if "memory_db_package" in n]
        memory2 = [n for n in namelist2 if "memory_db_package" in n]
        
        assert memory1 == memory2, f"Memory entries not deterministic!\nFirst: {memory1}\nSecond: {memory2}"
        
        # Verify alphabetical ordering
        expected_order = sorted(memory1)
        assert memory1 == expected_order, f"Memory entries not sorted: {memory1}"
        
        print(f"  [OK] memory_db_package entries deterministically ordered")

def test_zip_integrity_with_memory_package():
    """Test: Zip integrity with memory_db_package included"""
    print("\n[Test 5] Zip integrity with memory package...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_integrity_memory")
        os.makedirs(save_path)
        
        with open(os.path.join(save_path, "data.json"), "w") as f:
            f.write('{"test": "data"}')
        
        # Create memory package
        memory_package = os.path.join(save_path, "memory_db_package")
        os.makedirs(memory_package)
        with open(os.path.join(memory_package, "db.sqlite"), "w") as f:
            f.write("sqlite data")
        
        metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
        success, result = manager._generate_archive_zip(save_path, metadata)
        
        assert success is True
        
        # Verify integrity
        with zipfile.ZipFile(result["zip_path"], 'r') as zf:
            integrity_result = zf.testzip()
            assert integrity_result is None, f"Zip integrity check failed: {integrity_result}"
            
            # Verify all expected entries
            namelist = zf.namelist()
            assert "save_integrity_memory/data.json" in namelist
            assert any("memory_db_package" in n and "db.sqlite" in n for n in namelist)
        
        print(f"  [OK] Zip integrity verified with memory package")

def test_result_contract_unchanged():
    """Test: Result contract remains unchanged with memory package"""
    print("\n[Test 6] Result contract unchanged...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_contract_memory")
        os.makedirs(save_path)
        
        with open(os.path.join(save_path, "test.txt"), "w") as f:
            f.write("test")
        
        # Test without memory package
        metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
        success1, result1 = manager._generate_archive_zip(save_path, metadata)
        
        # Add memory package and test again
        memory_package = os.path.join(save_path, "memory_db_package")
        os.makedirs(memory_package)
        with open(os.path.join(memory_package, "data.json"), "w") as f:
            f.write('"memory"')
        
        success2, result2 = manager._generate_archive_zip(save_path, metadata)
        
        assert success1 and success2, "Both should succeed"
        
        # Verify exact contract for both
        for i, result in enumerate([result1, result2], 1):
            assert "status" in result, f"Case {i}: Missing status field"
            assert "zip_path" in result, f"Case {i}: Missing zip_path field"
            assert "zip_name" in result, f"Case {i}: Missing zip_name field"
            assert "bytes" in result, f"Case {i}: Missing bytes field"
            
            assert result["status"] == "success", f"Case {i}: Unexpected status"
            assert isinstance(result["bytes"], int), f"Case {i}: bytes not int"
            assert result["bytes"] > 0, f"Case {i}: bytes not positive"
        
        # Second archive should be larger (has memory package)
        assert result2["bytes"] > result1["bytes"], \
            f"Archive with memory package should be larger: {result2['bytes']} vs {result1['bytes']}"
        
        print(f"  [OK] Contract unchanged: without_memory={result1['bytes']}B, with_memory={result2['bytes']}B")

def test_memory_package_not_duplicated():
    """Test: memory_db_package not duplicated in archive"""
    print("\n[Test 7] memory_db_package not duplicated...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_no_dup")
        os.makedirs(save_path)
        
        with open(os.path.join(save_path, "save.json"), "w") as f:
            f.write('{"save": "data"}')
        
        # Create memory package
        memory_package = os.path.join(save_path, "memory_db_package")
        os.makedirs(memory_package)
        with open(os.path.join(memory_package, "manifest.json"), "w") as f:
            f.write('"manifest"')
        
        metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
        success, result = manager._generate_archive_zip(save_path, metadata)
        
        assert success is True
        
        with zipfile.ZipFile(result["zip_path"], 'r') as zf:
            namelist = zf.namelist()
            
            # Count memory_db_package occurrences
            memory_entries = [n for n in namelist if "memory_db_package" in n]
            manifest_entries = [n for n in namelist if "manifest.json" in n]
            
            # Should only have one manifest.json entry
            assert len(manifest_entries) == 1, f"manifest.json duplicated: {manifest_entries}"
            
            # All memory entries should be under save_no_dup/memory_db_package/
            assert all(n.startswith("save_no_dup/memory_db_package/") for n in memory_entries), \
                f"Memory entries not under save folder: {[n for n in memory_entries if not n.startswith('save_no_dup/memory_db_package/')]}"
        
        print(f"  [OK] memory_db_package not duplicated")

if __name__ == "__main__":
    print("=" * 60)
    print("Step 1.3 Memory Package Inclusion Tests")
    print("=" * 60)
    
    try:
        test_memory_package_inclusion()
        test_memory_package_absence_allowed()
        test_fail_closed_on_zip_failure()
        test_memory_package_deterministic_ordering()
        test_zip_integrity_with_memory_package()
        test_result_contract_unchanged()
        test_memory_package_not_duplicated()
        
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
