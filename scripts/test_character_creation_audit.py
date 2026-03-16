#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Unit-style assertions for character creation audit result classes."""

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.character_creation_audit import (
    AUDIT_RESULT_COMPLETENESS_ERROR,
    AUDIT_RESULT_SCHEMA_ERROR,
    AUDIT_RESULT_SUCCESS,
    audit_character_creation,
    audit_profile_readiness,
    is_generic_background_feature_name,
    is_generic_background_feature_description,
    sanitize_readiness_repair_patch,
    apply_readiness_repair_patch,
    get_mechanical_snapshot,
    diff_mechanical_snapshot,
)
from utils import pc_manager


def _base_payload() -> dict:
    return {
        "name": "Audit Tester",
        "race": "Human",
        "class": "Fighter",
        "background": "Soldier",
        "personality_traits": "Disciplined and focused.",
        "ideals": "Duty.",
        "bonds": "My unit.",
        "flaws": "I overcommit.",
        "backstory": "Former soldier seeking new purpose.",
        "backgroundFeature": {
            "name": "Military Rank",
            "description": "I can pull rank with soldiers.",
            "source": "SRD 5.2.1",
        },
    }


def test_helper_detection() -> None:
    """Test placeholder helper detection functions."""
    # True cases for name
    assert is_generic_background_feature_name("") == True, "Empty string should be generic"
    assert is_generic_background_feature_name("Feature") == True, "'Feature' should be generic"
    assert is_generic_background_feature_name("  feature  ") == True, "Whitespace-padded 'feature' should be generic"
    assert is_generic_background_feature_name("BACKGROUND FEATURE") == True, "Uppercase should be generic"
    assert is_generic_background_feature_name("Unknown") == True, "'Unknown' should be generic"
    assert is_generic_background_feature_name(None) == True, "None should be generic"
    
    # False cases for name
    assert is_generic_background_feature_name("Researcher") == False, "'Researcher' should not be generic"
    assert is_generic_background_feature_name("Criminal Contact") == False, "'Criminal Contact' should not be generic"
    assert is_generic_background_feature_name("Military Rank") == False, "'Military Rank' should not be generic"
    
    # True cases for description
    assert is_generic_background_feature_description("") == True, "Empty string desc should be generic"
    assert is_generic_background_feature_description("Standard background feature") == True, "Standard text should be generic"
    assert is_generic_background_feature_description("A defining feature from your background.") == True, "Defining text should be generic"
    assert is_generic_background_feature_description("  STANDARD BACKGROUND FEATURE  ") == True, "Whitespace-padded uppercase should be generic"
    
    # False cases for description
    assert is_generic_background_feature_description("You have a reliable contact in the criminal underworld.") == False, "Authored desc should not be generic"
    assert is_generic_background_feature_description("I can invoke my rank to influence soldiers.") == False, "Authored military desc should not be generic"
    
    print("[PASS] placeholder helper detection validated")


def test_completeness_error_on_generic_placeholders() -> None:
    """Test that generic placeholders trigger completeness errors."""
    payload = deepcopy(_base_payload())
    payload["backgroundFeature"] = {
        "name": "Feature",
        "description": "Standard background feature",
    }
    
    result = audit_character_creation(payload, source="test", enable_enrichment=False)
    
    assert result.result_type == AUDIT_RESULT_COMPLETENESS_ERROR, "Generic placeholders should trigger completeness_error"
    assert "backgroundFeature.name" in result.missing_paths, "Generic name should be in missing_paths"
    assert "backgroundFeature.description" in result.missing_paths, "Generic description should be in missing_paths"
    
    error_paths = {e["path"] for e in result.errors}
    assert "backgroundFeature.name" in error_paths, "Generic name should have error entry"
    assert "backgroundFeature.description" in error_paths, "Generic description should have error entry"
    
    print("[PASS] completeness error on generic placeholders validated")


def test_authored_value_success_and_preservation() -> None:
    """Test that authored non-placeholder values succeed and are preserved."""
    payload = deepcopy(_base_payload())
    payload["backgroundFeature"] = {
        "name": "Criminal Contact",
        "description": "You have a reliable contact who acts as your liaison to a network of other criminals.",
    }
    
    result = audit_character_creation(payload, source="test", enable_enrichment=False)
    
    assert result.result_type == AUDIT_RESULT_SUCCESS, "Authored values should result in success"
    
    # Verify authored values are preserved in normalized_data
    normalized_bg = result.normalized_data.get("backgroundFeature", {})
    assert normalized_bg.get("name") == "Criminal Contact", "Authored name should be preserved"
    assert normalized_bg.get("description") == "You have a reliable contact who acts as your liaison to a network of other criminals.", "Authored description should be preserved"
    
    print("[PASS] authored value success and preservation validated")


