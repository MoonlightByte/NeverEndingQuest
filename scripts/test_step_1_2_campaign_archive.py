#!/usr/bin/env python3
"""Smoke tests for Step 1.2 campaign-wide archive inclusion"""

import os
import sys
import tempfile
import shutil
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updates.save_game_manager import SaveGameManager

def test_played_modules_resolution():
    """Test: Helper resolves played modules from campaign archives"""
    print("\n[Test 1] Played modules resolution from campaign directories...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup campaign structure
        campaign_archives = os.path.join(tmpdir, "modules", "campaign_archives")
        campaign_summaries = os.path.join(tmpdir, "modules", "campaign_summaries")
        os.makedirs(campaign_archives)
        os.makedirs(campaign_summaries)
        
        # Create archive files for different modules
        with open(os.path.join(campaign_archives, "Keep_of_Doom_conversation_001.json"), "w") as f:
            f.write('{"test": "archive1"}')
        with open(os.path.join(campaign_archives, "Forest_of_Shadows_conversation_001.json"), "w") as f:
            f.write('{"test": "archive2"}')
        
        # Create summary files
        with open(os.path.join(campaign_summaries, "Keep_of_Doom_summary_001.json"), "w") as f:
            f.write('{"test": "summary1"}')
        with open(os.path.join(campaign_summaries, "Mountain_Pass_summary_001.json"), "w") as f:
            f.write('{"test": "summary2"}')
        
        # Change to temp directory for file operations
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Create save folder
            save_path = os.path.join(tmpdir, "save_test")
            os.makedirs(save_path)
            with open(os.path.join(save_path, "test.json"), "w") as f:
                f.write('{"save": "data"}')
            
            metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
            success, result = manager._generate_archive_zip(save_path, metadata)
            
            assert success is True, f"Expected success=True, got {success}"
            
            # Verify archive contains campaign files
            with zipfile.ZipFile(result["zip_path"], 'r') as zf:
                namelist = zf.namelist()
                print(f"  Archive contents: {namelist}")
                
                # Check campaign files are included
                assert any("campaign_archives" in name for name in namelist), "Missing campaign_archives"
                assert any("campaign_summaries" in name for name in namelist), "Missing campaign_summaries"
                
                # Check specific module files
                keep_archives = [n for n in namelist if "Keep_of_Doom" in n]
                keep_summaries = [n for n in namelist if "Keep_of_Doom" in n and "summaries" in n]
                
                assert len(keep_archives) > 0, "Keep_of_Doom archive not found"
                print(f"  [OK] Found Keep_of_Doom files: {keep_archives}")
                
        finally:
            os.chdir(original_cwd)

def test_deterministic_ordering():
    """Test: Archive entries are in deterministic order"""
    print("\n[Test 2] Deterministic entry ordering...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup structure with multiple files
        save_path = os.path.join(tmpdir, "save_deterministic")
        os.makedirs(save_path)
        
        # Create files in non-alphabetical order
        for filename in ["zebra.txt", "alpha.txt", "beta.txt", "gamma.txt"]:
            with open(os.path.join(save_path, filename), "w") as f:
                f.write(f"content of {filename}")
        
        # Create subdirectories with files
        for subdir in ["z_dir", "a_dir", "m_dir"]:
            subdir_path = os.path.join(save_path, subdir)
            os.makedirs(subdir_path)
            with open(os.path.join(subdir_path, "file.txt"), "w") as f:
                f.write(f"content in {subdir}")
        
        metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
        
        # Generate archive twice
        success1, result1 = manager._generate_archive_zip(save_path, metadata)
        success2, result2 = manager._generate_archive_zip(save_path, metadata)
        
        assert success1 and success2, "Archive generation failed"
        
        # Compare namelists - should be identical
        with zipfile.ZipFile(result1["zip_path"], 'r') as zf1:
            namelist1 = zf1.namelist()

        with zipfile.ZipFile(result2["zip_path"], 'r') as zf2:
            namelist2 = zf2.namelist()

        print(f"  First archive order: {namelist1[:5]}...")
        print(f"  Second archive order: {namelist2[:5]}...")

        assert namelist1 == namelist2, f"Ordering not deterministic!\nFirst: {namelist1}\nSecond: {namelist2}"

        # Verify save entries are alphabetically sorted
        save_entries = [n for n in namelist1 if n.startswith("save_deterministic/")]
        expected_save_order = sorted(save_entries)
        assert save_entries == expected_save_order, f"Save entries not sorted alphabetically: {save_entries}"

        print(f"  [OK] Deterministic ordering verified (save entries sorted)")

def test_missing_optional_files_skipped():
    """Test: Missing optional files are skipped safely"""
    print("\n[Test 3] Missing optional files skipped safely...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # No campaign directories - should still succeed
        save_path = os.path.join(tmpdir, "save_no_campaign")
        os.makedirs(save_path)
        
        with open(os.path.join(save_path, "data.json"), "w") as f:
            f.write('{"test": "data"}')
        
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
            success, result = manager._generate_archive_zip(save_path, metadata)
            
            assert success is True, f"Expected success with missing optional files, got: {result}"
            assert result["bytes"] > 0, "Expected non-empty archive"
            
            # Verify only save folder contents included
            with zipfile.ZipFile(result["zip_path"], 'r') as zf:
                namelist = zf.namelist()
                # Should only have save folder contents
                unexpected = [n for n in namelist if not n.startswith('save_no_campaign/')]
                assert all(name.startswith("save_no_campaign/") for name in namelist), \
                    f"Unexpected entries: {unexpected}"
            
            print(f"  [OK] Missing optional files handled gracefully")
            
        finally:
            os.chdir(original_cwd)

def test_envelope_preservation_with_additional():
    """Test: Save folder envelope preserved alongside additional artifacts"""
    print("\n[Test 4] Envelope preservation with additional artifacts...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup save folder
        save_path = os.path.join(tmpdir, "save_envelope")
        os.makedirs(save_path)
        with open(os.path.join(save_path, "save_data.json"), "w") as f:
            f.write('{"save": "data"}')
        
        # Setup campaign structure
        campaign_archives = os.path.join(tmpdir, "modules", "campaign_archives")
        os.makedirs(campaign_archives)
        with open(os.path.join(campaign_archives, "Test_Module_conversation_001.json"), "w") as f:
            f.write('{"archive": "data"}')
        
        # Setup global files
        modules_dir = os.path.join(tmpdir, "modules")
        with open(os.path.join(modules_dir, "world_registry.json"), "w") as f:
            f.write('{"registry": "data"}')
        
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
            success, result = manager._generate_archive_zip(save_path, metadata)

            assert success is True

            with zipfile.ZipFile(result["zip_path"], 'r') as zf:
                namelist = zf.namelist()
                print(f"  Archive contents: {namelist}")

                # Verify save folder envelope preserved
                save_entries = [n for n in namelist if n.startswith("save_envelope/")]
                assert len(save_entries) > 0, "Save folder envelope missing"
                
                # Verify campaign artifacts present
                campaign_entries = [n for n in namelist if "modules/" in n]
                assert len(campaign_entries) > 0, "Campaign artifacts missing"
                
                # Verify specific paths
                assert "save_envelope/save_data.json" in namelist, "Save data missing"
                assert any("world_registry.json" in n for n in namelist), "World registry missing"
                
            print(f"  [OK] Save envelope and campaign artifacts both present")
            
        finally:
            os.chdir(original_cwd)

def test_result_contract_unchanged():
    """Test: Result contract remains unchanged"""
    print("\n[Test 5] Result contract unchanged...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "save_contract")
        os.makedirs(save_path)
        with open(os.path.join(save_path, "test.txt"), "w") as f:
            f.write("test")
        
            metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
            success, result = manager._generate_archive_zip(save_path, metadata)
        
        assert success is True
        
        # Verify exact contract
        assert "status" in result, "Missing status field"
        assert "zip_path" in result, "Missing zip_path field"
        assert "zip_name" in result, "Missing zip_name field"
        assert "bytes" in result, "Missing bytes field"
        
        assert result["status"] == "success", f"Unexpected status: {result['status']}"
        assert isinstance(result["zip_path"], str), "zip_path not string"
        assert isinstance(result["zip_name"], str), "zip_name not string"
        assert isinstance(result["bytes"], int), "bytes not int"
        assert result["bytes"] > 0, "bytes not positive"
        
        print(f"  [OK] Contract: status={result['status']}, bytes={result['bytes']}")

def test_zip_integrity_with_additional():
    """Test: Zip integrity with additional campaign artifacts"""
    print("\n[Test 6] Zip integrity with additional artifacts...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup comprehensive structure
        save_path = os.path.join(tmpdir, "save_integrity")
        os.makedirs(save_path)
        with open(os.path.join(save_path, "data.json"), "w") as f:
            f.write('{"test": "data"}')
        
        # Campaign structure
        campaign_archives = os.path.join(tmpdir, "modules", "campaign_archives")
        os.makedirs(campaign_archives)
        with open(os.path.join(campaign_archives, "ModA_conversation_001.json"), "w") as f:
            f.write('{"archive": "a"}')
        
        campaign_summaries = os.path.join(tmpdir, "modules", "campaign_summaries")
        os.makedirs(campaign_summaries)
        with open(os.path.join(campaign_summaries, "ModB_summary_001.json"), "w") as f:
            f.write('{"summary": "b"}')
        
        # Global files
        modules_dir = os.path.join(tmpdir, "modules")
        with open(os.path.join(modules_dir, "campaign.json"), "w") as f:
            f.write('{"campaign": "data"}')
        with open(os.path.join(modules_dir, "world_registry.json"), "w") as f:
            f.write('{"registry": "data"}')
        
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            metadata = {"save_timestamp": datetime.now().isoformat(), "module": "TestModule"}
            success, result = manager._generate_archive_zip(save_path, metadata)

            assert success is True

            # Verify integrity
            with zipfile.ZipFile(result["zip_path"], 'r') as zf:
                integrity_result = zf.testzip()
                assert integrity_result is None, f"Zip integrity check failed: {integrity_result}"
                
                # Verify all expected entries present
                namelist = zf.namelist()
                
                # Save folder
                assert any("save_integrity" in n for n in namelist), "Save folder missing"
                
                # Campaign files
                assert any("campaign_archives" in n for n in namelist), "Campaign archives missing"
                assert any("campaign_summaries" in n for n in namelist), "Campaign summaries missing"
                
                # Global files
                assert any("campaign.json" in n for n in namelist), "campaign.json missing"
                assert any("world_registry.json" in n for n in namelist), "world_registry.json missing"
                
            print(f"  [OK] Zip integrity verified with all artifact types")
            
        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    print("=" * 60)
    print("Step 1.2 Campaign-Wide Archive Inclusion Tests")
    print("=" * 60)
    
    try:
        test_played_modules_resolution()
        test_deterministic_ordering()
        test_missing_optional_files_skipped()
        test_envelope_preservation_with_additional()
        test_result_contract_unchanged()
        test_zip_integrity_with_additional()
        
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
