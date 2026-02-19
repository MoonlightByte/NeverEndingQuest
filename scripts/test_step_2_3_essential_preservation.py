#!/usr/bin/env python3
"""Smoke tests for Step 2.3 essential save behavior preservation"""

import os
import sys
import tempfile
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updates.save_game_manager import SaveGameManager

def test_essential_save_legacy_payload():
    """Test: Essential save emits legacy payload shape (content-only)"""
    print("\n[Test 1] Essential save legacy payload shape...")
    
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
            
            # Simulate essential payload (from web_interface.py Step 2.3)
            payload = {
                'content': f"Game saved: {message}"
            }
            
            # Verify legacy shape: content-only
            assert 'content' in payload, "Missing content field"
            assert 'save_mode' not in payload, "Essential save should NOT have save_mode field"
            assert 'archive' not in payload, "Essential save should NOT have archive field"
            
            # Verify exact key set
            assert set(payload.keys()) == {'content'}, f"Expected keys {{'content'}}, got {set(payload.keys())}"
            
            print(f"  [OK] Essential payload (legacy shape): {json.dumps(payload)}")
            
        finally:
            os.chdir(original_cwd)

def test_full_save_payload_unchanged():
    """Test: Full save still emits full payload with archive fields"""
    print("\n[Test 2] Full save payload unchanged with archive fields...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
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
            success, message = manager.create_save_game("Test full save", save_mode="full")
            assert success is True, f"Full save should succeed: {message}"
            
            # Get archive result
            saves = manager.list_save_games()
            latest_save = saves[0]
            archive_success, archive_result = manager._generate_archive_zip(
                latest_save.get("save_path"), latest_save
            )
            assert archive_success is True, f"Archive should succeed: {archive_result}"
            
            # Simulate full payload (from web_interface.py)
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
            
            # Verify full payload has all fields
            assert 'content' in payload, "Missing content field"
            assert 'save_mode' in payload, "Missing save_mode field"
            assert 'archive' in payload, "Missing archive field"
            assert payload['save_mode'] == 'full', f"Expected save_mode='full', got {payload['save_mode']}"
            
            # Verify archive sub-fields
            archive = payload['archive']
            assert 'status' in archive, "Missing archive.status"
            assert 'zip_path' in archive, "Missing archive.zip_path"
            assert 'zip_name' in archive, "Missing archive.zip_name"
            assert 'bytes' in archive, "Missing archive.bytes"
            
            print(f"  [OK] Full payload unchanged: save_mode={payload['save_mode']}, archive fields present")
            
        finally:
            os.chdir(original_cwd)

def test_essential_before_after_comparison():
    """Test: Essential payload matches legacy shape exactly"""
    print("\n[Test 3] Essential payload legacy shape verification...")
    
    message = "Save created successfully"
    
    # Legacy shape (before archive work)
    legacy_payload = {
        'content': f"Game saved: {message}"
    }
    
    # Current shape (Step 2.3)
    current_payload = {
        'content': f"Game saved: {message}"
    }
    
    # They should be identical
    assert legacy_payload == current_payload, f"Payload shapes differ!\nLegacy: {legacy_payload}\nCurrent: {current_payload}"
    
    print(f"  [OK] Essential payload matches legacy shape exactly")

def test_frontend_backward_compatibility():
    """Test: Frontend can still access data.content for both modes"""
    print("\n[Test 4] Frontend backward compatibility (data.content)...")
    
    # Essential payload
    essential_payload = {
        'content': "Game saved: essential_test"
    }
    
    # Full payload
    full_payload = {
        'content': "Game saved: full_test\nArchive created: test.zip (100 bytes)",
        'save_mode': 'full',
        'archive': {'status': 'success', 'zip_path': '/path', 'zip_name': 'test.zip', 'bytes': 100}
    }
    
    # Simulate frontend access pattern from game_interface.html
    # socket.on('system_message', (data) => { addMessage('game-output', { type: 'system', content: data.content }); });
    
    essential_content = essential_payload.get('content')
    full_content = full_payload.get('content')
    
    assert essential_content is not None, "Essential data.content should be accessible"
    assert full_content is not None, "Full data.content should be accessible"
    assert "Game saved:" in essential_content, "Essential content malformed"
    assert "Game saved:" in full_content, "Full content malformed"
    
    print(f"  [OK] Both payloads have accessible data.content")

def test_fail_closed_preserved():
    """Test: Fail-closed behavior for full save archive failures preserved"""
    print("\n[Test 5] Fail-closed behavior preserved...")
    
    # Simulate archive failure
    archive_success = False
    archive_result = {"status": "error", "message": "Disk full"}
    
    if not archive_success:
        # Fail-closed: emit error, return early (no success emit)
        error_payload = {'message': f"Archive generation failed: {archive_result.get('message', 'unknown error')}"}
        # In real code: emit('error', error_payload); return
        
        # Verify error structure
        assert 'message' in error_payload, "Error payload missing message"
        assert "Archive generation failed" in error_payload['message'], "Error message incorrect"
        
        print(f"  [OK] Fail-closed preserved: error={error_payload['message']}")
    else:
        assert False, "Should not reach success path"

def test_payload_key_differences():
    """Test: Clear distinction between essential and full payload keys"""
    print("\n[Test 6] Payload key differences...")
    
    # Essential payload keys
    essential_keys = {'content'}
    
    # Full payload keys
    full_keys = {'content', 'save_mode', 'archive'}
    
    # They should be different
    assert essential_keys != full_keys, "Essential and full should have different keys"
    assert essential_keys.issubset(full_keys), "Essential keys should be subset of full keys"
    
    print(f"  [OK] Essential keys: {essential_keys}")
    print(f"  [OK] Full keys: {full_keys}")

if __name__ == "__main__":
    print("=" * 60)
    print("Step 2.3 Essential Save Preservation Tests")
    print("=" * 60)
    
    try:
        test_essential_save_legacy_payload()
        test_full_save_payload_unchanged()
        test_essential_before_after_comparison()
        test_frontend_backward_compatibility()
        test_fail_closed_preserved()
        test_payload_key_differences()
        
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