def test_profile_readiness_placeholder_signaling() -> None:
    """Test that profile readiness flags generic placeholders."""
    # Test with generic placeholders
    generic_payload = deepcopy(_base_payload())
    generic_payload["backgroundFeature"] = {
        "name": "Feature",
        "description": "A defining feature from your background.",
    }
    
    profile_result = audit_profile_readiness(generic_payload)
    
    assert profile_result["profile_ready"] == False, "Generic placeholders should result in profile not ready"
    assert "backgroundFeature.name" in profile_result["missing_profile_fields"], "Generic name should be in missing_profile_fields"
    assert "backgroundFeature.description" in profile_result["missing_profile_fields"], "Generic description should be in missing_profile_fields"
    
    # Test with authored values
    authored_payload = deepcopy(_base_payload())
    authored_payload["backgroundFeature"] = {
        "name": "Researcher",
        "description": "When you attempt to learn or recall a piece of lore, you often know where to obtain it.",
    }
    
    # Add required appearance fields to get profile_ready=True
    authored_payload["age"] = "25"
    authored_payload["height"] = "5'10"
    authored_payload["weight"] = "160 lbs"
    authored_payload["eyes"] = "Blue"
    authored_payload["skin"] = "Fair"
    authored_payload["hair"] = "Brown"
    
    authored_result = audit_profile_readiness(authored_payload)
    
    # Note: profile_ready may still be False due to missing appearance fields in base_payload
    # But background feature fields should NOT be flagged as missing
    assert "backgroundFeature.name" not in authored_result["missing_profile_fields"], "Authored name should not be in missing_profile_fields"
    assert "backgroundFeature.description" not in authored_result["missing_profile_fields"], "Authored description should not be in missing_profile_fields"
    
    print("[PASS] profile readiness placeholder signaling validated")


def test_readiness_repair_regression() -> None:
    """Regression test: repair apply replaces generic placeholders without changing mechanical fields."""
    # 1. Whitelist + sanitize regression
    patch = {
        "updates": {
            "backgroundFeature.name": "Criminal Contact",
            "backgroundFeature.description": "You have a trusted liaison in criminal circles.",
            "hitPoints": "9999",  # should be rejected - not in whitelist
            "armorClass": "25",   # should be rejected - not in whitelist
        }
    }
    sanitized = sanitize_readiness_repair_patch(patch)
    
    # Verify whitelist accepts narrative fields
    assert "backgroundFeature.name" in sanitized, "Sanitize should accept backgroundFeature.name"
    assert "backgroundFeature.description" in sanitized, "Sanitize should accept backgroundFeature.description"
    
    # Verify whitelist rejects mechanical fields
    assert "hitPoints" not in sanitized, "Sanitize should reject hitPoints (mechanical field)"
    assert "armorClass" not in sanitized, "Sanitize should reject armorClass (mechanical field)"
    
    print("[PASS] repair sanitize whitelist validated (accepts bg fields, rejects mechanical)")
    
    # 2. Apply patch regression (generic -> authored)
    payload = deepcopy(_base_payload())
    # Set generic placeholder values
    payload["backgroundFeature"] = {
        "name": "Feature",
        "description": "Standard background feature",
        "source": "SRD 5.2.1",
    }
    
    # Pre-apply completeness check - should fail due to generic placeholders
    pre_audit = audit_character_creation(payload, source="test", enable_enrichment=False)
    assert pre_audit.result_type == AUDIT_RESULT_COMPLETENESS_ERROR, "Pre-apply should fail due to generic placeholders"
    
    repair_updates = {
        "backgroundFeature.name": "Criminal Contact",
        "backgroundFeature.description": "You have a trusted liaison in criminal circles.",
    }
    patched = apply_readiness_repair_patch(payload, repair_updates)
    
    # Verify patched payload has new authored values
    assert patched["backgroundFeature"]["name"] == "Criminal Contact", "Patched name should be authored value"
    assert "trusted liaison" in patched["backgroundFeature"]["description"].lower(), "Patched description should be authored value"
    assert patched["backgroundFeature"]["source"] == "SRD 5.2.1", "Background feature source should be preserved"
    
    print("[PASS] repair apply replaces generic placeholders with authored values")
    
    # 3. Mechanical immutability regression
    before_snapshot = get_mechanical_snapshot(payload)
    after_snapshot = get_mechanical_snapshot(patched)
    diff = diff_mechanical_snapshot(before_snapshot, after_snapshot)
    
    assert diff == [], f"Mechanical snapshot should be unchanged, but changes detected: {diff}"
    
    print("[PASS] mechanical fields unchanged after repair apply")
    
    # 4. End-to-end readiness regression
    # Post-apply payload should pass completeness with authored replacements
    post_audit = audit_character_creation(patched, source="test", enable_enrichment=False)
    assert post_audit.result_type == AUDIT_RESULT_SUCCESS, "Post-apply should pass with authored replacements"
    
    print("[PASS] end-to-end readiness: generic placeholders replaced, completeness achieved")


