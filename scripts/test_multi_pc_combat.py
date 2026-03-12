# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Test Suite for MultiPCCombatManager
Phase 3 Refactoring Verification

This module provides comprehensive unit tests for the refactored MultiPCCombatManager,
including tests for:
- Sub-manager delegation pattern
- LLM prompt integration
- Combat state management
- Edge cases and error conditions

Usage:
    python scripts/test_multi_pc_combat.py
    python scripts/test_multi_pc_combat.py -v  # Verbose mode
"""

import unittest
import sys
import os
import json
import types

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.managers.multi_pc_combat import (
    MultiPCCombatManager,
    CombatStateManager,
    TurnQueueManager,
    PCStatus,
    Combatant,
    CombatantType,
    temporary_combat_manager,
    temporary_combat_callback,
    reset_combat_state,
    get_combat_manager,
    create_combat_manager,
    end_combat_session,
    modify_combat_prompt_for_multi_pc,
    get_multi_pc_initiative_narrative,
)


class TestCombatStateManager(unittest.TestCase):
    """Test CombatStateManager sub-manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state_mgr = CombatStateManager()
        self.sample_party = {
            "partyMembers": ["Acheron", "Merisiel"],
            "active_character": "Acheron"
        }
    
    def test_initialization(self):
        """Test CombatStateManager initializes correctly."""
        self.assertIsNotNone(self.state_mgr)
        self.assertEqual(self.state_mgr.pc_states, {})
        self.assertEqual(self.state_mgr.current_round, 1)
        self.assertIsNone(self.state_mgr.current_pc_name)
    
    def test_initialize_from_party(self):
        """Test initializing from party data."""
        self.state_mgr.initialize_from_party(self.sample_party)
        
        self.assertIn("Acheron", self.state_mgr.pc_states)
        self.assertIn("Merisiel", self.state_mgr.pc_states)
        self.assertEqual(len(self.state_mgr.pc_states), 2)
        
        # Check default values
        acheron = self.state_mgr.pc_states["Acheron"]
        self.assertEqual(acheron.status, PCStatus.READY)
        self.assertEqual(acheron.death_save_successes, 0)
        self.assertEqual(acheron.death_save_failures, 0)
    
    def test_get_available_pcs(self):
        """Test getting available PCs."""
        self.state_mgr.initialize_from_party(self.sample_party)
        
        available = self.state_mgr.get_available_pcs()
        self.assertEqual(len(available), 2)
        self.assertIn("Acheron", available)
        self.assertIn("Merisiel", available)
        
        # Mark one as acted
        self.state_mgr.pc_states["Acheron"].mark_acted()
        available = self.state_mgr.get_available_pcs()
        self.assertEqual(len(available), 1)
        self.assertIn("Merisiel", available)
    
    def test_get_incapacitated_pcs(self):
        """Test identifying incapacitated PCs."""
        self.state_mgr.initialize_from_party(self.sample_party)
        
        # Initially no one is incapacitated
        incapacitated = self.state_mgr.get_incapacitated_pcs()
        self.assertEqual(len(incapacitated), 0)
        
        # Incapacitate one PC
        self.state_mgr.pc_states["Acheron"].status = PCStatus.INCAPACITATED
        self.state_mgr.pc_states["Acheron"].current_hp = 0
        
        incapacitated = self.state_mgr.get_incapacitated_pcs()
        self.assertEqual(len(incapacitated), 1)
        self.assertIn("Acheron", incapacitated)
    
    def test_update_pc_hp(self):
        """Test HP updates and status transitions."""
        self.state_mgr.initialize_from_party(self.sample_party)
        
        # Set initial HP
        self.state_mgr.pc_states["Acheron"].current_hp = 20
        self.state_mgr.pc_states["Acheron"].max_hp = 20
        
        # Damage
        self.state_mgr.update_pc_hp("Acheron", 10)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].current_hp, 10)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].status, PCStatus.READY)
        
        # Drop to 0 HP
        self.state_mgr.update_pc_hp("Acheron", 0)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].current_hp, 0)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].status, PCStatus.INCAPACITATED)
        
        # Heal back up
        self.state_mgr.update_pc_hp("Acheron", 5)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].current_hp, 5)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].status, PCStatus.READY)
    
    def test_death_saves(self):
        """Test death saving throw mechanics."""
        self.state_mgr.initialize_from_party(self.sample_party)
        
        # Set up incapacitated PC
        self.state_mgr.pc_states["Acheron"].status = PCStatus.INCAPACITATED
        self.state_mgr.pc_states["Acheron"].current_hp = 0
        
        # Test successful death save - returns True (combat continues, PC not dead)
        combat_continues, message = self.state_mgr.pc_states["Acheron"].apply_death_save(15)
        self.assertTrue(combat_continues)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].death_save_successes, 1)
        
        # Test failed death save - returns True (combat continues, PC not dead yet)
        combat_continues, message = self.state_mgr.pc_states["Acheron"].apply_death_save(5)
        self.assertTrue(combat_continues)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].death_save_failures, 1)
        
        # Test critical success (natural 20) - PC recovers, returns True (combat continues)
        self.state_mgr.pc_states["Acheron"].death_save_successes = 2
        combat_continues, message = self.state_mgr.pc_states["Acheron"].apply_death_save(20)
        self.assertTrue(combat_continues)
        self.assertEqual(self.state_mgr.pc_states["Acheron"].status, PCStatus.READY)  # Natural 20 sets to READY, not STABLE
        
        # Test critical failure (natural 1) - adds 2 failures, returns True (combat continues, not dead yet)
        self.state_mgr.pc_states["Merisiel"].status = PCStatus.INCAPACITATED
        self.state_mgr.pc_states["Merisiel"].current_hp = 0
        combat_continues, message = self.state_mgr.pc_states["Merisiel"].apply_death_save(1)
        self.assertTrue(combat_continues)  # PC not dead yet, just 2 failures
        self.assertEqual(self.state_mgr.pc_states["Merisiel"].death_save_failures, 2)
    
    def test_death_from_failed_saves(self):
        """Test PC death from 3 failed saves."""
        self.state_mgr.initialize_from_party(self.sample_party)
        
        self.state_mgr.pc_states["Acheron"].status = PCStatus.INCAPACITATED
        self.state_mgr.pc_states["Acheron"].current_hp = 0
        self.state_mgr.pc_states["Acheron"].death_save_failures = 2
        
        # Third failed save - PC dies, so combat_continues returns False
        combat_continues, message = self.state_mgr.pc_states["Acheron"].apply_death_save(2)
        self.assertFalse(combat_continues)  # PC is dead, combat doesn't continue for them
        self.assertEqual(self.state_mgr.pc_states["Acheron"].status, PCStatus.DEAD)


