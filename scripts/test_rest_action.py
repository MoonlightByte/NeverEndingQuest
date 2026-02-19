#!/usr/bin/env python3
"""
Test script for rest automation action.

Validates:
1. Short rest: Warlock gets spell slots, others don't
2. Long rest: Full restoration for all classes
3. Exhaustion removal on long rest
4. Fuzzy character name matching
5. 5e compliance (no auto-heal on short rest)
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.file_operations import safe_read_json, safe_write_json
from core.ai.action_handler import _process_character_rest


def create_test_character(name, char_class, hp, max_hp, spell_slots=None, conditions=None, features=None):
    """Create a test character with minimal required fields."""
    character = {
        "character_role": "player",
        "character_type": "player",
        "name": name,
        "type": "player",
        "size": "Medium",
        "level": 5,
        "race": "Human",
        "class": char_class,
        "alignment": "neutral good",
        "background": "Soldier",
        "status": "alive",
        "condition": "none",
        "condition_affected": conditions or [],
        "hitPoints": hp,
        "maxHitPoints": max_hp,
        "armorClass": 15,
        "initiative": 2,
        "speed": 30,
        "abilities": {
            "strength": 14,
            "dexterity": 12,
            "constitution": 13,
            "intelligence": 10,
            "wisdom": 16,
            "charisma": 8
        },
        "savingThrows": [],
        "skills": [],
        "proficiencyBonus": 3,
        "senses": {"passivePerception": 12},
        "languages": ["Common"],
        "proficiencies": {"armor": [], "weapons": [], "tools": []},
        "damageVulnerabilities": [],
        "damageResistances": [],
        "damageImmunities": [],
        "conditionImmunities": [],
        "classFeatures": features or [],
        "racialTraits": [],
        "backgroundFeature": {"name": "Test", "description": "Test feature"},
        "temporaryEffects": [],
        "injuries": [],
        "equipment_effects": [],
        "feats": [],
        "equipment": [],
        "attacksAndSpellcasting": [],
        "spellcasting": {
            "ability": "wisdom" if "Cleric" in char_class or "Druid" in char_class else "intelligence",
            "spellSaveDC": 14,
            "spellAttackBonus": 6,
            "spells": {
                "cantrips": [],
                "level1": ["Spell1"],
                "level2": ["Spell2"]
            },
            "spellSlots": spell_slots or {
                "level1": {"current": 2, "max": 4},
                "level2": {"current": 1, "max": 3}
            }
        },
        "currency": {"gold": 50, "silver": 10, "copper": 0},
        "experience_points": 6500,
        "exp_required_for_next_level": 14000,
        "personality_traits": "",
        "ideals": "",
        "bonds": "",
        "flaws": ""
    }
    return character


def test_short_rest_warlock():
    """Test that Warlock gets spell slots back on short rest."""
    print("\n[Test] Short Rest - Warlock")
    print("-" * 50)
    
    # Create temp directory and character
    with tempfile.TemporaryDirectory() as temp_dir:
        characters_dir = os.path.join(temp_dir, "characters")
        os.makedirs(characters_dir)
        
        # Create a Warlock with used spell slots
        warlock = create_test_character(
            "Grimm the Warlock",
            "Warlock",
            hp=25,
            max_hp=35,
            spell_slots={
                "level1": {"current": 0, "max": 4},
                "level2": {"current": 0, "max": 2}
            }
        )
        
        char_file = os.path.join(characters_dir, "grimm_the_warlock.json")
        safe_write_json(char_file, warlock)
        
        # Mock party tracker
        party_tracker = {
            "module": "Test Module",
            "partyMembers": ["Grimm the Warlock"],
            "active_character": "Grimm the Warlock"
        }
        
        # Process short rest
        result = _process_character_rest("Grimm the Warlock", "short", party_tracker)
        
        if result is None:
            print("[FAIL] Rest processing failed")
            return False
        
        # Warlock should get spell slots back
        if result["spell_slots_restored"] > 0:
            print(f"[PASS] Warlock restored {result['spell_slots_restored']} spell slots")
        else:
            print(f"[FAIL] Warlock should have restored spell slots, got {result['spell_slots_restored']}")
            return False
        
        # Warlock should NOT auto-heal on short rest
        if result["hp_restored"] == 0:
            print("[PASS] No HP auto-restored on short rest (5e compliant)")
        else:
            print(f"[FAIL] HP should not auto-restore on short rest, got {result['hp_restored']}")
            return False
        
        return True


def test_short_rest_wizard():
    """Test that Wizard does NOT get spell slots back on short rest."""
    print("\n[Test] Short Rest - Wizard")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        characters_dir = os.path.join(temp_dir, "characters")
        os.makedirs(characters_dir)
        
        # Create a Wizard with used spell slots
        wizard = create_test_character(
            "Elara the Wise",
            "Wizard",
            hp=20,
            max_hp=30,
            spell_slots={
                "level1": {"current": 0, "max": 4},
                "level2": {"current": 0, "max": 3}
            }
        )
        
        char_file = os.path.join(characters_dir, "elara_the_wise.json")
        safe_write_json(char_file, wizard)
        
        party_tracker = {
            "module": "Test Module",
            "partyMembers": ["Elara the Wise"],
            "active_character": "Elara the Wise"
        }
        
        result = _process_character_rest("Elara the Wise", "short", party_tracker)
        
        if result is None:
            print("[FAIL] Rest processing failed")
            return False
        
        # Wizard should NOT get spell slots back on short rest
        if result["spell_slots_restored"] == 0:
            print("[PASS] Wizard correctly did NOT restore spell slots on short rest (5e compliant)")
        else:
            print(f"[FAIL] Wizard should NOT restore spell slots on short rest, got {result['spell_slots_restored']}")
            return False
        
        # No HP restoration
        if result["hp_restored"] == 0:
            print("[PASS] No HP auto-restored on short rest")
        else:
            print(f"[FAIL] HP should not auto-restore on short rest, got {result['hp_restored']}")
            return False
        
        return True


def test_long_rest_full_restoration():
    """Test that long rest fully restores HP, spell slots, and features."""
    print("\n[Test] Long Rest - Full Restoration")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        characters_dir = os.path.join(temp_dir, "characters")
        os.makedirs(characters_dir)
        
        # Create a Cleric with depleted resources
        features = [
            {
                "name": "Channel Divinity",
                "description": "Turn undead",
                "usage": {"current": 0, "max": 2, "refreshOn": "shortRest"}
            },
            {
                "name": "Destroy Undead",
                "description": "Destroy CR 1/2 or lower",
                "usage": {"current": 0, "max": 1, "refreshOn": "longRest"}
            }
        ]
        
        cleric = create_test_character(
            "Brother Aldric",
            "Cleric",
            hp=10,
            max_hp=40,
            spell_slots={
                "level1": {"current": 0, "max": 4},
                "level2": {"current": 0, "max": 3}
            },
            features=features
        )
        
        char_file = os.path.join(characters_dir, "brother_aldric.json")
        safe_write_json(char_file, cleric)
        
        party_tracker = {
            "module": "Test Module",
            "partyMembers": ["Brother Aldric"],
            "active_character": "Brother Aldric"
        }
        
        result = _process_character_rest("Brother Aldric", "long", party_tracker)
        
        if result is None:
            print("[FAIL] Rest processing failed")
            return False
        
        # Should restore all HP
        if result["hp_restored"] == 30:
            print(f"[PASS] Restored {result['hp_restored']} HP (10 -> 40)")
        else:
            print(f"[FAIL] Should restore 30 HP, got {result['hp_restored']}")
            return False
        
        # Should restore all spell slots
        if result["spell_slots_restored"] == 7:  # 4 level 1 + 3 level 2
            print(f"[PASS] Restored {result['spell_slots_restored']} spell slots")
        else:
            print(f"[FAIL] Should restore 7 spell slots, got {result['spell_slots_restored']}")
            return False
        
        # Should refresh both features
        if len(result["features_reset"]) == 2:
            print(f"[PASS] Refreshed {len(result['features_reset'])} features")
        else:
            print(f"[FAIL] Should refresh 2 features, got {len(result['features_reset'])}")
            return False
        
        return True


def test_exhaustion_removal():
    """Test that exhaustion is removed on long rest."""
    print("\n[Test] Long Rest - Exhaustion Removal")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        characters_dir = os.path.join(temp_dir, "characters")
        os.makedirs(characters_dir)
        
        # Create character with exhaustion (as string per schema)
        fighter = create_test_character(
            "Tough Guy",
            "Fighter",
            hp=40,
            max_hp=50,
            conditions=["exhaustion", "prone"]  # String format per char_schema.json
        )
        
        char_file = os.path.join(characters_dir, "tough_guy.json")
        safe_write_json(char_file, fighter)
        
        party_tracker = {
            "module": "Test Module",
            "partyMembers": ["Tough Guy"],
            "active_character": "Tough Guy"
        }
        
        result = _process_character_rest("Tough Guy", "long", party_tracker)
        
        if result is None:
            print("[FAIL] Rest processing failed")
            return False
        
        # Should detect and remove exhaustion
        if result["exhaustion_reduced"]:
            print("[PASS] Exhaustion correctly detected and flagged for removal")
        else:
            print("[FAIL] Exhaustion should be detected and removed")
            return False
        
        return True


def test_fuzzy_name_matching():
    """Test that fuzzy name matching works for characters."""
    print("\n[Test] Fuzzy Character Name Matching")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        characters_dir = os.path.join(temp_dir, "characters")
        os.makedirs(characters_dir)
        
        # Create character with complex name
        paladin = create_test_character(
            "Sir Gawain the Pure",
            "Paladin",
            hp=30,
            max_hp=45
        )
        
        char_file = os.path.join(characters_dir, "sir_gawain_the_pure.json")
        safe_write_json(char_file, paladin)
        
        party_tracker = {
            "module": "Test Module",
            "partyMembers": ["Sir Gawain the Pure"],
            "active_character": "Sir Gawain the Pure"
        }
        
        # Try with partial name
        result = _process_character_rest("Gawain", "long", party_tracker)
        
        if result is not None:
            print("[PASS] Fuzzy matching found character with partial name 'Gawain'")
        else:
            print("[FAIL] Fuzzy matching failed to find character")
            return False
        
        return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Rest Automation Test Suite")
    print("Testing 5e-compliant rest mechanics")
    print("=" * 60)
    
    tests = [
        ("Short Rest - Warlock", test_short_rest_warlock),
        ("Short Rest - Wizard", test_short_rest_wizard),
        ("Long Rest - Full Restoration", test_long_rest_full_restoration),
        ("Long Rest - Exhaustion Removal", test_exhaustion_removal),
        ("Fuzzy Name Matching", test_fuzzy_name_matching),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test_name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)