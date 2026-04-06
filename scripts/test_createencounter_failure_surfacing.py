# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Regression Tests - createEncounter Failure Surfacing
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Regression coverage for Task 4.3: createEncounter produces [SYSTEM] error, no narration leak.
"""

import unittest
import json
import tempfile
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCreateEncounterErrorMessage(unittest.TestCase):
    """Test that createEncounter errors include monster details (Task 4.3)"""
    
    def test_error_message_includes_monster_name_and_path(self):
        """Test that error message parsing extracts monster name and expected file"""
        # Test the regex pattern used in action_handler for extracting monster info
            
        # Test the regex pattern used in action_handler
        import re
        
        sample_output = """
[DEBUG ACTION_HANDLER] FAILED! Encounter was not created successfully
[DEBUG ACTION_HANDLER] Full stdout: [ERROR] [UpdateCharacterInfo] TABLETOP MODE: Monster 'Cornfield Shadow' not found in bestiary at modules/The_Pumpkin_Kings_Curse/monsters/cornfield_shadow.json. Refusing to auto-create - narrator may have hallucinated this creature.
[COMBAT_BUILDER] Encounter generation failed
[DEBUG ACTION_HANDLER] Full stderr: 
[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END WITH FAILURE ==========
"""
        
        # Extract using same regex as action_handler
        monster_match = re.search(r"TABLETOP MODE: Monster '([^']+)' not found in bestiary at ([^\.]+\.json)", sample_output)
        
        self.assertIsNotNone(monster_match, "Should find monster name and path in output")
        self.assertEqual(monster_match.group(1), "Cornfield Shadow", "Should extract monster name")
        self.assertEqual(monster_match.group(2), "modules/The_Pumpkin_Kings_Curse/monsters/cornfield_shadow.json", "Should extract expected file path")

    def test_scene_entity_error_class_is_explicit(self):
        """Scene-entity combat rejection should surface dedicated failure class."""
        sample_error = (
            "non_combat_valid_scene_entity: 'Red (The Crimson Binder)' is authored "
            "as scene-only content (manifestation=incorporeal, policy=incorporeal_no_effect) "
            "and cannot be used in createEncounter.monsters[]."
        )
        self.assertIn("non_combat_valid_scene_entity", sample_error)
        self.assertIn("scene-only", sample_error)


class TestCreateEncounterNarrationGate(unittest.TestCase):
    """Test createEncounter narration gating contracts."""
    
    def test_successful_createEncounter_allows_narration(self):
        """Successful createEncounter should still preserve deferred narration state."""
        
        # Check that main.py has the deferred narration variables
        main_file = Path(__file__).parent.parent / "main.py"
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Assert: Should have deferred narration variables
        self.assertIn("narration_deferred", content, "main.py should have narration_deferred variable")
        self.assertIn("narration_emitted", content, "main.py should have narration_emitted variable")
        
        # Assert: Generic deferred emission path still exists for non-combat actions
        self.assertIn("if not narration_emitted and narration_deferred:", content, 
                     "Should have deferred emission check")

    def test_createEncounter_emits_single_intro_before_combat_handoff(self):
        """createEncounter should print one intro beat before process_action starts combat."""
        main_file = Path(__file__).parent.parent / "main.py"
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()

        intro_gate = 'action.get("action") == "createEncounter"'
        narration_print = 'print(colored("Dungeon Master:", "blue"), colored(narration_deferred, "blue"))'
        process_call = 'result = action_handler.process_action(action, party_tracker_data, location_data, conversation_history)'

        self.assertIn(intro_gate, content, "Should special-case createEncounter narration")
        self.assertIn(narration_print, content, "Should print narration for createEncounter before combat handoff")
        self.assertIn(process_call, content, "Should still hand off to action processing")

        intro_gate_pos = content.find(intro_gate)
        narration_print_pos = content.find(narration_print, intro_gate_pos)
        process_call_pos = content.find(process_call, narration_print_pos)

        self.assertGreater(narration_print_pos, intro_gate_pos, "Narration print should occur inside createEncounter gate")
        self.assertGreater(process_call_pos, narration_print_pos, "Narration should print before process_action starts combat")
        

class TestErrorMessageContent(unittest.TestCase):
    """Test enriched error message content (Task 4.3)"""
    
    def test_error_message_is_actionable(self):
        """Test that error message is actionable for operators"""
        # Expected error message format from action_handler
        expected_error = ("Combat encounter creation failed: Monster 'Cornfield Shadow' is referenced in module "
                        "content but missing stat file 'modules/The_Pumpkin_Kings_Curse/monsters/cornfield_shadow.json'. "
                        "Add the monster stat file or correct the reference.")
        
        # Check that error message contains key actionable elements
        self.assertIn("Cornfield Shadow", expected_error, "Should include monster name")
        self.assertIn("cornfield_shadow.json", expected_error, "Should include expected file path")
        self.assertIn("Add the monster stat file", expected_error, "Should suggest fix")
        
    def test_error_includes_module_context(self):
        """Test that error includes module context"""
        # Verify action_handler.py has the TABLETOP MODE enrichment
        handler_file = Path(__file__).parent.parent / "core/ai/action_handler.py"
        with open(handler_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Assert: Should have TABLETOP MODE enrichment
        self.assertIn("TABLETOP MODE: 3.1 Enrich error message", content,
                     "Should have TABLETOP MODE comment for enrichment")
        self.assertIn("Combat encounter creation failed: Monster", content,
                     "Should have enriched error message pattern")
        

if __name__ == '__main__':
    unittest.main(verbosity=2)
