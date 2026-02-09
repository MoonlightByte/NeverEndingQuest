# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# ============================================================================
# MULTI_PC_COMBAT.PY - Multi-Player Character Combat Manager
# ============================================================================
#
# ARCHITECTURE ROLE: Plugin-style module for multi-PC combat support
#
# This module isolates all multi-PC combat logic to enable easy upstream merging.
# It is activated when MULTIPLAYER_MODE = True in config.py.
#
# KEY RESPONSIBILITIES:
# - Track which PCs have acted in the current combat round
# - Manage PC turn order (player-selected via UI tab clicks)
# - Handle group initiative (PC Party vs Enemies)
# - Prompt incapacitated PCs for death saving throws
# - Coordinate with existing combat system via hooks
# - Manage Turn Queue (Initiative Order)
# - Handle Combat Commands (/att, /dmg) locally
#
# DESIGN PRINCIPLES:
# - Plugin architecture: minimal changes to existing files
# - All multi-PC logic contained in this module
# - Feature flag: MULTIPLAYER_MODE controls activation
# - LLM combat agency: enemies target via LLM decision
# ============================================================================

import random
import json
from typing import Dict, List, Optional, Any, Tuple, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
import os

# Import config to check MULTIPLAYER_MODE
try:
    from config import MULTIPLAYER_MODE
except ImportError:
    MULTIPLAYER_MODE = False

# TABLETOP MODE: Internal imports - fail fast if missing
from utils.encoding_utils import safe_json_load
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, error

# TABLETOP MODE: Debug utilities
# Defer import to method level to handle missing module gracefully during development
_tabletop_debug_available = None

def _get_tabletop_debug():
    """Lazy import of tabletop debug utilities"""
    global _tabletop_debug_available
    if _tabletop_debug_available is None:
        try:
            from utils import tabletop_debug
            _tabletop_debug_available = tabletop_debug
        except ImportError:
            _tabletop_debug_available = None
    return _tabletop_debug_available


class PCStatus(Enum):
    """Status of a PC in combat."""
    READY = "ready"           # Has not acted this round
    ACTED = "acted"           # Has completed their turn this round
    INCAPACITATED = "incapacitated"  # At 0 HP, needs death saves
    DEAD = "dead"             # Failed death saves
    STABLE = "stable"         # Unconscious but stable

class CombatantType(Enum):
    PC = "pc"
    ENEMY = "enemy"
    NPC = "npc"

@dataclass
class Combatant:
    """Generic wrapper for any entity in the turn queue."""
    name: str
    type: CombatantType
    initiative: int
    hp: int
    max_hp: int
    ac: int
    status: str = "alive"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PCCombatState:
    """Tracks a single PC's state during combat."""
    character_name: str
    initiative_modifier: int = 0
    status: PCStatus = PCStatus.READY
    death_save_successes: int = 0
    death_save_failures: int = 0
    current_hp: int = 0
    max_hp: int = 0
    ac: int = 10  # Armor Class for hit/miss determination
    # Metadata for arbitrary upstream data (position, markers, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def reset_for_new_round(self):
        """Reset PC state for a new combat round."""
        if self.status == PCStatus.ACTED:
            self.status = PCStatus.READY
    
    def mark_acted(self):
        """Mark this PC as having acted this round."""
        if self.status == PCStatus.READY:
            self.status = PCStatus.ACTED
    
    def needs_death_save(self) -> bool:
        """Check if PC needs to make a death saving throw."""
        return self.status == PCStatus.INCAPACITATED
    
    def apply_death_save(self, roll: int) -> Tuple[bool, str]:
        """
        Apply a death saving throw result.
        
        Args:
            roll: The d20 roll result (1-20)
            
        Returns:
            Tuple of (combat_continues, result_message)
        """
        if roll == 1:
            # Critical failure - two failures
            self.death_save_failures += 2
            message = f"{self.character_name} rolls a natural 1! Two death save failures!"
        elif roll == 20:
            # Critical success - regain 1 HP
            self.death_save_successes = 0
            self.death_save_failures = 0
            self.current_hp = 1
            self.status = PCStatus.READY
            message = f"{self.character_name} rolls a natural 20! They regain consciousness with 1 HP!"
            return True, message
        elif roll >= 10:
            self.death_save_successes += 1
            message = f"{self.character_name} succeeds on their death save ({self.death_save_successes}/3 successes)."
        else:
            self.death_save_failures += 1
            message = f"{self.character_name} fails their death save ({self.death_save_failures}/3 failures)."
        
        # Check for stabilization or death
        if self.death_save_successes >= 3:
            self.status = PCStatus.STABLE
            message += f" {self.character_name} has stabilized!"
        elif self.death_save_failures >= 3:
            self.status = PCStatus.DEAD
            message += f" {self.character_name} has died!"
            
        return self.status != PCStatus.DEAD, message


@dataclass
class CombatStateManager:
    """
    Manages PC combat states, HP tracking, and combat metadata.
    
    This class handles all state-related operations for multi-PC combat,
    keeping state management separate from turn queue logic.
    """
    
    # PC states indexed by character name
    pc_states: Dict[str, PCCombatState] = field(default_factory=dict)
    
    # Current active PC (selected via UI)
    current_pc_name: Optional[str] = None
    
    # Combat tracking
    current_round: int = 1
    party_initiative: int = 0
    enemy_initiative: int = 0
    party_goes_first: bool = True
    
    # Encounter data reference
    encounter_data: Optional[Dict[str, Any]] = None
    
    # Party size limit
    MAX_PARTY_SIZE: int = 6
    
    def initialize_from_party(self, party_data: Dict[str, Any]) -> None:
        """
        Initialize PC states from party tracker data.
        
        Args:
            party_data: The party_tracker.json data
        """
        self.pc_states.clear()
        
        party_members = party_data.get("partyMembers", [])
        
        # Enforce party size limit
        if len(party_members) > self.MAX_PARTY_SIZE:
            party_members = party_members[:self.MAX_PARTY_SIZE]
        
        for member_name in party_members:
            # TABLETOP MODE: Load character data directly from character JSON file
            # party_tracker.json does not store nested character objects
            # Build path manually to avoid circular dependencies and import issues
            try:
                normalized_name = member_name.lower().replace(' ', '_')
                char_file_path = f"characters/{normalized_name}.json"
                
                # Use safe_json_load if available, otherwise fall back to standard json
                if safe_json_load:
                    char_data = safe_json_load(char_file_path) or {}
                else:
                    # Use standard json module (already imported)
                    with open(char_file_path, 'r', encoding='utf-8') as f:
                        char_data = json.load(f)
                
                if not char_data:
                    debug(f"TABLETOP MODE: Character file not found or empty: {char_file_path}", 
                          category="combat_events")
            except Exception as e:
                debug(f"TABLETOP MODE: Failed to load character {member_name}: {e}", 
                      category="combat_events")
                char_data = {}
            
            # Read HP from character schema (hitPoints is top-level, not nested under hp)
            current_hp = char_data.get("hitPoints", 10)
            max_hp = char_data.get("maxHitPoints", current_hp)
            
            # Determine initial status based on HP
            if current_hp <= 0:
                status = PCStatus.INCAPACITATED
            else:
                status = PCStatus.READY
                
            # Capture any metadata (like position) from char_data
            metadata = char_data.get("metadata", {}) or {}
                
            self.pc_states[member_name] = PCCombatState(
                character_name=member_name,
                initiative_modifier=char_data.get("initiative", 0),
                status=status,
                current_hp=current_hp,
                max_hp=max_hp,
                ac=char_data.get("armorClass", 10),
                metadata=metadata
            )
        
        # Set first PC as current if none selected
        if not self.current_pc_name and self.pc_states:
            self.current_pc_name = list(self.pc_states.keys())[0]
    
    def get_available_pcs(self) -> List[str]:
        """Get list of PCs who can still act this round."""
        return [
            name for name, state in self.pc_states.items()
            if state.status == PCStatus.READY
        ]
    
    def get_incapacitated_pcs(self) -> List[str]:
        """Get list of PCs who need death saves."""
        return [
            name for name, state in self.pc_states.items()
            if state.status == PCStatus.INCAPACITATED
        ]
    
    def get_all_active_pcs(self) -> List[str]:
        """Get all PCs who are still in combat (not dead)."""
        return [
            name for name, state in self.pc_states.items()
            if state.status != PCStatus.DEAD
        ]
    
    def set_current_pc(self, character_name: str) -> bool:
        """
        Set the current active PC (via tab click).
        
        Args:
            character_name: Name of the PC to activate
            
        Returns:
            True if successful, False if PC can't act
        """
        if character_name not in self.pc_states:
            return False
            
        state = self.pc_states[character_name]
        
        # Can select if ready OR incapacitated (for death saves)
        if state.status in (PCStatus.READY, PCStatus.INCAPACITATED):
            self.current_pc_name = character_name
            return True
            
        return False
    
    def update_pc_hp(self, character_name: str, new_hp: int) -> None:
        """
        Update a PC's HP and status.
        
        Args:
            character_name: Name of the PC
            new_hp: New HP value
        """
        if character_name not in self.pc_states:
            return
            
        state = self.pc_states[character_name]
        state.current_hp = new_hp
        
        if new_hp <= 0 and state.status not in (PCStatus.DEAD, PCStatus.STABLE):
            state.status = PCStatus.INCAPACITATED
            state.death_save_successes = 0
            state.death_save_failures = 0
        elif new_hp > 0 and state.status in (PCStatus.INCAPACITATED, PCStatus.STABLE):
            state.status = PCStatus.READY
            state.death_save_successes = 0
            state.death_save_failures = 0