class TestTurnQueueManager(unittest.TestCase):
    """Test TurnQueueManager sub-manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.turn_mgr = TurnQueueManager()
        self.state_mgr = CombatStateManager()
        
        # Link the managers
        self.turn_mgr.state_manager = self.state_mgr
        
        self.sample_encounter = {
            "creatures": [
                {"name": "Goblin", "type": "enemy", "armorClass": 15, "hp": 7, "maxHp": 7},
                {"name": "Orc", "type": "enemy", "armorClass": 13, "hp": 15, "maxHp": 15},
            ]
        }
        
        self.sample_party = {
            "partyMembers": ["Acheron", "Merisiel"],
            "active_character": "Acheron"
        }
    
    def test_initialization(self):
        """Test TurnQueueManager initializes correctly."""
        self.assertIsNotNone(self.turn_mgr)
        self.assertEqual(self.turn_mgr.turn_queue, [])
        self.assertEqual(self.turn_mgr.current_turn_index, 0)
        self.assertFalse(self.turn_mgr.pc_phase_complete)
    
    def test_initialize_turn_queue(self):
        """Test building turn queue from encounter."""
        self.state_mgr.initialize_from_party(self.sample_party)
        self.state_mgr.pc_states["Acheron"].initiative_modifier = 2
        self.state_mgr.pc_states["Acheron"].current_hp = 20
        self.state_mgr.pc_states["Acheron"].max_hp = 20
        self.state_mgr.pc_states["Merisiel"].initiative_modifier = 3
        self.state_mgr.pc_states["Merisiel"].current_hp = 18
        self.state_mgr.pc_states["Merisiel"].max_hp = 18
        
        self.turn_mgr.initialize_turn_queue(self.sample_encounter)
        
        # Should have 4 combatants (2 PCs + 2 enemies)
        self.assertEqual(len(self.turn_mgr.turn_queue), 4)
        
        # Verify all are present
        names = [c.name for c in self.turn_mgr.turn_queue]
        self.assertIn("Acheron", names)
        self.assertIn("Merisiel", names)
        self.assertIn("Goblin", names)
        self.assertIn("Orc", names)
    
    def test_get_current_actor(self):
        """Test getting current actor from queue."""
        self.state_mgr.initialize_from_party(self.sample_party)
        self.state_mgr.pc_states["Acheron"].initiative_modifier = 2
        self.state_mgr.pc_states["Acheron"].current_hp = 20
        self.state_mgr.pc_states["Acheron"].max_hp = 20
        
        self.turn_mgr.initialize_turn_queue(self.sample_encounter)
        
        # Queue is sorted by initiative, so get first
        current = self.turn_mgr.get_current_actor()
        self.assertIsNotNone(current)
        self.assertIsInstance(current, Combatant)
    
    def test_advance_turn(self):
        """Test turn advancement."""
        self.state_mgr.initialize_from_party(self.sample_party)
        self.state_mgr.pc_states["Acheron"].initiative_modifier = 2
        self.state_mgr.pc_states["Acheron"].current_hp = 20
        self.state_mgr.pc_states["Acheron"].max_hp = 20
        self.state_mgr.pc_states["Merisiel"].initiative_modifier = 3
        self.state_mgr.pc_states["Merisiel"].current_hp = 18
        self.state_mgr.pc_states["Merisiel"].max_hp = 18
        
        self.turn_mgr.initialize_turn_queue(self.sample_encounter)
        
        initial_actor = self.turn_mgr.get_current_actor()
        next_actor, rolled_over = self.turn_mgr.advance_turn()

        self.assertIsNotNone(next_actor)
        self.assertNotEqual(initial_actor.name, next_actor.name)
        self.assertFalse(rolled_over)  # First advance, no wraparound
    
    def test_get_remaining_enemies(self):
        """Test getting remaining enemies for the round."""
        self.state_mgr.initialize_from_party(self.sample_party)
        for pc_name in ["Acheron", "Merisiel"]:
            self.state_mgr.pc_states[pc_name].initiative_modifier = 2
            self.state_mgr.pc_states[pc_name].current_hp = 20
            self.state_mgr.pc_states[pc_name].max_hp = 20
        
        self.turn_mgr.initialize_turn_queue(self.sample_encounter)
        
        remaining = self.turn_mgr.get_remaining_enemies_for_round()
        self.assertEqual(len(remaining), 2)  # Both enemies
        
        # Simulate enemy phase complete
        self.turn_mgr.pc_phase_complete = True
        
        # All enemies should be in remaining list
        remaining = self.turn_mgr.get_remaining_enemies_for_round()
        self.assertIn("Goblin", remaining)
        self.assertIn("Orc", remaining)

    def test_get_remaining_enemies_filters_invalid_statuses(self):
        """C4 regression: include only living non-PC actors."""
        self.turn_mgr.current_turn_index = 0
        self.turn_mgr.turn_queue = [
            Combatant("Goblin A", CombatantType.ENEMY, 15, 7, 7, 15, "alive"),
            Combatant("Fallen Orc", CombatantType.ENEMY, 12, 0, 15, 13, "dead"),
            Combatant("Guard Ally", CombatantType.NPC, 10, 12, 12, 14, "alive"),
            Combatant("Stunned Ally", CombatantType.NPC, 9, 0, 12, 13, "unconscious"),
            Combatant("Acheron", CombatantType.PC, 18, 21, 21, 16, "alive"),
        ]

        remaining = self.turn_mgr.get_remaining_enemies_for_round()

        self.assertEqual(remaining, ["Goblin A", "Guard Ally"])

    def test_get_remaining_enemies_ignores_current_turn_index(self):
        """Enemy batch list must be invariant to queue pointer."""
        self.turn_mgr.turn_queue = [
            Combatant("Goblin A", CombatantType.ENEMY, 19, 7, 7, 15, "alive"),
            Combatant("Acheron", CombatantType.PC, 16, 21, 21, 16, "alive"),
            Combatant("Guard Ally", CombatantType.NPC, 14, 12, 12, 14, "alive"),
            Combatant("Bandit B", CombatantType.ENEMY, 10, 11, 11, 12, "alive"),
        ]

        expected = ["Goblin A", "Guard Ally", "Bandit B"]

        self.turn_mgr.current_turn_index = 0
        self.assertEqual(self.turn_mgr.get_remaining_enemies_for_round(), expected)

        self.turn_mgr.current_turn_index = 2
        self.assertEqual(self.turn_mgr.get_remaining_enemies_for_round(), expected)

        self.turn_mgr.current_turn_index = 3
        self.assertEqual(self.turn_mgr.get_remaining_enemies_for_round(), expected)

    def test_advance_turn_skips_defeated_and_unconscious_non_pc(self):
        """Turn advancement must skip inactive non-PC actors."""
        self.turn_mgr.current_turn_index = 0
        self.turn_mgr.turn_queue = [
            Combatant("Acheron", CombatantType.PC, 18, 21, 21, 16, "alive"),
            Combatant("Captured Bandit", CombatantType.ENEMY, 15, 1, 11, 12, "defeated"),
            Combatant("Downed Ally", CombatantType.NPC, 13, 0, 12, 14, "unconscious"),
            Combatant("Goblin A", CombatantType.ENEMY, 10, 7, 7, 15, "alive"),
        ]

        next_actor, rolled_over = self.turn_mgr.advance_turn()

        self.assertEqual(next_actor.name, "Goblin A")
        self.assertFalse(rolled_over)


class TestMultiPCCombatManagerFacade(unittest.TestCase):
    """Test MultiPCCombatManager facade and delegation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = MultiPCCombatManager()
        self.sample_party = {
            "partyMembers": ["Acheron", "Merisiel"],
            "active_character": "Acheron"
        }
        self.sample_encounter = {
            "creatures": [
                {"name": "Goblin", "type": "enemy", "armorClass": 15, "hp": 7, "maxHp": 7},
            ]
        }
    
    def test_facade_initialization(self):
        """Test facade creates and links sub-managers."""
        self.assertIsNotNone(self.manager._state)
        self.assertIsNotNone(self.manager._turns)
        self.assertIsInstance(self.manager._state, CombatStateManager)
        self.assertIsInstance(self.manager._turns, TurnQueueManager)
        self.assertIs(self.manager._turns.state_manager, self.manager._state)
    
    def test_delegation_initialize_from_party(self):
        """Test delegation to CombatStateManager."""
        # This should delegate to _state.initialize_from_party
        self.manager.initialize_from_party(self.sample_party)
        
        self.assertIn("Acheron", self.manager._state.pc_states)
        self.assertIn("Merisiel", self.manager._state.pc_states)
    
    def test_delegation_get_available_pcs(self):
        """Test get_available_pcs delegation."""
        self.manager.initialize_from_party(self.sample_party)
        
        available = self.manager.get_available_pcs()
        self.assertEqual(len(available), 2)
    
    def test_delegation_initialize_turn_queue(self):
        """Test initialize_turn_queue delegation."""
        self.manager.initialize_from_party(self.sample_party)
        for pc_name in ["Acheron", "Merisiel"]:
            self.manager._state.pc_states[pc_name].initiative_modifier = 2
            self.manager._state.pc_states[pc_name].current_hp = 20
            self.manager._state.pc_states[pc_name].max_hp = 20
        
        self.manager.initialize_turn_queue(self.sample_encounter)
        
        self.assertEqual(len(self.manager._turns.turn_queue), 3)  # 2 PCs + 1 enemy
    
    def test_delegation_get_current_actor(self):
        """Test get_current_actor delegation."""
        self.manager.initialize_from_party(self.sample_party)
        for pc_name in ["Acheron", "Merisiel"]:
            self.manager._state.pc_states[pc_name].initiative_modifier = 2
            self.manager._state.pc_states[pc_name].current_hp = 20
            self.manager._state.pc_states[pc_name].max_hp = 20
        
        self.manager.initialize_turn_queue(self.sample_encounter)
        
        actor = self.manager.get_current_actor()
        self.assertIsNotNone(actor)
    
    def test_coordination_update_pc_hp(self):
        """Test coordination method: update_pc_hp."""
        self.manager.initialize_from_party(self.sample_party)
        for pc_name in ["Acheron", "Merisiel"]:
            self.manager._state.pc_states[pc_name].initiative_modifier = 2
            self.manager._state.pc_states[pc_name].current_hp = 20
            self.manager._state.pc_states[pc_name].max_hp = 20
        
        # Update HP - updates state manager
        self.manager.update_pc_hp("Acheron", 15)
        
        # Verify state manager is updated
        self.assertEqual(self.manager._state.pc_states["Acheron"].current_hp, 15)
        
        # Note: Turn queue HP sync happens during initialize_turn_queue, not during update_pc_hp
        # Turn queue represents snapshot at combat start; live HP tracked in state manager
    
    def test_coordination_complete_pc_turn(self):
        """Test coordination method: complete_pc_turn."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.current_pc_name = "Acheron"
        
        # Mark Acheron's turn complete - returns False because Merisiel still needs to act
        result = self.manager.complete_pc_turn("Acheron")
        
        self.assertFalse(result)  # Not all PCs have acted yet
        self.assertEqual(self.manager._state.pc_states["Acheron"].status, PCStatus.ACTED)
        
        # Mark Merisiel's turn complete - returns True because all PCs have acted
        self.manager._state.current_pc_name = "Merisiel"
        result = self.manager.complete_pc_turn("Merisiel")
        self.assertTrue(result)  # All PCs have acted now
        self.assertTrue(self.manager._turns.pc_phase_complete)


class TestLLMPromptIntegration(unittest.TestCase):
    """Test LLM prompt generation and formatting."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = MultiPCCombatManager()
        self.sample_party = {
            "partyMembers": ["Acheron", "Merisiel"],
            "active_character": "Acheron"
        }
        self.sample_encounter = {
            "creatures": [
                {"name": "Goblin", "type": "enemy", "armorClass": 15, "hp": 7, "maxHp": 7},
            ]
        }
    
    def test_format_pc_context_for_prompt(self):
        """Test PC-specific context formatting."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.pc_states["Acheron"].current_hp = 15
        self.manager._state.pc_states["Acheron"].max_hp = 20
        
        context = self.manager.format_pc_context_for_prompt("Acheron")
        
        self.assertIn("[Acheron]", context)
        self.assertIn("HP: 15/20", context)
        self.assertIn("Status: ready", context)
    
    def test_format_pc_context_incapacitated(self):
        """Test context formatting for incapacitated PC."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.pc_states["Acheron"].current_hp = 0
        self.manager._state.pc_states["Acheron"].max_hp = 20
        self.manager._state.pc_states["Acheron"].status = PCStatus.INCAPACITATED
        self.manager._state.pc_states["Acheron"].death_save_successes = 1
        self.manager._state.pc_states["Acheron"].death_save_failures = 0
        
        context = self.manager.format_pc_context_for_prompt("Acheron")
        
        self.assertIn("Status: incapacitated", context)
        self.assertIn("Death Saves - Successes: 1/3", context)
        self.assertIn("ACTION REQUIRED", context)
    
    def test_format_party_turn_summary(self):
        """Test party turn status summary."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.current_pc_name = "Acheron"
        self.manager._state.pc_states["Acheron"].current_hp = 15
        self.manager._state.pc_states["Acheron"].max_hp = 20
        self.manager._state.pc_states["Merisiel"].current_hp = 18
        self.manager._state.pc_states["Merisiel"].max_hp = 18
        
        summary = self.manager.format_party_turn_summary()
        
        self.assertIn("PC PARTY TURN STATUS", summary)
        self.assertIn("Acheron", summary)
        self.assertIn("Merisiel", summary)
        self.assertIn("Round 1", summary)
    
    def test_format_multi_pc_head_context(self):
        """Test JSON head context generation."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.pc_states["Acheron"].current_hp = 15
        self.manager._state.pc_states["Acheron"].max_hp = 20
        self.manager._state.pc_states["Merisiel"].current_hp = 18
        self.manager._state.pc_states["Merisiel"].max_hp = 18
        self.manager._state.current_round = 2
        self.manager._state.current_pc_name = "Acheron"
        
        head_context = self.manager.format_multi_pc_head_context()
        
        # Verify it's valid JSON within the context block
        self.assertIn("multi_pc_combat_state", head_context)
        self.assertIn("\"combat_round\": 2", head_context)
        self.assertIn("\"active_pc\": \"Acheron\"", head_context)
        self.assertIn("Acheron", head_context)
        self.assertIn("Merisiel", head_context)
    
    def test_get_required_response_prompt_pc_phase(self):
        """Test required response prompt during PC phase."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.current_pc_name = "Acheron"
        self.manager._turns.pc_phase_complete = False
        
        # Initialize turn queue so get_current_actor works
        for pc_name in ["Acheron", "Merisiel"]:
            self.manager._state.pc_states[pc_name].initiative_modifier = 2
            self.manager._state.pc_states[pc_name].current_hp = 20
            self.manager._state.pc_states[pc_name].max_hp = 20
        
        self.manager.initialize_turn_queue(self.sample_encounter)
        
        prompt = self.manager.get_required_response_prompt()
        
        self.assertIn("PC_PHASE", prompt)
        # Active actor can vary with initiative/phase state; ensure actor slot is present.
        self.assertIn("ACTIVE ACTOR:", prompt)
        self.assertIn("FORBIDDEN ACTORS", prompt)
        self.assertIn("Goblin", prompt)  # Enemies should be forbidden
    
    def test_get_required_response_prompt_enemy_phase(self):
        """Test required response prompt during enemy phase."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.current_pc_name = "Acheron"
        self.manager._turns.pc_phase_complete = True
        
        for pc_name in ["Acheron", "Merisiel"]:
            self.manager._state.pc_states[pc_name].initiative_modifier = 2
            self.manager._state.pc_states[pc_name].current_hp = 20
            self.manager._state.pc_states[pc_name].max_hp = 20
        
        self.manager.initialize_turn_queue(self.sample_encounter)
        
        prompt = self.manager.get_required_response_prompt()
        
        self.assertIn("ENEMY_PHASE", prompt)
        self.assertIn("BATCH RESOLUTION", prompt)
        self.assertIn("Acheron", prompt)  # PCs should be forbidden
        self.assertIn("Merisiel", prompt)
    
    def test_format_initiative_tracker(self):
        """Test initiative tracker formatting."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.current_pc_name = "Acheron"
        
        for pc_name in ["Acheron", "Merisiel"]:
            self.manager._state.pc_states[pc_name].initiative_modifier = 2
            self.manager._state.pc_states[pc_name].current_hp = 20
            self.manager._state.pc_states[pc_name].max_hp = 20
        
        self.manager.initialize_turn_queue(self.sample_encounter)
        
        tracker = self.manager.format_initiative_tracker(self.sample_encounter)

        # Check for key elements in the tracker (actual format uses "--- ROUND INFO ---" and "**Live Initiative Tracker:**")
        self.assertIn("ROUND INFO", tracker)
        self.assertIn("Acheron", tracker)
        self.assertIn("Merisiel", tracker)
        self.assertIn("Goblin", tracker)
        self.assertIn("[>]", tracker)  # Current turn marker
    
    def test_modify_combat_prompt_for_multi_pc(self):
        """Test combat prompt modification."""
        self.manager.initialize_from_party(self.sample_party)
        self.manager._state.current_pc_name = "Acheron"
        self.manager._state.pc_states["Acheron"].current_hp = 15
        self.manager._state.pc_states["Acheron"].max_hp = 20
        
        base_prompt = "++ HOW TO USE THIS SYSTEM ++\nCombat instructions here."
        
        modified = modify_combat_prompt_for_multi_pc(base_prompt, "Acheron", self.manager)
        
        self.assertIn("MULTI-PC COMBAT MODE ACTIVE", modified)
        self.assertIn("[Acheron]", modified)
        self.assertIn("what do you do?", modified)  # Check for the question (actual format has quotes)
        self.assertIn(base_prompt, modified)  # Original should be preserved


class TestContextManagers(unittest.TestCase):
    """Test context managers for testing."""
    
    def setUp(self):
        """Reset global state before each test."""
        reset_combat_state()
    
    def tearDown(self):
        """Clean up after each test."""
        reset_combat_state()
    
    def test_temporary_combat_manager(self):
        """Test temporary_combat_manager context manager."""
        mock_manager = MultiPCCombatManager()
        
        # Initially no manager
        self.assertIsNone(get_combat_manager())
        
        # Use context manager
        with temporary_combat_manager(mock_manager):
            self.assertIs(get_combat_manager(), mock_manager)
        
        # Manager restored to None after context
        self.assertIsNone(get_combat_manager())
    
    def test_temporary_combat_manager_restores_previous(self):
        """Test that context manager restores previous manager."""
        original_manager = MultiPCCombatManager()
        mock_manager = MultiPCCombatManager()
        
        # Set up original
        with temporary_combat_manager(original_manager):
            # Now replace with mock
            with temporary_combat_manager(mock_manager):
                self.assertIs(get_combat_manager(), mock_manager)
            
            # Should be restored to original
            self.assertIs(get_combat_manager(), original_manager)
    
    def test_temporary_combat_callback(self):
        """Test temporary_combat_callback context manager."""
        captured_events = []
        test_callback = lambda event, data: captured_events.append((event, data))
        
        with temporary_combat_callback(test_callback):
            # Access internal callback to verify it's set
            from core.managers.multi_pc_combat import _combat_callback
            self.assertIs(_combat_callback, test_callback)
        
        # Callback restored after context
        from core.managers.multi_pc_combat import _combat_callback
        self.assertIsNone(_combat_callback)
    
    def test_emit_combat_event(self):
        """Test event emission with callback."""
        captured_events = []
        
        def test_callback(event_type, data):
            captured_events.append((event_type, data))
        
        with temporary_combat_callback(test_callback):
            from core.managers.multi_pc_combat import emit_combat_event
            emit_combat_event("test_event", {"key": "value"})
        
        self.assertEqual(len(captured_events), 1)
        self.assertEqual(captured_events[0][0], "test_event")
        self.assertEqual(captured_events[0][1]["key"], "value")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_combat_state()
        self.manager = MultiPCCombatManager()
    
    def tearDown(self):
        """Clean up after each test."""
        reset_combat_state()
    
    def test_empty_party(self):
        """Test handling of empty party."""
        empty_party = {"partyMembers": []}
        
        # Should not crash
        self.manager.initialize_from_party(empty_party)
        self.assertEqual(len(self.manager._state.pc_states), 0)
        
        available = self.manager.get_available_pcs()
        self.assertEqual(len(available), 0)
    
    def test_all_pcs_incapacitated(self):
        """Test edge case: all PCs at 0 HP."""
        party = {"partyMembers": ["Acheron", "Merisiel"]}
        self.manager.initialize_from_party(party)
        
        # Set all to 0 HP
        for pc_name in self.manager._state.pc_states:
            self.manager._state.pc_states[pc_name].current_hp = 0
            self.manager._state.pc_states[pc_name].max_hp = 20
            self.manager._state.pc_states[pc_name].status = PCStatus.INCAPACITATED
        
        # Should still function
        available = self.manager.get_available_pcs()
        self.assertEqual(len(available), 0)  # Incapacitated PCs can't act
        
        incapacitated = self.manager.get_incapacitated_pcs()
        self.assertEqual(len(incapacitated), 2)
    
    def test_encounter_with_no_enemies(self):
        """Test combat with no enemies."""
        party = {"partyMembers": ["Acheron"]}
        encounter = {"creatures": []}
        
        self.manager.initialize_from_party(party)
        self.manager._state.pc_states["Acheron"].initiative_modifier = 2
        self.manager._state.pc_states["Acheron"].current_hp = 20
        self.manager._state.pc_states["Acheron"].max_hp = 20
        
        # Should not crash
        self.manager.initialize_turn_queue(encounter)
        self.assertEqual(len(self.manager._turns.turn_queue), 1)  # Just the PC
    
    def test_invalid_pc_name(self):
        """Test operations with invalid PC names."""
        party = {"partyMembers": ["Acheron"]}
        self.manager.initialize_from_party(party)
        
        # Should handle gracefully
        context = self.manager.format_pc_context_for_prompt("NonExistent")
        self.assertEqual(context, "")
        
        # Should not crash
        self.manager.update_pc_hp("NonExistent", 10)  # Should be a no-op or log warning
    
    def test_get_forbidden_actors_pc_phase(self):
        """Test forbidden actors during PC phase."""
        party = {"partyMembers": ["Acheron"]}
        encounter = {
            "creatures": [
                {"name": "Goblin", "type": "enemy", "armorClass": 15, "hp": 7, "maxHp": 7},
            ]
        }
        
        self.manager.initialize_from_party(party)
        self.manager._state.pc_states["Acheron"].initiative_modifier = 2
        self.manager._state.pc_states["Acheron"].current_hp = 20
        self.manager._state.pc_states["Acheron"].max_hp = 20
        
        self.manager.initialize_turn_queue(encounter)
        self.manager._turns.pc_phase_complete = False
        
        forbidden = self.manager.get_forbidden_actors()
        self.assertIn("Goblin", forbidden)
        self.assertNotIn("Acheron", forbidden)
    
    def test_get_forbidden_actors_enemy_phase(self):
        """Test forbidden actors during enemy phase."""
        party = {"partyMembers": ["Acheron"]}
        encounter = {
            "creatures": [
                {"name": "Goblin", "type": "enemy", "armorClass": 15, "hp": 7, "maxHp": 7},
            ]
        }
        
        self.manager.initialize_from_party(party)
        self.manager._state.pc_states["Acheron"].initiative_modifier = 2
        self.manager._state.pc_states["Acheron"].current_hp = 20
        self.manager._state.pc_states["Acheron"].max_hp = 20
        
        self.manager.initialize_turn_queue(encounter)
        self.manager._turns.pc_phase_complete = True
        
        forbidden = self.manager.get_forbidden_actors()
        self.assertEqual(len(forbidden), 0)  # No restrictions during enemy phase
    
    def test_create_and_end_combat_session(self):
        """Test full combat session lifecycle."""
        party = {"partyMembers": ["Acheron"], "active_character": "Acheron"}
        
        # Initially no manager
        self.assertIsNone(get_combat_manager())
        
        # Create session
        manager = create_combat_manager(party)
        self.assertIsNotNone(manager)
        self.assertIs(get_combat_manager(), manager)
        
        # End session
        end_combat_session()
        self.assertIsNone(get_combat_manager())


class TestIntegrationScenarios(unittest.TestCase):
    """Test realistic integration scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_combat_state()
        self.manager = MultiPCCombatManager()
    
    def tearDown(self):
        """Clean up after each test."""
        reset_combat_state()
    
    def test_full_combat_round(self):
        """Test a complete combat round with multiple PCs."""
        party = {"partyMembers": ["Acheron", "Merisiel"], "active_character": "Acheron"}
        encounter = {
            "creatures": [
                {"name": "Goblin", "type": "enemy", "armorClass": 15, "hp": 7, "maxHp": 7},
            ]
        }
        
        # Initialize
        self.manager.initialize_from_party(party)
        for pc_name in ["Acheron", "Merisiel"]:
            self.manager._state.pc_states[pc_name].initiative_modifier = 2
            self.manager._state.pc_states[pc_name].current_hp = 20
            self.manager._state.pc_states[pc_name].max_hp = 20
        
        self.manager.initialize_turn_queue(encounter)
        
        # Round 1, PC phase
        self.assertEqual(self.manager._state.current_round, 1)
        
        # Acheron's turn
        self.manager._state.current_pc_name = "Acheron"
        self.manager.complete_pc_turn("Acheron")
        self.assertEqual(self.manager._state.pc_states["Acheron"].status, PCStatus.ACTED)
        
        # Merisiel's turn
        self.manager._state.current_pc_name = "Merisiel"
        self.manager.complete_pc_turn("Merisiel")
        self.assertEqual(self.manager._state.pc_states["Merisiel"].status, PCStatus.ACTED)
        
        # All PCs have acted, end PC phase
        self.assertEqual(len(self.manager.get_available_pcs()), 0)
        
        # Enemy phase
        self.manager.force_end_pc_phase()
        self.assertTrue(self.manager._turns.pc_phase_complete)
        
        # New round
        new_round = self.manager.start_new_round()
        self.assertEqual(new_round, 2)
        
        # PCs should be reset to READY
        self.assertEqual(self.manager._state.pc_states["Acheron"].status, PCStatus.READY)
        self.assertEqual(self.manager._state.pc_states["Merisiel"].status, PCStatus.READY)
    
    def test_pc_death_mid_combat(self):
        """Test handling when a PC dies during combat."""
        party = {"partyMembers": ["Acheron", "Merisiel"], "active_character": "Acheron"}
        encounter = {
            "creatures": [
                {"name": "Goblin", "type": "enemy", "armorClass": 15, "hp": 7, "maxHp": 7},
            ]
        }
        
        self.manager.initialize_from_party(party)
        for pc_name in ["Acheron", "Merisiel"]:
            self.manager._state.pc_states[pc_name].initiative_modifier = 2
            self.manager._state.pc_states[pc_name].current_hp = 20
            self.manager._state.pc_states[pc_name].max_hp = 20
        
        self.manager.initialize_turn_queue(encounter)
        
        # Kill Acheron
        self.manager.update_pc_hp("Acheron", 0)
        self.manager._state.pc_states["Acheron"].status = PCStatus.DEAD
        
        # Update turn queue
        for combatant in self.manager._turns.turn_queue:
            if combatant.name == "Acheron":
                combatant.status = "dead"
        
        # Only Merisiel should be available
        available = self.manager.get_available_pcs()
        self.assertEqual(len(available), 1)
        self.assertIn("Merisiel", available)
        
        # Initiative tracker should show dead status
        tracker = self.manager.format_initiative_tracker(encounter)
        self.assertIn("[D]", tracker)


