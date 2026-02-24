#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Unit tests for background feature placeholder remediation script.

Covers dry-run behavior, apply behavior, mixed cases, error handling, and idempotency.
Uses temporary directories to avoid mutating real character files.
"""

import os
import sys
import tempfile
import json
from pathlib import Path
from typing import Any, Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.remediate_background_feature_placeholders import (
    analyze_character,
    remediate_file,
)


def test_dry_run_no_write() -> None:
    """Verify dry-run mode reports changes but does not modify files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create generic placeholder character (known background)
        generic_char = {
            "name": "Test Criminal",
            "race": "Human",
            "class": "Rogue",
            "background": "criminal",
            "backgroundFeature": {
                "name": "Feature",
                "description": "Standard background feature",
                "source": "SRD 5.2.1",
            },
            "level": 1,
        }
        
        # Create authored character (should be skipped)
        authored_char = {
            "name": "Test Sage",
            "race": "Elf",
            "class": "Wizard",
            "background": "sage",
            "backgroundFeature": {
                "name": "Researcher",
                "description": "I know where to find obscure information.",
                "source": "SRD 5.2.1",
            },
            "level": 1,
        }
        
        # Write test files
        generic_path = os.path.join(tmpdir, "generic_criminal.json")
        authored_path = os.path.join(tmpdir, "authored_sage.json")
        
        with open(generic_path, "w") as f:
            json.dump(generic_char, f, indent=2)
        with open(authored_path, "w") as f:
            json.dump(authored_char, f, indent=2)
        
        # Capture original file contents
        with open(generic_path, "r") as f:
            original_generic = f.read()
        with open(authored_path, "r") as f:
            original_authored = f.read()
        
        # Run dry-run analysis
        status_gen, updates_gen, err_type_gen = remediate_file(generic_path, dry_run=True)
        status_auth, updates_auth, err_type_auth = remediate_file(authored_path, dry_run=True)
        
        # Assertions
        assert status_gen == "changed", f"Generic char should report 'changed', got {status_gen}"
        assert updates_gen["name_changed"] == True, "Generic name should be flagged for change"
        assert updates_gen["description_changed"] == True, "Generic description should be flagged for change"
        assert err_type_gen is None, f"Generic char should have no error, got {err_type_gen}"
        
        assert status_auth == "skipped", f"Authored char should report 'skipped', got {status_auth}"
        assert err_type_auth is None, f"Authored char should have no error, got {err_type_auth}"
        
        # Verify files unchanged after dry-run
        with open(generic_path, "r") as f:
            after_generic = f.read()
        with open(authored_path, "r") as f:
            after_authored = f.read()
        
        assert original_generic == after_generic, "Dry-run should NOT modify generic file"
        assert original_authored == after_authored, "Dry-run should NOT modify authored file"
        
    print("[PASS] dry-run mode reports changes without modifying files")


def test_apply_updates_generic_only() -> None:
    """Verify apply mode updates generic placeholders, preserves authored content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generic character
        generic_char = {
            "name": "Test Soldier",
            "race": "Human",
            "class": "Fighter",
            "background": "soldier",
            "backgroundFeature": {
                "name": "Feature",
                "description": "Standard background feature",
                "source": "SRD 5.2.1",
            },
            "level": 1,
            "hitPoints": 12,
            "maxHitPoints": 12,
        }
        
        # Write test file
        test_path = os.path.join(tmpdir, "test_soldier.json")
        with open(test_path, "w") as f:
            json.dump(generic_char, f, indent=2)
        
        # Apply remediation
        status, updates, err_type = remediate_file(test_path, dry_run=False)
        
        # Assertions
        assert status == "changed", f"Should report 'changed', got {status}"
        assert err_type is None, f"Should have no error, got {err_type}"
        
        # Read updated file
        with open(test_path, "r") as f:
            updated = json.load(f)
        
        # Verify background feature updated
        assert updated["backgroundFeature"]["name"] == "Military Rank", f"Expected 'Military Rank', got {updated['backgroundFeature']['name']}"
        assert "soldiers" in updated["backgroundFeature"]["description"].lower(), "Description should contain SRD text"
        
        # Verify mechanical fields preserved
        assert updated["hitPoints"] == 12, f"hitPoints should be preserved, got {updated['hitPoints']}"
        assert updated["maxHitPoints"] == 12, f"maxHitPoints should be preserved, got {updated['maxHitPoints']}"
        assert updated["level"] == 1, f"level should be preserved, got {updated['level']}"
        
    print("[PASS] apply mode updates generic placeholders and preserves mechanical fields")


def test_mixed_unknown_background_behavior() -> None:
    """Verify unknown backgrounds remain unchanged (per helper contract)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Unknown background with generic placeholders
        unknown_char = {
            "name": "Test Pirate",
            "race": "Human",
            "class": "Rogue",
            "background": "pirate",  # Unknown - not in known backgrounds
            "backgroundFeature": {
                "name": "Feature",
                "description": "Standard background feature",
                "source": "SRD 5.2.1",
            },
            "level": 1,
        }
        
        # Write test file
        test_path = os.path.join(tmpdir, "test_pirate.json")
        with open(test_path, "w") as f:
            json.dump(unknown_char, f, indent=2)
        
        # Analyze - should detect generic but no suggestion available
        status, data, updates = analyze_character(test_path)
        
        # Since background is unknown, helper returns unchanged values
        # So name_changed and description_changed will be False
        assert status == "skipped", f"Unknown background generic should be 'skipped' (no changes possible), got {status}"
        assert updates["name_changed"] == False, "Unknown bg: name should not be changed"
        assert updates["description_changed"] == False, "Unknown bg: description should not be changed"
        
    print("[PASS] unknown backgrounds remain unchanged (no forced synthetic values)")