@dataclass
class TurnQueueManager:
    """
    Manages initiative order, turn advancement, and round tracking.
    
    This class handles the turn queue lifecycle independent of PC state management,
    allowing for cleaner separation between state and turn flow.
    """
    
    # Turn Queue Management
    turn_queue: List[Combatant] = field(default_factory=list)
    current_turn_index: int = 0
    
    # Phase tracking
    pc_phase_complete: bool = False
    enemy_phase_complete: bool = False
    
    # Combat flow
    first_round: bool = True
    
    # Reference to state manager for PC lookups
    state_manager: Optional[CombatStateManager] = None
    
    def initialize_turn_queue(self, encounter_data: Dict[str, Any]) -> None:
        """
        Build the turn queue from PC states and encounter data.
        Call this at the start of combat or when initiative changes.
        """
        self.turn_queue.clear()
        
        # Add PCs from state manager
        if self.state_manager:
            for name, state in self.state_manager.pc_states.items():
                # Calculate initiative (d20 + mod)
                init_roll = random.randint(1, 20) + state.initiative_modifier
                self.turn_queue.append(Combatant(
                    name=name,
                    type=CombatantType.PC,
                    initiative=init_roll,
                    hp=state.current_hp,
                    max_hp=state.max_hp,
                    ac=state.ac,  # Use AC from character data
                    status=state.status.value
                ))
        
        # Add enemies and NPCs from encounter
        for creature in encounter_data.get("creatures", []):
            if creature.get("type") == "enemy":
                # TABLETOP MODE: Backfill armorClass from monster template if missing
                ac = creature.get("armorClass")
                if ac is None and ModulePathManager and safe_json_load:
                    monster_type = creature.get("monsterType", "").lower()
                    if monster_type:
                        try:
                            # Get current module from encounter data or party tracker
                            module_name = encounter_data.get("module", "").replace(" ", "_")
                            if not module_name:
                                party_tracker = safe_json_load("party_tracker.json") or {}
                                module_name = party_tracker.get("module", "").replace(" ", "_")
                            
                            path_manager = ModulePathManager(module_name if module_name else None)
                            monster_file = path_manager.get_monster_path(monster_type)
                            
                            if monster_file and os.path.exists(monster_file):
                                monster_data = safe_json_load(monster_file)
                                if monster_data:
                                    ac = monster_data.get("armorClass", 10)
                        except Exception as e:
                            # Log lookup failure for debugging, but continue with default AC
                            creature_name = creature.get("name", "Unknown")
                            debug(f"TABLETOP MODE: Monster AC lookup failed for {creature_name} (type: {monster_type}): {e}",
                                  category="combat_events")
                
                # Default to 10 if still not found
                if ac is None:
                    ac = 10
                
                self.turn_queue.append(Combatant(
                    name=creature.get("name", "Unknown"),
                    type=CombatantType.ENEMY,
                    initiative=creature.get("initiative", random.randint(1, 20)),
                    hp=creature.get("currentHitPoints", 10),
                    max_hp=creature.get("maxHitPoints", 10),
                    ac=ac,
                    status=creature.get("status", "alive")
                ))
            elif creature.get("type") == "npc":
                 self.turn_queue.append(Combatant(
                    name=creature.get("name", "Unknown"),
                    type=CombatantType.NPC,
                     initiative=creature.get("initiative", random.randint(1, 20)),
                    hp=creature.get("currentHitPoints", 10),
                    max_hp=creature.get("maxHitPoints", 10),
                    ac=creature.get("armorClass", 10),
                    status=creature.get("status", "alive")
                ))

        # Sort by Initiative (Descending)
        self.turn_queue.sort(key=lambda x: x.initiative, reverse=True)
        self.current_turn_index = 0
        
        # Update current PC if the first actor is a PC
        current_actor = self.get_current_actor()
        if current_actor and current_actor.type == CombatantType.PC and self.state_manager:
            self.state_manager.set_current_pc(current_actor.name)
    
    def get_current_actor(self) -> Optional[Combatant]:
        """Get the combatant whose turn it is."""
        if not self.turn_queue:
            return None
        return self.turn_queue[self.current_turn_index]
    
    def advance_turn(self) -> Tuple[Combatant, bool]:
        """
        Move to the next turn in the queue.
        Skips dead combatants.

        Returns:
            Tuple of (next_actor, round_rolled_over)
            round_rolled_over is True if the index wrapped past the end of the queue
        """
        start_index = self.current_turn_index
        rolled_over = False

        while True:
            self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_queue)

            # Detect round rollover (index wrapped to start)
            if self.current_turn_index == 0:
                rolled_over = True

            actor = self.turn_queue[self.current_turn_index]

            # Skip dead combatants
            if actor.status.lower() != "dead":
                return actor, rolled_over

            # Infinite loop safety (if everyone is dead)
            if self.current_turn_index == start_index:
                return actor, rolled_over
    
    def find_target(self, partial_name: str, encounter_data: Dict[str, Any]) -> Optional[Combatant]:
        """
        Fuzzy find a target in the encounter.
        Matches partial names (case-insensitive).
        Prioritizes enemies, then living targets.
        """
        partial_name = partial_name.lower().strip()
        candidates = []
        
        # Search in turn queue
        for combatant in self.turn_queue:
            if partial_name in combatant.name.lower():
                candidates.append(combatant)
        
        if not candidates:
            return None
            
        # Prioritize enemies
        enemies = [c for c in candidates if c.type == CombatantType.ENEMY]
        if enemies:
            return enemies[0]
            
        # Then prioritize living targets
        living = [c for c in candidates if c.status.lower() != "dead"]
        if living:
            return living[0]
            
        return candidates[0]
    
    def complete_pc_turn(self, character_name: Optional[str] = None) -> bool:
        """
        Mark a PC's turn as complete.
        
        Args:
            character_name: Name of PC (uses current if None)
            
        Returns:
            True if successful
        """
        if not self.state_manager:
            return False
            
        if character_name is None:
            character_name = self.state_manager.current_pc_name
            
        if not character_name or character_name not in self.state_manager.pc_states:
            return False
            
        state = self.state_manager.pc_states[character_name]
        
        # Only mark if currently ready
        if state.status == PCStatus.READY:
            state.mark_acted()
            return True
            
        return False
    
    def force_end_pc_phase(self) -> None:
        """Force the PC phase to end, even if not all PCs have acted."""
        self.pc_phase_complete = True
        # Mark all remaining ready PCs as acted
        if self.state_manager:
            for name, state in self.state_manager.pc_states.items():
                if state.status == PCStatus.READY:
                    state.mark_acted()
    
    def get_remaining_enemies_for_round(self) -> List[str]:
        """Get list of enemies and allied NPCs who haven't acted this round."""
        remaining = []
        current_idx = self.current_turn_index

        # Look ahead in queue
        for i in range(len(self.turn_queue)):
            idx = (current_idx + i) % len(self.turn_queue)
            combatant = self.turn_queue[idx]

            # Stop when we loop back
            if i > 0 and idx == 0:
                break

            if combatant.type in (CombatantType.ENEMY, CombatantType.NPC) and combatant.status.lower() != "dead":
                remaining.append(combatant.name)

        return remaining


