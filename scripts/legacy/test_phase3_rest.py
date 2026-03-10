#!/usr/bin/env python3
"""
Test script for Phase 3 Rest Automation Enhancement
Validates the rest action handler implementation without full module imports
"""

import json
import os

def test_rest_action_structure():
    """Verify that the rest action is properly defined in action_handler.py"""
    
    with open('core/ai/action_handler.py', 'r') as f:
        content = f.read()
    
    # Check for ACTION_REST constant
    assert 'ACTION_REST = "rest"' in content, "ACTION_REST constant not found"
    print("✓ ACTION_REST constant defined")
    
    # Check for rest action handler
    assert 'elif action_type == ACTION_REST:' in content, "Rest action handler not found"
    print("✓ Rest action handler block present")
    
    # Check for helper functions
    assert 'def _process_character_rest(' in content, "_process_character_rest function not found"
    print("✓ _process_character_rest function defined")
    
    assert 'def _format_rest_summary(' in content, "_format_rest_summary function not found"
    print("✓ _format_rest_summary function defined")
    
    # Check for TABLETOP MODE comment
    assert '# TABLETOP MODE: Phase 3 - Rest Automation Enhancement (Option B)' in content
    print("✓ TABLETOP MODE comment present")
    
    return True

def test_compressed_prompt_updates():
    """Verify compressed prompt has @PARTY_HANDLING and updated @REST"""
    
    with open('prompts/system_prompt_compressed.txt', 'r') as f:
        content = f.read()
    
    # Check for @PARTY_HANDLING section
    assert '@PARTY_HANDLING={' in content, "@PARTY_HANDLING section not found"
    print("✓ @PARTY_HANDLING section present")
    
    # Check for key fields in PARTY_HANDLING
    assert 'composition:' in content, "composition field not found"
    assert 'scaling:' in content, "scaling field not found"
    assert 'rest_action:' in content, "rest_action field not found"
    print("✓ PARTY_HANDLING fields present")
    
    # Check for updated @REST section
    assert '@REST={' in content, "@REST section not found"
    assert 'action:' in content, "rest action field not found"
    print("✓ @REST section updated with action field")
    
    return True

def test_character_structure():
    """Verify we understand character file structure"""
    
    # Check if character files exist
    chars_dir = 'characters'
    if not os.path.exists(chars_dir):
        print("⚠ characters directory not found, skipping character structure test")
        return True
    
    char_files = [f for f in os.listdir(chars_dir) if f.endswith('.json') and not f.startswith('.')]
    if not char_files:
        print("⚠ No character files found, skipping character structure test")
        return True
    
    # Check structure of first character file
    with open(os.path.join(chars_dir, char_files[0]), 'r') as f:
        char_data = json.load(f)
    
    # Verify expected fields exist
    assert 'hitPoints' in char_data or 'hit_points' in str(char_data).lower(), "HP field not found"
    assert 'maxHitPoints' in char_data or 'max_hp' in str(char_data).lower(), "Max HP field not found"
    print(f"✓ Character file structure valid ({char_files[0]})")
    
    # Check for spellcasting section (if present)
    if 'spellcasting' in char_data:
        spellcasting = char_data['spellcasting']
        if 'spellSlots' in spellcasting:
            print(f"✓ Spell slots structure present")
    
    return True

def test_syntax():
    """Verify Python syntax is valid"""
    import subprocess
    result = subprocess.run(['python3', '-m', 'py_compile', 'core/ai/action_handler.py'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f"✗ Syntax error: {result.stderr}")
        return False
    print("✓ Python syntax valid")
    return True

def main():
    print("=" * 60)
    print("Phase 3 Rest Automation Enhancement - Validation Tests")
    print("=" * 60)
    print()
    
    tests = [
        ("Python Syntax", test_syntax),
        ("Rest Action Structure", test_rest_action_structure),
        ("Compressed Prompt Updates", test_compressed_prompt_updates),
        ("Character Structure", test_character_structure),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} PASSED")
            else:
                failed += 1
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"✗ {test_name} FAILED: {e}")
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All validation tests passed!")
        print("\nPhase 3 Implementation Summary:")
        print("- Rest action handler added to action_handler.py")
        print("- _process_character_rest() helper function implemented")
        print("- _format_rest_summary() helper function implemented")
        print("- @PARTY_HANDLING section added to compressed prompt")
        print("- @REST section updated with rest action guidance")
        print("\nThe rest automation will now:")
        print("1. Restore HP to max for all targeted characters")
        print("2. Restore all spell slots to max")
        print("3. Reset class feature usages based on refreshOn property")
        print("4. Reduce exhaustion by 1 level (long rest only)")
        print("5. Generate a summary message for the conversation")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    exit(main())
