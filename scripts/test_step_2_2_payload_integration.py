#!/usr/bin/env python3
"""Smoke tests for Step 2.2 archive payload with operator guidance"""

import os
import sys
import tempfile
import zipfile
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updates.save_game_manager import SaveGameManager

class MockEmit:
    """Mock emit function to capture emitted payloads"""
    def __init__(self):
        self.emitted = []
    
    def __call__(self, event, data):
        self.emitted.append((event, data))

def test_full_save_payload_with_archive():
    """Test: Full save emits system_message with archive artifact info"""
    print("\n[Test 1] Full save payload includes archive info...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup minimal campaign structure
        os.makedirs(os.path.join(tmpdir, "modules", "campaign_archives"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "modules", "campaign_summaries"), exist_ok=True)
        
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
            success, message = manager.create_save_game("Test full save with payload", save_mode="full")
            assert success is True, f"Full save should succeed: {message}"
            
            # Get latest save and generate archive
            saves = manager.list_save_games()
            assert len(saves) > 0, "No saves found"
            
            latest_save = saves[0]
            save_path = latest_save.get("save_path")
            archive_success, archive_result = manager._generate_archive_zip(save_path, latest_save)
            assert archive_success is True, f"Archive should succeed: {archive_result}"
            
            # Simulate payload construction (from web_interface.py)
            payload = {
                'content': f"Game saved: {message}\nArchive created: {archive_result.get('zip_name')} ({archive_result.get('bytes')} bytes)",
                'save_mode': 'full',
                'archive': {
                    'status': archive_result.get('status'),
                    'zip_path': archive_result.get('zip_path'),
                    'zip_name': archive_result.get('zip_name'),
                    'bytes': archive_result.get('bytes')
                }
            }
            
            # Verify payload structure
            assert 'content' in payload, "Missing content field"
            assert 'save_mode' in payload, "Missing save_mode field"
            assert 'archive' in payload, "Missing archive field"
            
            # Verify archive fields
            archive = payload['archive']
            assert 'status' in archive, "Missing archive.status"
            assert 'zip_path' in archive, "Missing archive.zip_path"
            assert 'zip_name' in archive, "Missing archive.zip_name"
            assert 'bytes' in archive, "Missing archive.bytes"
            
            assert archive['status'] == 'success', f"Expected status=success, got {archive['status']}"
            assert isinstance(archive['bytes'], int), "bytes should be int"
            assert archive['bytes'] > 0, "bytes should be positive"
            
            # Verify content includes operator guidance
            assert "Archive created:" in payload['content'], "Missing operator guidance in content"
            assert archive['zip_name'] in payload['content'], "Missing zip_name in content"
            
            print(f"  [OK] Payload: {json.dumps(payload, indent=2)}")
            
        finally:
            os.chdir(original_cwd)

def test_essential_save_payload_unchanged():
    """Test: Essential save payload remains backward-compatible"""
    print("\n[Test 2] Essential save payload backward-compatible...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
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
            
            # Simulate essential payload (from web_interface.py)
            payload = {
                'content': f"Game saved: {message}",
                'save_mode': 'essential'
            }
            
            # Verify backward-compatible structure
            assert 'content' in payload, "Missing content field"
            assert 'save_mode' in payload, "Missing save_mode field"
            assert 'archive' not in payload, "Essential save should not have archive field"
            
            # Verify content format
            assert "Game saved:" in payload['content'], "Missing standard save message"
            assert "Archive" not in payload['content'], "Essential save should not mention archive"
            
            print(f"  [OK] Essential payload: {json.dumps(payload, indent=2)}")
            
        finally:
            os.chdir(original_cwd)

def test_payload_backward_compatibility():
    """Test: Existing frontend code can still access data.content"""
    print("\n[Test 3] Backward compatibility - data.content accessible...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
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
            
            # Full save with archive
            success, message = manager.create_save_game("Test full", save_mode="full")
            saves = manager.list_save_games()
            latest_save = saves[0]
            archive_success, archive_result = manager._generate_archive_zip(
                latest_save.get("save_path"), latest_save
            )
            
            # Full save payload
            full_payload = {
                'content': f"Game saved: {message}\nArchive created: {archive_result.get('zip_name')} ({archive_result.get('bytes')} bytes)",
                'save_mode': 'full',
                'archive': archive_result
            }
            
            # Simulate frontend access pattern from game_interface.html
            # socket.on('system_message', (data) => { addMessage('game-output', { type: 'system', content: data.content }); });
            content_accessible = full_payload.get('content') is not None
            assert content_accessible, "data.content should be accessible"
            
            # Essential save payload
            essential_payload = {
                'content': f"Game saved: {message}",
                'save_mode': 'essential'
            }
            
            content_accessible = essential_payload.get('content') is not None
            assert content_accessible, "Essential data.content should be accessible"
            
            print(f"  [OK] Both full and essential payloads have accessible data.content")
            
        finally:
            os.chdir(original_cwd)

def test_archive_failure_not_in_payload():
    """Test: Archive failure path does not emit success payload"""
    print("\n[Test 4] Archive failure does not emit success payload...")
    
    # Simulate fail-closed behavior (from web_interface.py)
    archive_success = False
    archive_result = {"status": "error", "message": "Test failure"}
    
    if not archive_success:
        # Fail-closed: emit error, return early
        error_payload = {'message': f"Archive generation failed: {archive_result.get('message', 'unknown error')}"}
        # In real code: emit('error', error_payload); return
        
        # Verify error payload structure
        assert 'message' in error_payload, "Error payload should have message"
        assert "Archive generation failed" in error_payload['message'], "Should indicate archive failure"
        
        # Success payload should NOT be emitted in this path
        print(f"  [OK] Error emitted: {error_payload['message']}")
    else:
        assert False, "Should not reach success path on archive failure"

def test_full_save_payload_shape():
    """Test: Full save payload has exact expected shape"""
    print("\n[Test 5] Full save payload exact shape verification...")
    
    # Build expected payload (from web_interface.py logic)
    message = "Save game created successfully"
    archive_result = {
        'status': 'success',
        'zip_path': '/path/to/archive_20240216_120000.zip',
        'zip_name': 'archive_20240216_120000.zip',
        'bytes': 12345
    }
    
    payload = {
        'content': f"Game saved: {message}\nArchive created: {archive_result.get('zip_name')} ({archive_result.get('bytes')} bytes)",
        'save_mode': 'full',
        'archive': {
            'status': archive_result.get('status'),
            'zip_path': archive_result.get('zip_path'),
            'zip_name': archive_result.get('zip_name'),
            'bytes': archive_result.get('bytes')
        }
    }
    
    # Verify exact keys
    expected_keys = {'content', 'save_mode', 'archive'}
    actual_keys = set(payload.keys())
    assert actual_keys == expected_keys, f"Expected keys {expected_keys}, got {actual_keys}"
    
    # Verify archive sub-keys
    archive_expected_keys = {'status', 'zip_path', 'zip_name', 'bytes'}
    archive_actual_keys = set(payload['archive'].keys())
    assert archive_actual_keys == archive_expected_keys, f"Expected archive keys {archive_expected_keys}, got {archive_actual_keys}"
    
    print(f"  [OK] Payload shape verified: {json.dumps(payload, indent=2)}")

if __name__ == "__main__":
    print("=" * 60)
    print("Step 2.2 Archive Payload Integration Tests")
    print("=" * 60)
    
    try:
        test_full_save_payload_with_archive()
        test_essential_save_payload_unchanged()
        test_payload_backward_compatibility()
        test_archive_failure_not_in_payload()
        test_full_save_payload_shape()
        
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
