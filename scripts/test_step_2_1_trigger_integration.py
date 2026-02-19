#!/usr/bin/env python3
"""Smoke tests for Step 2.1 archive trigger integration"""

import os
import sys
import tempfile
import zipfile
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updates.save_game_manager import SaveGameManager

def test_full_save_triggers_archive():
    """Test: save_mode=full triggers archive generation after save"""
    print("\n[Test 1] Full save triggers archive generation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup minimal campaign structure
        os.makedirs(os.path.join(tmpdir, "modules", "campaign_archives"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "modules", "campaign_summaries"), exist_ok=True)
        
        # Create minimal required files
        with open(os.path.join(tmpdir, "party_tracker.json"), "w") as f:
            json.dump({"module": "TestModule", "partyMembers": []}, f)
        with open(os.path.join(tmpdir, "journal.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(tmpdir, "current_location.json"), "w") as f:
            json.dump({}, f)
        
        os.makedirs(os.path.join(tmpdir, "characters"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "modules", "TestModule"), exist_ok=True)
        
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            manager = SaveGameManager()
            
            # Create a full save
            success, message = manager.create_save_game("Test full save", save_mode="full")
            
            assert success is True, f"Full save should succeed: {message}"
            
            # Simulate web interface archive trigger logic
            saves = manager.list_save_games()
            if saves and len(saves) > 0:
                latest_save = saves[0]
                save_path = latest_save.get("save_path")
                if save_path and os.path.exists(save_path):
                    # This is what web_interface.py does for full saves
                    archive_success, archive_result = manager._generate_archive_zip(save_path, latest_save)
                    assert archive_success is True, f"Archive generation should succeed: {archive_result}"
            
            # Check that archive zip was created
            saves = manager.list_save_games()
            assert len(saves) > 0, "No saves found"
            
            latest_save = saves[0]
            save_parent = os.path.dirname(latest_save["save_path"])
            
            # Look for archive zip in save parent directory
            archive_files = [f for f in os.listdir(save_parent) if f.startswith("archive_") and f.endswith(".zip")]
            assert len(archive_files) > 0, f"Archive zip not created in {save_parent}"
            
            print(f"  [OK] Archive created: {archive_files[0]}")
            
        finally:
            os.chdir(original_cwd)

def test_essential_save_no_archive():
    """Test: save_mode=essential does NOT trigger archive generation"""
    print("\n[Test 2] Essential save does not create archive...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup minimal campaign structure
        os.makedirs(os.path.join(tmpdir, "modules", "campaign_archives"), exist_ok=True)
        
        with open(os.path.join(tmpdir, "party_tracker.json"), "w") as f:
            json.dump({"module": "TestModule", "partyMembers": []}, f)
        with open(os.path.join(tmpdir, "journal.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(tmpdir, "current_location.json"), "w") as f:
            json.dump({}, f)
        
        os.makedirs(os.path.join(tmpdir, "characters"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "modules", "TestModule"), exist_ok=True)
        
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            manager = SaveGameManager()
            
            # Create an essential save
            success, message = manager.create_save_game("Test essential save", save_mode="essential")
            
            assert success is True, f"Essential save should succeed: {message}"
            
            # Essential save does NOT trigger archive generation (web_interface.py only does this for full)
            # Check that NO archive zip was created
            saves = manager.list_save_games()
            if saves:
                latest_save = saves[0]
                save_parent = os.path.dirname(latest_save["save_path"])
                archive_files = [f for f in os.listdir(save_parent) if f.startswith("archive_") and f.endswith(".zip")]
                assert len(archive_files) == 0, f"Archive zip should not exist for essential save: {archive_files}"
            
            print(f"  [OK] No archive created for essential save")
            
        finally:
            os.chdir(original_cwd)

def test_archive_trigger_location():
    """Test: Archive trigger logic location in save flow"""
    print("\n[Test 3] Archive trigger location verification...")
    
    # This is a code structure test - verify the trigger is in web_interface.py
    web_interface_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "web_interface.py"
    )
    
    with open(web_interface_path, "r") as f:
        content = f.read()
    
    # Check for archive trigger in saveGame branch
    assert "action_type == 'saveGame'" in content, "saveGame branch not found"
    assert "_generate_archive_zip" in content, "Archive trigger not found in web_interface.py"
    assert 'save_mode == "full"' in content, "Full save mode check not found"
    
    print(f"  [OK] Archive trigger integrated in web/web_interface.py")

def test_fail_closed_behavior():
    """Test: Fail-closed behavior when archive generation fails"""
    print("\n[Test 4] Fail-closed behavior on archive failure...")
    
    manager = SaveGameManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with invalid path - should return failure
        success, result = manager._generate_archive_zip("/nonexistent/path", {})
        
        assert success is False, "Should return False for invalid path"
        assert result["status"] == "error", f"Status should be error, got: {result.get('status')}"
        
        print(f"  [OK] Fail-closed: status={result['status']}")

def test_archive_includes_save_contents():
    """Test: Archive includes actual save folder contents"""
    print("\n[Test 5] Archive includes save contents...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup minimal campaign structure
        os.makedirs(os.path.join(tmpdir, "modules", "campaign_archives"), exist_ok=True)
        
        with open(os.path.join(tmpdir, "party_tracker.json"), "w") as f:
            json.dump({"module": "TestModule", "partyMembers": []}, f)
        with open(os.path.join(tmpdir, "journal.json"), "w") as f:
            json.dump({"test": "journal"}, f)
        with open(os.path.join(tmpdir, "current_location.json"), "w") as f:
            json.dump({}, f)
        
        os.makedirs(os.path.join(tmpdir, "characters"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "modules", "TestModule"), exist_ok=True)
        
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            manager = SaveGameManager()
            
            # Create a full save
            success, message = manager.create_save_game("Test archive contents", save_mode="full")
            
            assert success is True, f"Full save should succeed: {message}"
            
            # Simulate web interface archive trigger
            saves = manager.list_save_games()
            if saves and len(saves) > 0:
                latest_save = saves[0]
                save_path = latest_save.get("save_path")
                if save_path and os.path.exists(save_path):
                    archive_success, archive_result = manager._generate_archive_zip(save_path, latest_save)
                    assert archive_success is True, f"Archive generation should succeed: {archive_result}"
            
            # Find and verify archive
            saves = manager.list_save_games()
            latest_save = saves[0]
            save_parent = os.path.dirname(latest_save["save_path"])
            
            archive_files = [f for f in os.listdir(save_parent) if f.startswith("archive_") and f.endswith(".zip")]
            assert len(archive_files) > 0, "Archive not found"
            
            archive_path = os.path.join(save_parent, archive_files[0])
            
            # Verify archive contents
            with zipfile.ZipFile(archive_path, 'r') as zf:
                namelist = zf.namelist()
                print(f"  Archive entries: {len(namelist)} files")
                
                # Should have save metadata
                save_entries = [n for n in namelist if "save_" in n and "/save_metadata.json" in n]
                assert len(save_entries) > 0, "Save metadata not in archive"
                
                # Should have essential files
                assert any("party_tracker.json" in n for n in namelist), "party_tracker.json missing"
                
            print(f"  [OK] Archive contains expected save contents")
            
        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    print("=" * 60)
    print("Step 2.1 Archive Trigger Integration Tests")
    print("=" * 60)
    
    try:
        test_full_save_triggers_archive()
        test_essential_save_no_archive()
        test_archive_trigger_location()
        test_fail_closed_behavior()
        test_archive_includes_save_contents()
        
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