class TestCombatIntegrityValidation(unittest.TestCase):
    """C4 regression tests for enemy-phase PC target integrity."""

    @classmethod
    def setUpClass(cls):
        cls.validate_integrity = staticmethod(cls._import_integrity_validator())

    @staticmethod
    def _import_integrity_validator():
        """Import validate_combatant_integrity with lightweight dependency stubs."""
        openai_mod = types.ModuleType("openai")

        class OpenAI:
            def __init__(self, *args, **kwargs):
                self.chat = types.SimpleNamespace(
                    completions=types.SimpleNamespace(create=lambda *a, **k: None)
                )

        openai_mod.OpenAI = OpenAI
        sys.modules["openai"] = openai_mod

        update_character_info_mod = types.ModuleType("updates.update_character_info")
        update_character_info_mod.update_character_info = lambda *a, **k: None
        update_character_info_mod.normalize_character_name = lambda name: name
        sys.modules["updates.update_character_info"] = update_character_info_mod
        sys.modules["updates.update_encounter"] = types.ModuleType("updates.update_encounter")
        sys.modules["updates.update_party_tracker"] = types.ModuleType("updates.update_party_tracker")

        core_ai_pkg = types.ModuleType("core.ai")
        sys.modules["core.ai"] = core_ai_pkg
        import core
        core.ai = core_ai_pkg

        sys.modules["core.ai.cumulative_summary"] = types.ModuleType("core.ai.cumulative_summary")

        combat_compressor_mod = types.ModuleType("core.ai.combat_compressor")

        class CombatUserMessageCompressor:
            def __init__(self, *args, **kwargs):
                pass

            def process_combat_conversation(self, history):
                return history

        combat_compressor_mod.CombatUserMessageCompressor = CombatUserMessageCompressor
        sys.modules["core.ai.combat_compressor"] = combat_compressor_mod

        inventory_mod = types.ModuleType("core.ai.inventory_context_integration")
        inventory_mod.enhance_player_input_with_inventory = lambda *a, **k: a[0] if a else ""
        sys.modules["core.ai.inventory_context_integration"] = inventory_mod

        if "core.managers.combat_manager" in sys.modules:
            del sys.modules["core.managers.combat_manager"]

        from core.managers.combat_manager import validate_combatant_integrity

        return validate_combatant_integrity

    def test_accepts_non_active_pc_target_from_multi_pc_roster(self):
        """C4.A1/C4.A2: non-active PC target is legal during enemy phase."""
        response = (
            '{"actions":[{"action":"updateCharacterInfo",'
            '"parameters":{"characterName":"Merisiel","changes":"Takes 6 damage."}}]}'
        )
        encounter_data = {
            "creatures": [
                {"name": "Goblin A", "type": "enemy"},
                {"name": "Guard Ally", "type": "npc"},
            ]
        }
        multi_pc_manager = types.SimpleNamespace(pc_states={"Acheron": {}, "Merisiel": {}})

        result = self.validate_integrity(
            response,
            encounter_data,
            multi_pc_manager=multi_pc_manager,
            party_tracker_data={},
        )

        self.assertTrue(result is True)

    def test_rejects_unknown_target_not_in_authoritative_roster(self):
        """C4.A2 guardrail: unknown target remains invalid."""
        response = (
            '{"actions":[{"action":"updateCharacterInfo",'
            '"parameters":{"characterName":"Phantom Knight","changes":"Takes 5 damage."}}]}'
        )
        encounter_data = {
            "creatures": [
                {"name": "Goblin A", "type": "enemy"},
                {"name": "Acheron", "type": "player"},
            ]
        }

        result = self.validate_integrity(response, encounter_data, multi_pc_manager=None, party_tracker_data={})

        self.assertIsInstance(result, str)
        self.assertIn("INTEGRITY ERROR", result)
        self.assertIn("Phantom Knight", result)


def run_tests():
    """Run all tests and return results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCombatStateManager))
    suite.addTests(loader.loadTestsFromTestCase(TestTurnQueueManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiPCCombatManagerFacade))
    suite.addTests(loader.loadTestsFromTestCase(TestLLMPromptIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestContextManagers))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestCombatIntegrityValidation))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("MultiPCCombatManager Test Suite - Phase 3 Refactoring")
    print("=" * 70)
    print()
    
    result = run_tests()
    
    # Summary
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n[PASS] All tests passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Some tests failed!")
        sys.exit(1)