@dataclass 
class MultiPCCombatManager:
    """
    Manages combat state for multiple player characters.
    
    This is the core class for multi-PC combat support. It coordinates between
    CombatStateManager (PC states) and TurnQueueManager (initiative/turns).
    
    ARCHITECTURE: Facade pattern - thin coordinator over focused sub-managers
    """
    
    # Sub-managers (initialized in __post_init__)
    _state: CombatStateManager = field(init=False)
    _turns: TurnQueueManager = field(init=False)
    
    # Narrative Context (stored between commands)
    last_attack_weapon: Optional[str] = None
    last_target: Optional[Combatant] = None
    
    # Combat constants
    DEFAULT_AC: int = 10  # Default Armor Class when not specified
    INITIATIVE_DIE: int = 20  # d20 for initiative rolls
    MAX_PARTY_SIZE: int = 6  # Maximum party size (hard limit)
    
    # UPSTREAM ALIGNMENT: Consolidated character updates (deferred persistence)
    # Tracks pending HP/status changes to be written at combat end
    # Format: {character_name: ["change string 1", "change string 2", ...]}
    pending_character_updates: Dict[str, List[str]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize sub-managers with default state."""
        self._state = CombatStateManager()
        self._turns = TurnQueueManager(state_manager=self._state)
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if multi-PC combat is enabled."""
        return MULTIPLAYER_MODE
    
    # ========================================================================
    # PHASE 1 OPTIMIZATION: Explicit Phase Tracking
    # ========================================================================
    
    @property
    def combat_phase(self) -> str:
        """
        Get the current combat phase as an explicit string.
        
        This provides clear phase indication for LLM prompts to prevent
        confusion about when enemies should act.
        
        Returns:
            "PC_PHASE" - PCs are still taking their turns
            "ENEMY_PHASE" - All PCs have acted, enemies can now resolve
        """
        if self._turns.pc_phase_complete:
            return "ENEMY_PHASE"
        return "PC_PHASE"
    
    @property
    def pc_states(self) -> Dict[str, PCCombatState]:
        """
        Backward compatibility property for accessing PC states.
        
        Returns:
            Dictionary mapping character names to PCCombatState objects
        """
        return self._state.pc_states
    
    @property
    def current_pc_name(self) -> Optional[str]:
        """
        Backward compatibility property for current active PC.
        
        Returns:
            Name of the currently active PC, or None
        """
        return self._state.current_pc_name
    
    @property
    def party_initiative(self) -> int:
        """Backward compatibility property for party initiative."""
        return self._state.party_initiative
    
    @party_initiative.setter
    def party_initiative(self, value: int) -> None:
        """Backward compatibility setter for party initiative."""
        self._state.party_initiative = value
    
    @property
    def enemy_initiative(self) -> int:
        """Backward compatibility property for enemy initiative."""
        return self._state.enemy_initiative
    
    @enemy_initiative.setter
    def enemy_initiative(self, value: int) -> None:
        """Backward compatibility setter for enemy initiative."""
        self._state.enemy_initiative = value
    
    @property
    def party_goes_first(self) -> bool:
        """Backward compatibility property for party initiative order."""
        return self._state.party_goes_first
    
    @party_goes_first.setter
    def party_goes_first(self, value: bool) -> None:
        """Backward compatibility setter for party initiative order."""
        self._state.party_goes_first = value
    
    @property
    def pc_phase_complete(self) -> bool:
        """Backward compatibility property for PC phase completion status."""
        return self._turns.pc_phase_complete
    
    @pc_phase_complete.setter
    def pc_phase_complete(self, value: bool) -> None:
        """Backward compatibility setter for PC phase completion status."""
        self._turns.pc_phase_complete = value
    
    @property
    def current_round(self) -> int:
        """Backward compatibility property for current combat round."""
        return self._state.current_round
    
    @current_round.setter
    def current_round(self, value: int) -> None:
        """Backward compatibility setter for current combat round."""
        self._state.current_round = value
    
    def get_forbidden_actors(self) -> List[str]:
        """
        Get list of combatants that MUST NOT act during the current phase.
        
        During PC_PHASE: Returns all enemies and NPCs (they must wait for /end)
        During ENEMY_PHASE: Returns empty list (enemies are free to act)
        
        This creates a hard block for the LLM to prevent premature enemy narration.
        
        Returns:
            List of combatant names that are forbidden from acting
        """
        if not self._turns.pc_phase_complete:
            # During PC phase, all enemies and NPCs are forbidden
            return [
                c.name for c in self._turns.turn_queue 
                if c.type in (CombatantType.ENEMY, CombatantType.NPC) 
                and c.status != "dead"
            ]
        # During enemy phase, no restrictions
        return []
    
    def get_next_pc_to_act(self) -> Optional[str]:
        """
        Get the name of the next PC who hasn't acted yet.
        
        Used for the "What does [PC_NAME] do?" prompt continuation.
        
        Returns:
            Name of next PC to act, or None if all have acted
        """
        available = self.get_available_pcs()
        if not available:
            return None
        # Return first available PC that isn't the current one
        for pc in available:
            if pc != self._state.current_pc_name:
                return pc
        # If current PC is the only one left, return them
        return available[0] if available else None
    
    def initialize_from_party(self, party_data: Dict[str, Any]) -> None:
        """
        Initialize PC states from party tracker data.
        
        Delegates to CombatStateManager - see CombatStateManager.initialize_from_party() for details.
        
        Args:
            party_data: The party_tracker.json data
        """
        # TABLETOP MODE: Debug party loading
        tt_debug = _get_tabletop_debug()
        if tt_debug:
            party_members = party_data.get("partyMembers", [])
            tt_debug.log_tabletop_event("party_load_start", {
                "member_count": len(party_members),
                "members": party_members
            }, verbose=tt_debug.is_tabletop_verbose())
        
        self._state.initialize_from_party(party_data)
        
        # TABLETOP MODE: Debug party loaded
        if tt_debug:
            tt_debug.log_tabletop_event("party_load_complete", {
                "pc_count": len(self._state.pc_states),
                "loaded_pcs": list(self._state.pc_states.keys())
            }, verbose=tt_debug.is_tabletop_verbose())
            
    def initialize_turn_queue(self, encounter_data: Dict[str, Any]) -> None:
        """
        Build the turn queue from PC states and encounter data.
        Call this at the start of combat or when initiative changes.
        
        Delegates to TurnQueueManager - see TurnQueueManager.initialize_turn_queue() for details.
        """
        # TABLETOP MODE: Debug queue initialization
        tt_debug = _get_tabletop_debug()
        if tt_debug:
            tt_debug.log_tabletop_event("turn_queue_init_start", {
                "encounter_id": encounter_data.get("id", "unknown"),
                "creature_count": len(encounter_data.get("creatures", []))
            }, verbose=tt_debug.is_tabletop_verbose())
        
        self._turns.initialize_turn_queue(encounter_data)
        
        # TABLETOP MODE: Debug queue initialized
        if tt_debug:
            current_actor = self._turns.get_current_actor()
            tt_debug.log_tabletop_event("turn_queue_init_complete", {
                "queue_size": len(self._turns.turn_queue),
                "current_actor": current_actor.name if current_actor else None
            }, verbose=tt_debug.is_tabletop_verbose())

    def get_current_actor(self) -> Optional[Combatant]:
        """Get the combatant whose turn it is.
        
        Delegates to TurnQueueManager - see TurnQueueManager.get_current_actor() for details.
        """
        return self._turns.get_current_actor()

    def advance_turn(self) -> Combatant:
        """
        Move to the next turn in the queue.
        Skips dead combatants. Handles round rollover coordination.

        Delegates to TurnQueueManager.advance_turn() and performs
        cross-manager coordination if the round rolls over.

        Returns:
            The next active Combatant
        """
        # TABLETOP MODE: Debug turn advancement
        tt_debug = _get_tabletop_debug()
        old_actor = self.get_current_actor()
        old_name = old_actor.name if old_actor else None

        result, rolled_over = self._turns.advance_turn()

        # Coordination: handle round rollover
        if rolled_over:
            self._state.current_round += 1
            for state in self._state.pc_states.values():
                state.reset_for_new_round()
            self._turns.pc_phase_complete = False
            self._turns.enemy_phase_complete = False

        # Coordination: update active PC if next actor is a PC
        if result.type == CombatantType.PC:
            self._state.set_current_pc(result.name)

        # TABLETOP MODE: Debug turn advanced
        if tt_debug:
            new_name = result.name if result else None

            if old_name != new_name:
                tt_debug.log_tabletop_event("turn_advanced", {
                    "from_actor": old_name,
                    "to_actor": new_name,
                    "round": self._state.current_round,
                    "queue_index": self._turns.current_turn_index,
                    "round_rolled_over": rolled_over
                }, verbose=tt_debug.is_tabletop_verbose())

                if result and result.type == CombatantType.PC and new_name:
                    tt_debug.log_state_transition(new_name, "waiting", "acting", reason="turn_advanced")

        return result

    def find_target(self, partial_name: str, encounter_data: Dict[str, Any]) -> Optional[Combatant]:
        """
        Fuzzy find a target in the encounter.
        Matches partial names (case-insensitive).
        Prioritizes enemies, then living targets.
        
        Delegates to TurnQueueManager - see TurnQueueManager.find_target() for details.
        """
        return self._turns.find_target(partial_name, encounter_data)

    def handle_combat_command(self, cmd: str, encounter_data: Dict[str, Any], actor_name: str = "Player") -> Tuple[Optional[str], Optional[str]]:
        """
        Process a local combat command.
        
        Args:
            cmd: The user input string (e.g., "/att goblin 18")
            encounter_data: Current encounter state
            actor_name: Name of the character performing the action
            
        Returns:
            Tuple(UserFeedback, SystemLogInjection)
            - UserFeedback: String to show user immediately (or None)
            - SystemLogInjection: String to inject into LLM history (or None)
        """
        # TABLETOP MODE: Debug entry
        tt_debug = _get_tabletop_debug()
        if tt_debug:
            tt_debug.log_tabletop_event("combat_command_entry", {
                "cmd": cmd[:50] if len(cmd) > 50 else cmd,
                "actor": actor_name,
                "encounter_id": encounter_data.get("id", "unknown")
            }, verbose=tt_debug.is_tabletop_verbose())
        
        parts = cmd.strip().split()
        if not parts:
            return None, None
            
        command = parts[0].lower()
        args = parts[1:]
        
        if command == "/att":
            # Syntax: /att [target] [roll] [optional: weapon]
            if len(args) < 2:
                return "Dungeon Master: [SYSTEM] Usage: /att [target] [roll] [weapon]", None
            
            # Check if optional weapon argument is present (last argument if not a number)
            # Standard args: target... roll
            # Enhanced args: target... roll weapon...
            
            # Find the roll (first number from the right)
            roll_index = -1
            roll = None
            weapon_parts = []
            
            # Iterate backwards to find the roll
            for i in range(len(args) - 1, -1, -1):
                try:
                    roll = int(args[i])
                    roll_index = i
                    break
                except ValueError:
                    weapon_parts.insert(0, args[i])
            
            if roll is None:
                return "Dungeon Master: [SYSTEM] Invalid roll. Usage: /att [target] [roll] [weapon]", None
            
            # Target is everything before the roll
            target_name = " ".join(args[:roll_index])
            
            # Weapon is everything after the roll (already collected in weapon_parts)
            weapon_name = " ".join(weapon_parts) if weapon_parts else None
            
            # Store weapon for context carry-over
            if weapon_name:
                self.last_attack_weapon = weapon_name
            else:
                self.last_attack_weapon = None
                
            target = self.find_target(target_name, encounter_data)
            if not target:
                return f"Dungeon Master: [SYSTEM] Target '{target_name}' not found.", None
            
            # Store as last target for /dmg command
            self.last_target = target
                
            # Check Hit (AC)
            # Use AC from target in queue, or fallback to encounter data if missing
            ac = target.ac
            if ac is None or ac == 0:
                 # Try to find in encounter data
                 for c in encounter_data.get("creatures", []):
                      if c.get("name") == target.name:
                          ac = c.get("armorClass", MultiPCCombatManager.DEFAULT_AC)
                          break
            
            if roll >= ac:
                # TABLETOP MODE: Debug hit
                if tt_debug:
                    tt_debug.log_tabletop_event("combat_command_hit", {
                        "target": target.name,
                        "roll": roll,
                        "ac": ac,
                        "result": "waiting_for_damage"
                    }, verbose=tt_debug.is_tabletop_verbose())
                
                # TABLETOP MODE: Add prefill marker so UI auto-populates /dmg command
                return f"[skipTTS][prefill:/dmg ] Dungeon Master: Hit! (Rolled {roll} vs AC {ac}). Roll damage.", None
            else:
                # Miss logic - pass to LLM for narration
                weapon_context = f" with {weapon_name}" if weapon_name else ""
                log_msg = f"[System: {actor_name} attacked {target.name}{weapon_context} with roll {roll} vs AC {ac} and MISSED.]"
                
                # TABLETOP MODE: Debug miss
                if tt_debug:
                    tt_debug.log_tabletop_event("combat_command_miss", {
                        "target": target.name,
                        "roll": roll,
                        "ac": ac,
                        "has_feedback": True,
                        "has_log_msg": True,
                        "result": "continue_to_llm"
                    }, verbose=tt_debug.is_tabletop_verbose())
                
                return f"[skipTTS] Dungeon Master: Miss. (Rolled {roll} vs AC {ac}).\nProcessing outcome...", log_msg
                
        elif command == "/dmg":
            # Syntax: /dmg [amount] [flavor text...]
            if len(args) < 1:
                return "[skipTTS] Dungeon Master: [SYSTEM] Usage: /dmg [amount] [optional flavor]", None
                
            try:
                amount = int(args[0])
            except ValueError:
                return "[skipTTS] Dungeon Master: [SYSTEM] Invalid amount. Usage: /dmg [amount] [flavor]", None
            
            # Determine flavor text
            if len(args) > 1:
                # User provided explicit flavor
                flavor_text = " ".join(args[1:])
            elif self.last_attack_weapon:
                # Fallback to context carry-over
                flavor_text = f"{self.last_attack_weapon} damage"
            else:
                # Generic fallback
                flavor_text = "damage"
            
            target = getattr(self, 'last_target', None)
            
            if not target:
                return "[skipTTS] Dungeon Master: [SYSTEM] No target selected. Use /att first or specify target.", None
            
            # Apply Damage
            previous_hp = target.hp
            target.hp -= amount
            status_update = ""
            status_text = ""
            if target.hp <= 0:
                target.status = "dead" # or defeated/unconscious
                target.hp = 0
                status_update = " [Target Defeated]"
                status_text = "defeated"
            elif target.hp < target.max_hp / 2:
                status_update = " [Bloodied]"
                status_text = "bloodied"
            
            # UPSTREAM ALIGNMENT: Queue character update for deferred persistence
            if target.type == CombatantType.PC:
                damage_taken = previous_hp - target.hp
                change_desc = f"took {damage_taken} damage from {actor_name}"
                if status_text:
                    change_desc += f", now {status_text}"
                change_desc += f" (HP: {target.hp}/{target.max_hp})"
                self._queue_character_update(target.name, change_desc)
            
            # Sync enemy HP changes back to encounter_data for persistence
            # TABLETOP MODE: This ensures encounter file has updated HP when saved
            if target.type == CombatantType.ENEMY:
                for creature in encounter_data.get("creatures", []):
                    if creature.get("name") == target.name:
                        creature["currentHitPoints"] = target.hp
                        if target.status == "dead":
                            creature["status"] = "dead"
                        break
            
            log_msg = f"[System: {actor_name} dealt {amount} damage ({flavor_text}) to {target.name}. HP: {target.hp}/{target.max_hp}.{status_update}]"
            
            return f"[skipTTS] Dungeon Master: Damage applied ({amount}). Target HP: {target.hp}/{target.max_hp}{status_update}.\nProcessing outcome...", log_msg
            
        return None, None


    
    def roll_group_initiative(self) -> Tuple[int, int, bool]:
        """
        Roll group initiative for PC party vs enemies.
        
        Returns:
            Tuple of (party_roll, enemy_roll, party_goes_first)
        """
        # Roll d20 for each side
        party_roll = random.randint(1, self.INITIATIVE_DIE)
        enemy_roll = random.randint(1, self.INITIATIVE_DIE)
        
        # Add highest PC initiative modifier to party roll
        max_pc_mod = max(
            (pc.initiative_modifier for pc in self._state.pc_states.values()),
            default=0
        )
        self._state.party_initiative = party_roll + max_pc_mod
        self._state.enemy_initiative = enemy_roll
        
        # Determine who goes first (party wins ties)
        self._state.party_goes_first = self._state.party_initiative >= self._state.enemy_initiative
        
        return party_roll, enemy_roll, self._state.party_goes_first
    
    def get_available_pcs(self) -> List[str]:
        """Get list of PCs who can still act this round.
        
        Delegates to CombatStateManager - see CombatStateManager.get_available_pcs() for details.
        """
        return self._state.get_available_pcs()
    
    def get_incapacitated_pcs(self) -> List[str]:
        """Get list of PCs who need death saves.
        
        Delegates to CombatStateManager.get_incapacitated_pcs().
        """
        return self._state.get_incapacitated_pcs()
    
    def get_all_active_pcs(self) -> List[str]:
        """Get all PCs who are still in combat (not dead).
        
        Delegates to CombatStateManager.get_all_active_pcs().
        """
        return self._state.get_all_active_pcs()
    
    def set_current_pc(self, character_name: str) -> bool:
        """
        Set the current active PC (via tab click).
        
        Args:
            character_name: Name of the PC to activate
            
        Returns:
            True if successful, False if PC can't act
            
        Delegates to CombatStateManager.set_current_pc().
        """
        return self._state.set_current_pc(character_name)
    
    def complete_pc_turn(self, character_name: Optional[str] = None) -> bool:
        """
        Mark a PC's turn as complete and check if PC phase is done.
        
        Args:
            character_name: PC who completed turn (uses current if None)
            
        Returns:
            True if all PCs have acted (PC phase complete)
        """
        name = character_name or self._state.current_pc_name
        
        # Delegate marking to TurnQueueManager (includes READY guard)
        marked = self._turns.complete_pc_turn(name)
        
        if not marked:
            # PC wasn't ready or doesn't exist — still check phase status
            # (another path may have already marked them)
            pass
        
        # Coordination: check if all PCs have acted
        available = self.get_available_pcs()
        incapacitated = self.get_incapacitated_pcs()
        self._turns.pc_phase_complete = len(available) == 0 and len(incapacitated) == 0
        
        return self._turns.pc_phase_complete
    
    def force_end_pc_phase(self) -> None:
        """
        Forcefully mark all PCs as having acted this round.
        Used when the DM manually triggers the enemy phase via /end.
        This ensures the prompt context reflects that the PC phase is over.
        
        Delegates to TurnQueueManager.force_end_pc_phase().
        """
        self._turns.force_end_pc_phase()

    def get_remaining_enemies_for_round(self) -> List[str]:
        """
        Get a list of enemies/NPCs that should act in the enemy phase.
        Uses pc_phase_complete state + initiative order (Option B approach).
        
        DETERMINISM RULE: This function MUST ignore current_turn_index.
        It returns ALL living non-PCs. The LLM then processes them in initiative order.
        
        Delegates to TurnQueueManager - see TurnQueueManager.get_remaining_enemies_for_round() for details.
        
        Returns:
            List of combatant names (Enemies and NPCs) in initiative order
        """
        return self._turns.get_remaining_enemies_for_round()

    def start_new_round(self) -> int:
        """
        Start a new combat round.
        
        Returns:
            The new round number
        """
        self._state.current_round += 1
        self._turns.pc_phase_complete = False
        self._turns.enemy_phase_complete = False
        
        # Reset Turn Queue Pointer to the top of initiative
        self._turns.current_turn_index = 0
        
        # Update active PC if the new first actor is a PC
        current_actor = self.get_current_actor()
        if current_actor and current_actor.type == CombatantType.PC:
            self.set_current_pc(current_actor.name)
        
        # Reset all PC states for new round
        for state in self._state.pc_states.values():
            state.reset_for_new_round()
            
        return self._state.current_round
    
    def sync_round_from_encounter(self, encounter_data: Dict[str, Any]) -> bool:
        """
        Sync manager round state from persisted encounter file.
        
        Called on combat start/resume to ensure the manager's current_round
        matches the encounter file's combat_round. The encounter file is the
        single source of truth for persisted round state.
        
        Args:
            encounter_data: The encounter JSON data
            
        Returns:
            True if round was synced (values differed), False if already in sync
        """
        encounter_round = encounter_data.get('combat_round', encounter_data.get('current_round', 1))
        if encounter_round > 0 and encounter_round != self._state.current_round:
            self._state.current_round = encounter_round
            return True
        return False
    
    def update_pc_hp(self, character_name: str, new_hp: int) -> None:
        """
        Update a PC's HP and status.
        
        Delegates HP/status update to CombatStateManager.update_pc_hp().
        
        Note: Turn queue Combatant objects have their own hp field set at
        initialization. If turn queue HP sync becomes needed, add it here
        as coordination logic after the delegation call.
        
        Args:
            character_name: Name of the PC
            new_hp: New HP value
        """
        self._state.update_pc_hp(character_name, new_hp)
    
    def _queue_character_update(self, character_name: str, change_description: str) -> None:
        """
        Queue a character update for deferred persistence.
        
        UPSTREAM ALIGNMENT: Implements consolidated update pattern matching
        combat_manager.py. Changes are batched and applied at combat end.
        
        Args:
            character_name: Name of the character
            change_description: Description of the change (e.g., "took 15 damage")
        """
        if character_name not in self.pending_character_updates:
            self.pending_character_updates[character_name] = []
        self.pending_character_updates[character_name].append(change_description)
    
    def persist_combat_changes(self) -> Dict[str, bool]:
        """
        Persist all queued combat changes to character files.
        
        UPSTREAM ALIGNMENT: Implements deferred persistence pattern matching
        combat_manager.py behavior. Called when combat ends to save all HP
        and status changes accumulated during combat.
        
        Returns:
            Dictionary mapping character names to success status
        """
        results = {}
        
        if not self.pending_character_updates:
            # No pending updates - still save current HP state
            for pc_name, pc_state in self._state.pc_states.items():
                try:
                    # Import here to avoid circular dependencies
                    from updates.update_character_info import update_character_info
                    
                    change_str = f"HP updated to {pc_state.current_hp} after combat"
                    if pc_state.status == PCStatus.DEAD:
                        change_str += ", status: dead"
                    elif pc_state.status == PCStatus.INCAPACITATED:
                        change_str += ", status: unconscious"
                    elif pc_state.status == PCStatus.STABLE:
                        change_str += ", status: stable"
                    
                    success = update_character_info(pc_name, change_str)
                    results[pc_name] = success
                except Exception as e:
                    error(f"Failed to persist combat changes for {pc_name}: {e}", category="combat_persistence")
                    results[pc_name] = False
            return results
        
        # Process consolidated updates
        for character_name, changes_list in self.pending_character_updates.items():
            try:
                # Import here to avoid circular dependencies
                from updates.update_character_info import update_character_info
                
                # Build consolidated change string (upstream pattern)
                final_change_string = "Combat results: " + "; ".join(changes_list) + "."
                
                success = update_character_info(character_name, final_change_string)
                results[character_name] = success
                
                if success:
                    info(f"Saved combat changes for {character_name}", category="combat_persistence")
                else:
                    error(f"Failed to save changes for {character_name}", category="combat_persistence")
                    
            except Exception as e:
                error(f"Exception persisting combat changes for {character_name}: {e}", exception=e, category="combat_persistence")
                results[character_name] = False
        
        # Clear pending updates after processing
        self.pending_character_updates.clear()
        
        return results
    
    def get_combat_state_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current combat state for the UI.
        
        Returns:
            Dictionary with combat state info
        """
        return {
            "current_round": self._state.current_round,
            "party_initiative": self._state.party_initiative,
            "enemy_initiative": self._state.enemy_initiative,
            "party_goes_first": self._state.party_goes_first,
            "current_pc": self._state.current_pc_name,
            "pc_phase_complete": self._turns.pc_phase_complete,
            "enemy_phase_complete": self._turns.enemy_phase_complete,
            "pcs": {
                name: {
                    "status": state.status.value,
                    "hp": state.current_hp,
                    "max_hp": state.max_hp,
                    "death_saves": {
                        "successes": state.death_save_successes,
                        "failures": state.death_save_failures
                    },
                    "metadata": state.metadata
                }
                for name, state in self._state.pc_states.items()
            },
            "available_pcs": self.get_available_pcs(),
            "incapacitated_pcs": self.get_incapacitated_pcs()
        }
    
    def format_pc_context_for_prompt(self, pc_name: str) -> str:
        """
        Format PC-specific context for combat prompt.
        
        Args:
            pc_name: Name of the PC
            
        Returns:
            Formatted context string for prompt insertion
        """
        if pc_name not in self._state.pc_states:
            return ""
            
        state = self._state.pc_states[pc_name]
        
        lines = [
            f"!!! CRITICAL OVERRIDE: THE CURRENT ACTIVE PLAYER CHARACTER IS: [{pc_name}] !!!",
            f"IGNORE all other turn indicators. Only [{pc_name}] can act now.",
            f"HP: {state.current_hp}/{state.max_hp}",
            f"Status: {state.status.value}",
        ]
        
        if state.status == PCStatus.INCAPACITATED:
            lines.append(f"Death Saves - Successes: {state.death_save_successes}/3, Failures: {state.death_save_failures}/3")
            lines.append("ACTION REQUIRED: This PC must make a death saving throw!")
            
        return "\n".join(lines)
    
    def format_party_turn_summary(self) -> str:
        """
        Format summary of which PCs have/haven't acted.
        
        Returns:
            Formatted summary string
        """
        lines = [f"=== PC PARTY TURN STATUS (Round {self._state.current_round}) ==="]
        
        for name, state in self._state.pc_states.items():
            marker = "[>]" if name == self._state.current_pc_name else "   "
            status_icon = {
                PCStatus.READY: "[WAIT] Ready",
                PCStatus.ACTED: "[DONE] Acted",
                PCStatus.INCAPACITATED: "[DOWN] Down",
                PCStatus.DEAD: "[DEAD] Dead",
                PCStatus.STABLE: "[STBL] Stable"
            }.get(state.status, "?")
            
            lines.append(f"{marker} {name}: {status_icon} (HP: {state.current_hp}/{state.max_hp})")
            
        available = self.get_available_pcs()
        if available:
            lines.append(f"\nPCs who can still act: {', '.join(available)}")
        else:
            lines.append("\nAll PCs have acted this round.")
            
        return "\n".join(lines)

    def format_multi_pc_head_context(self) -> str:
        """
        Generate a structured JSON context block for the prompt "Head".
        This contains authoritative state for ALL PCs in the combat.
        
        Returns:
            Formatted JSON string for system prompt injection
        """
        context = {
            "type": "multi_pc_combat_state",
            "combat_round": self._state.current_round,
            "active_pc": self._state.current_pc_name,
            "party_initiative": self._state.party_initiative,
            "enemy_initiative": self._state.enemy_initiative,
            "party_goes_first": self._state.party_goes_first,
            "pc_phase_complete": self._turns.pc_phase_complete,
            "player_characters": []
        }
        
        for name, state in self._state.pc_states.items():
            pc_data = {
                "name": name,
                "hp": f"{state.current_hp}/{state.max_hp}",
                "status": state.status.value,
                "metadata": state.metadata
            }
            
            # Include death save info if relevant
            if state.status == PCStatus.INCAPACITATED:
                pc_data["death_saves"] = {
                    "successes": state.death_save_successes,
                    "failures": state.death_save_failures
                }
                
            context["player_characters"].append(pc_data)
            
        return f"=== AUTHORITATIVE MULTI-PC STATE (JSON) ===\n{json.dumps(context, indent=2)}\n"

    def get_required_response_prompt(self) -> str:
        """
        Generate the appropriate 'REQUIRED RESPONSE' system instruction for the AI.
        
        PHASE 1 OPTIMIZATION: Enhanced with explicit phase indicator and forbidden actors.
        
        This logic enforces:
        1. STRICT TURN ISOLATION during PC_PHASE (no enemy narration allowed).
        2. BATCH RESOLUTION during ENEMY_PHASE (after /end command).
        
        Returns:
            The instruction string to inject into the user prompt.
        """
        # Get forbidden actors for PC phase enforcement
        forbidden = self.get_forbidden_actors()
        forbidden_str = ", ".join(forbidden) if forbidden else "None"
        
        # ====================================================================
        # ENEMY_PHASE: BATCH MODE (after /end command)
        # ====================================================================
        if self._turns.pc_phase_complete:
            pending = self.get_remaining_enemies_for_round()
            actors_str = ", ".join(pending) if pending else "remaining enemies"
            
            # Explicitly identify Player Characters to forbid them from acting
            pc_names = list(self._state.pc_states.keys())
            pc_forbidden_str = ", ".join(pc_names) if pc_names else "None"
            
            return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CURRENT PHASE: ENEMY_PHASE  │  PC PHASE COMPLETE: TRUE                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MODE: ENEMY & NPC BATCH RESOLUTION                                          ║
║  RESOLVE IN ORDER: {actors_str[:60]}
╠══════════════════════════════════════════════════════════════════════════════╣
║  [BLOCKED] FORBIDDEN ACTORS (DO NOT NARRATE):                                ║
║  {pc_forbidden_str[:70]:<70} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  REQUIRED RESPONSE:                                                          ║
║  1. Resolve turns for ALL listed ENEMIES and NPC ALLIES in order.            ║
║  2. STRICT: Only narrate for DM-controlled entities (Enemies/NPC Allies).    ║
║  3. NEVER narrate actions for Forbidden Player Characters listed above.       ║
║  4. STOP immediately after the last enemy/NPC ally acts.                     ║
║  5. Announce round completion and ask for PC actions.                        ║
║  6. Return structured JSON with plan, narration, combat_round, actions.      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

        # PC_PHASE: STRICT TURN ISOLATION MODE
        current_actor = self.get_current_actor()
        actor_name = current_actor.name if current_actor else "Current Actor"
        
        # Count remaining PCs
        available_pcs = self.get_available_pcs()
        pcs_remaining = len(available_pcs)
        
        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CURRENT PHASE: PC_PHASE  │  ACTIVE ACTOR: {actor_name:<30} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  PCs REMAINING THIS ROUND: {pcs_remaining}                                              ║
║  AWAITING /end COMMAND: YES (enemies cannot act yet)                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  [BLOCKED] FORBIDDEN ACTORS (DO NOT NARRATE):                                ║
║  {forbidden_str[:70]:<70} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  REQUIRED RESPONSE:                                                          ║
║  1. Narrate ONLY the result of {actor_name}'s declared action.               ║
║  2. FLAVOR TEXT: Treat shouts/battle cries as roleplay from {actor_name}.    ║
║  3. STOP IMMEDIATELY after this single resolution.                           ║
║  4. DO NOT narrate actions for other PCs. Await /end for enemy phase.        ║
║  5. DO NOT name or prompt the next PC. The facilitator controls turn order.  ║
║  6. Return structured JSON with plan, narration, combat_round, actions.      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  [WARNING] VIOLATION = CRITICAL FAILURE: Narrating for forbidden actors will ║
║      cause combat desync. Only [{actor_name}] has authority to act now.
╚══════════════════════════════════════════════════════════════════════════════╝
"""

    def _get_combatant_marker(self, combatant: Combatant) -> Tuple[str, str]:
        """
        Determine state marker and status for a combatant in initiative tracker.
        
        Args:
            combatant: The combatant to get marker for
            
        Returns:
            Tuple of (marker, state_description)
        """
        status = combatant.status.lower()
        name = combatant.name
        
        if status == "dead":
            return "[D]", "Dead"
        
        if combatant.type == CombatantType.PC:
            pc_state = self._state.pc_states.get(name)
            if pc_state:
                if pc_state.status == PCStatus.ACTED:
                    return "[X]", "Acted"
                elif name == self._state.current_pc_name:
                    return "[>]", "CURRENT TURN"
            return "[ ]", "Waiting"
        
        # NPCs/Enemies default to Waiting
        return "[ ]", "Waiting"
    
    def _build_initiative_lines(self, sorted_queue: List[Combatant]) -> Tuple[List[str], List[str]]:
        """
        Build initiative and tracker lines from sorted queue.
        
        Args:
            sorted_queue: List of combatants sorted by initiative
            
        Returns:
            Tuple of (initiative_lines, tracker_lines)
        """
        initiative_lines = []
        tracker_lines = []
        
        for combatant in sorted_queue:
            name = combatant.name
            init = combatant.initiative
            status = combatant.status.lower()
            marker, state = self._get_combatant_marker(combatant)
            
            initiative_lines.append(f"- {name} ({init}) - {status}")
            tracker_lines.append(f"- {marker} {name} ({init}) - {state}")
        
        return initiative_lines, tracker_lines
    
    def _determine_instruction_block(self, sorted_queue: List[Combatant]) -> Tuple[str, List[str]]:
        """
        Determine instruction block and turn window based on combat phase.
        
        Args:
            sorted_queue: List of combatants sorted by initiative
            
        Returns:
            Tuple of (instruction_block, turn_window)
        """
        current_round = self._state.current_round
        
        if self._turns.pc_phase_complete:
            # ENEMY_PHASE
            pending_enemies = self.get_remaining_enemies_for_round()
            if pending_enemies:
                enemy_list = "\n".join([f"- {name}" for name in pending_enemies])
                instruction = f""">>> PROCESS TO END ROUND:
{enemy_list}
>>> THEN: End Round {current_round}, Start Round {current_round + 1}"""
                return instruction, pending_enemies
            else:
                instruction = ">>> ROUND COMPLETE\nAll creatures have acted. Increment combat_round."
                return instruction, []
        
        # PC_PHASE
        active_pc = self._state.current_pc_name
        active_pc_index = -1
        
        for i, combatant in enumerate(sorted_queue):
            if combatant.name == active_pc:
                active_pc_index = i
                break
        
        if active_pc_index < 0:
            return f">>> CURRENT: {active_pc} - PLAYER TURN (await input)", [active_pc]
        
        # Find NPCs acting before active PC
        npcs_before = [
            combatant.name for i, combatant in enumerate(sorted_queue[:active_pc_index])
            if combatant.type in (CombatantType.ENEMY, CombatantType.NPC)
        ]
        
        if npcs_before:
            npc_list = "\n".join([f"- {name}" for name in npcs_before])
            instruction = f""">>> PROCESS ALL OF THESE IN ONE RESPONSE (Initiative Order):
{npc_list}
>>> THEN STOP AT: {active_pc} (Player)"""
            return instruction, npcs_before + [active_pc]
        else:
            active_init = sorted_queue[active_pc_index].initiative
            instruction = f">>> CURRENT: {active_pc} ({active_init}) - PLAYER TURN (await input)"
            return instruction, [active_pc]
    
    def format_initiative_tracker(self, encounter_data: Dict[str, Any]) -> str:
        """
        Generate Live Initiative Tracker markdown matching AI tracker format.
        This replaces the AI initiative tracker in multi-PC mode for deterministic,
        accurate tracking that correctly handles all PCs.
        
        Args:
            encounter_data: The encounter data with creatures list
            
        Returns:
            Formatted initiative tracker string matching AI tracker output format
        """
        current_round = self._state.current_round
        
        # Sort turn queue by initiative (highest first)
        sorted_queue = sorted(self._turns.turn_queue, key=lambda x: x.initiative, reverse=True)
        
        # Build initiative lines
        initiative_lines, tracker_lines = self._build_initiative_lines(sorted_queue)
        
        # Determine instructions
        instruction_block, turn_window = self._determine_instruction_block(sorted_queue)
        
        # Build tracker output
        tracker_output = f"""--- ROUND INFO ---
combat_round: {current_round}
player_name: {self._state.current_pc_name}
initiative_order:
{chr(10).join(initiative_lines)}

--- LIVE TRACKER ---
**Live Initiative Tracker:**
{chr(10).join(tracker_lines)}

{instruction_block}

```json
{{
  "combat_round": {current_round},
  "player_name": "{self._state.current_pc_name}",
  "turn_window": {json.dumps(turn_window)},
  "pc_phase_complete": {str(self._turns.pc_phase_complete).lower()}
}}
```"""
        
        return tracker_output


# Global instance for combat session
_active_combat_manager: Optional[MultiPCCombatManager] = None
_combat_callback: Optional[Any] = None  # Callback for combat events (e.g., to web UI)


@contextmanager
def temporary_combat_manager(manager: MultiPCCombatManager) -> Generator[MultiPCCombatManager, None, None]:
    """
    Temporarily replace global combat manager for testing.

    Usage:
        with temporary_combat_manager(mock_manager):
            # All code here sees mock_manager as the active combat manager
            result = get_combat_manager()
            assert result == mock_manager
        # Original manager restored automatically
    """
    global _active_combat_manager
    previous = _active_combat_manager
    _active_combat_manager = manager
    try:
        yield manager
    finally:
        _active_combat_manager = previous


@contextmanager
def temporary_combat_callback(callback: Any) -> Generator[Any, None, None]:
    """
    Temporarily replace global callback for testing.

    Usage:
        captured_events = []
        with temporary_combat_callback(lambda event, data: captured_events.append((event, data))):
            emit_combat_event("test_event", {"data": "value"})
            assert len(captured_events) == 1
    """
    global _combat_callback
    previous = _combat_callback
    _combat_callback = callback
    try:
        yield callback
    finally:
        _combat_callback = previous


def reset_combat_state() -> None:
    """
    Reset global combat state - USE ONLY IN TESTS.
    Clears both active manager and callback.
    """
    global _active_combat_manager, _combat_callback
    _active_combat_manager = None
    _combat_callback = None
    info("Combat state reset", category="combat_lifecycle")


def set_combat_callback(callback: Any) -> None:
    """
    Set the callback function for combat events.
    
    Args:
        callback: Function to call with event data
    """
    global _combat_callback
    _combat_callback = callback


def emit_combat_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    Emit a combat event to the callback.
    
    Args:
        event_type: Type of event (e.g., 'multi_pc_combat_started')
        data: Event payload
    """
    global _combat_callback
    if _combat_callback:
        try:
            _combat_callback(event_type, data)
        except Exception as e:
            error(f"Error in combat callback: {e}", exception=e, category="combat_events")


def get_combat_manager() -> Optional[MultiPCCombatManager]:
    """Get the active combat manager instance."""
    global _active_combat_manager
    return _active_combat_manager


def create_combat_manager(party_data: Dict[str, Any]) -> MultiPCCombatManager:
    """
    Create a new combat manager for a combat session.
    
    Args:
        party_data: Party tracker data
        
    Returns:
        New MultiPCCombatManager instance
    """
    global _active_combat_manager
    
    manager = MultiPCCombatManager()
    manager.initialize_from_party(party_data)
    _active_combat_manager = manager
    
    # Emit start event
    emit_combat_event("multi_pc_combat_started", manager.get_combat_state_summary())
    
    return manager


def end_combat_session() -> None:
    """End the current combat session and clean up."""
    global _active_combat_manager
    if _active_combat_manager:
        # UPSTREAM ALIGNMENT: Persist all combat changes before ending
        info("Ending combat session - persisting damage to character files...", category="combat_lifecycle")
        results = _active_combat_manager.persist_combat_changes()
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        info(f"Persisted changes for {success_count}/{total_count} characters", category="combat_lifecycle")
        
        emit_combat_event("combat_ended", {})
    _active_combat_manager = None


def cleanup_combat_manager() -> None:
    """
    Clean up the combat manager after combat ends.
    
    This is an alias for end_combat_session() provided for clarity
    when called from action_handler.py post-combat save logic.
    """
    end_combat_session()


def is_multi_pc_combat_enabled() -> bool:
    """Check if multi-PC combat mode is enabled."""
    return MULTIPLAYER_MODE


# ============================================================================
# PROMPT MODIFICATION UTILITIES
# ============================================================================

def modify_combat_prompt_for_multi_pc(
    base_prompt: str,
    pc_name: str,
    manager: MultiPCCombatManager
) -> str:
    """
    Modify the combat prompt to support multi-PC mode.
    
    This replaces generic "you/your" references with PC-specific language
    and adds multi-PC context.
    
    Args:
        base_prompt: Original single-PC combat prompt
        pc_name: Name of the currently active PC
        manager: The combat manager instance
        
    Returns:
        Modified prompt for multi-PC combat
    """
    # Add multi-PC header section
    multi_pc_header = f"""
++ MULTI-PC COMBAT MODE ACTIVE ++
This combat involves multiple player characters. Each PC takes their turn when 
selected by the player via the character tabs. Address the current PC by name
using [{pc_name}] instead of generic "you" references.

{manager.format_party_turn_summary()}

{manager.format_pc_context_for_prompt(pc_name)}

IMPORTANT MULTI-PC RULES:
1. Address actions to [{pc_name}] specifically, not generic "you"
2. When prompting for actions, ask "[{pc_name}], what do you do?"
3. Other PCs are treated as player-controlled allies, not AI NPCs
4. Only process the current PC's turn, then await the next PC selection
5. Death saves: Incapacitated PCs roll death saves on their turn

"""
    
    # Insert header after the first section of the prompt
    insert_point = base_prompt.find("++ HOW TO USE")
    if insert_point > 0:
        modified = base_prompt[:insert_point] + multi_pc_header + base_prompt[insert_point:]
    else:
        modified = multi_pc_header + base_prompt
    
    return modified


def get_multi_pc_initiative_narrative(manager: MultiPCCombatManager) -> str:
    """
    Generate narrative text for group initiative roll.
    
    Args:
        manager: Combat manager with initiative already rolled
        
    Returns:
        Narrative description of initiative
    """
    party_roll, enemy_roll, party_first = (
        manager.party_initiative,
        manager.enemy_initiative,
        manager.party_goes_first
    )

    pc_names = list(manager.pc_states.keys())
    pc_list = ", ".join(pc_names[:-1]) + f" and {pc_names[-1]}" if len(pc_names) > 1 else pc_names[0]
    
    if party_first:
        return f"""The party rolls for initiative as one! {pc_list} ready themselves for battle.
Party Initiative: {party_roll} | Enemy Initiative: {enemy_roll}
The heroes act first! Select which party member takes the opening move."""
    else:
        return f"""The party rolls for initiative as one! {pc_list} ready themselves for battle.
Party Initiative: {party_roll} | Enemy Initiative: {enemy_roll}
The enemies act first! Brace yourselves as the foes make their move."""