def test_backstory_completeness() -> None:
    """Test that missing backstory triggers completeness_error."""
    payload = deepcopy(_base_payload())
    # Remove backstory to simulate incomplete character
    payload["backstory"] = ""
    
    result = audit_character_creation(payload, source="test", enable_enrichment=False)
    
    assert result.result_type == AUDIT_RESULT_COMPLETENESS_ERROR, "Missing backstory should trigger completeness_error"
    assert "backstory" in result.missing_paths, "backstory should be in missing_paths"
    
    # Verify authored backstory passes
    authored_payload = deepcopy(_base_payload())
    authored_payload["backstory"] = "A mysterious past full of secrets."
    authored_result = audit_character_creation(authored_payload, source="test", enable_enrichment=False)
    assert authored_result.result_type == AUDIT_RESULT_SUCCESS, "Authored backstory should result in success"
    
    print("[PASS] backstory completeness validation")


def test_character_creation_prompt_formatting() -> None:
    """Regression test: DM interview prompt formats without leaking raw placeholders."""
    party_tracker = {
        "partyMembers": ["Blairen", "Vitreol", "Chronos"],
        "worldConditions": {
            "currentLocation": "Rangers' Command Post",
            "currentArea": "Rangers' Outpost",
        },
    }

    prompt = pc_manager.get_character_creation_prompt(
        module_name="The_Thornwood_Watch",
        character_name="Valerius",
        party_tracker=party_tracker,
        level=1,
        is_mid_campaign=True,
        active_pc="Blairen",
        current_location="Rangers' Command Post",
    )

    assert prompt, "Character creation prompt should not be empty"
    assert not prompt.startswith("# SPDX"), "SPDX header should be stripped from model prompt"
    assert "{module_name}" not in prompt, "module_name placeholder should be formatted"
    assert "{level_context}" not in prompt, "level_context placeholder should be formatted"
    assert "{experience_points}" not in prompt, "experience_points placeholder should be formatted"
    assert "{exp_next}" not in prompt, "exp_next placeholder should be formatted"
    assert "spellSlots {}" not in prompt, "Literal format braces should not leak into the prompt"
    assert "Begin by asking what kind of hero they want to become!" in prompt, "Prompt body should remain intact"

    print("[PASS] character creation prompt formatting validated")


def main() -> None:
    good_payload = _base_payload()
    success_result = audit_character_creation(good_payload, source="test", enable_enrichment=False)
    assert success_result.result_type == AUDIT_RESULT_SUCCESS, "Expected success result"

    schema_error_payload = deepcopy(good_payload)
    schema_error_payload["level"] = "invalid"
    schema_result = audit_character_creation(schema_error_payload, source="test", enable_enrichment=False)
    assert schema_result.result_type == AUDIT_RESULT_SCHEMA_ERROR, "Expected schema_error result"

    completeness_payload = deepcopy(good_payload)
    completeness_payload["personality_traits"] = ""
    completeness_result = audit_character_creation(completeness_payload, source="test", enable_enrichment=False)
    assert completeness_result.result_type == AUDIT_RESULT_COMPLETENESS_ERROR, "Expected completeness_error result"

    print("[PASS] character_creation_audit deterministic result classes validated")
    
    # Run new placeholder detection tests
    test_helper_detection()
    test_completeness_error_on_generic_placeholders()
    test_authored_value_success_and_preservation()
    test_profile_readiness_placeholder_signaling()
    
    # Run backstory completeness test
    test_backstory_completeness()

    # Run DM interview prompt formatting regression test
    test_character_creation_prompt_formatting()

    # Run readiness repair regression tests
    test_readiness_repair_regression()


if __name__ == "__main__":
    main()