def test_fail_open_read_error() -> None:
    """Verify read errors are caught, categorized, and processing continues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create valid character
        valid_char = {
            "name": "Test Valid",
            "race": "Human",
            "class": "Fighter",
            "background": "soldier",
            "backgroundFeature": {
                "name": "Feature",
                "description": "Standard background feature",
            },
            "level": 1,
        }
        
        # Create malformed JSON file
        malformed_path = os.path.join(tmpdir, "malformed.json")
        with open(malformed_path, "w") as f:
            f.write("{invalid json content")
        
        # Create valid file
        valid_path = os.path.join(tmpdir, "valid.json")
        with open(valid_path, "w") as f:
            json.dump(valid_char, f, indent=2)
        
        # Process both with fail-open guarantee
        results = []
        for filepath in [malformed_path, valid_path]:
            status, updates, err_type = remediate_file(filepath, dry_run=True)
            results.append((status, err_type))
        
        # Malformed should error but continue
        malformed_status, malformed_err = results[0]
        assert malformed_status == "error", f"Malformed should error, got {malformed_status}"
        assert malformed_err == "read", f"Malformed error should be 'read', got {malformed_err}"
        
        # Valid should process normally
        valid_status, valid_err = results[1]
        assert valid_status == "changed", f"Valid should be changed, got {valid_status}"
        assert valid_err is None, f"Valid should have no error, got {valid_err}"
        
    print("[PASS] fail-open error handling: read errors caught and categorized, processing continues")


def test_idempotent_second_apply() -> None:
    """Verify second apply run produces zero additional changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Character with generic placeholders
        test_char = {
            "name": "Test Criminal",
            "race": "Human",
            "class": "Rogue",
            "background": "criminal",
            "backgroundFeature": {
                "name": "Feature",
                "description": "Standard background feature",
                "source": "SRD 5.2.1",
            },
            "level": 1,
        }
        
        # Write test file
        test_path = os.path.join(tmpdir, "test_idempotent.json")
        with open(test_path, "w") as f:
            json.dump(test_char, f, indent=2)
        
        # First apply
        status1, _, _ = remediate_file(test_path, dry_run=False)
        assert status1 == "changed", f"First apply should change, got {status1}"
        
        # Second apply
        status2, updates2, _ = remediate_file(test_path, dry_run=False)
        assert status2 == "skipped", f"Second apply should be skipped (idempotent), got {status2}"
        
    print("[PASS] second apply produces zero additional changes (idempotent)")


def main() -> None:
    """Run all remediation script tests."""
    print("=" * 70)
    print("BACKGROUND FEATURE REMEDIATION SCRIPT TESTS")
    print("=" * 70)
    print()
    
    test_dry_run_no_write()
    test_apply_updates_generic_only()
    test_mixed_unknown_background_behavior()
    test_fail_open_read_error()
    test_idempotent_second_apply()
    
    print()
    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
