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
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import re
import os

# Import config to check MULTIPLAYER_MODE
try:
    from config import MULTIPLAYER_MODE
except ImportError:
    MULTIPLAYER_MODE = False

# TABLETOP MODE: Imports for armorClass backfill from monster templates
try:
    from utils.module_path_manager import ModulePathManager
    from utils.encoding_utils import safe_json_load
except ImportError:
    ModulePathManager = None
    safe_json_load = None


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
class MultiPCCombatManager:
    """
    Manages combat state for multiple player characters.
    
    This is the core class for multi-PC combat support. It tracks:
    - All PCs in the party and their combat states
    - Which PCs have acted in the current round
    - Group initiative for PC party vs enemies
    - Death saving throws for incapacitated PCs
    - Turn Queue and Command Resolution
    """
    
    # PC states indexed by character name
    pc_states: Dict[str, PCCombatState] = field(default_factory=dict)
    
    # Combat tracking
    current_round: int = 1
    party_initiative: int = 0
    enemy_initiative: int = 0
    party_goes_first: bool = True
    
    # Turn Queue Management
    turn_queue: List[Combatant] = field(default_factory=list)
    current_turn_index: int = 0
    
    # Current active PC (selected via UI or Turn Queue)
    current_pc_name: Optional[str] = None
    
    # Combat phase tracking
    pc_phase_complete: bool = False
    enemy_phase_complete: bool = False
    
    # Narrative Context (stored between commands)
    last_attack_weapon: Optional[str] = None
    
    # Maximum party size (hard limit)
    MAX_PARTY_SIZE: int = 6
    
    def __post_init__(self):
        """Initialize with empty state if not provided."""
        if self.pc_states is None:
            self.pc_states = {}
        if self.turn_queue is None:
            self.turn_queue = []
    
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
        if self.pc_phase_complete:
            return "ENEMY_PHASE"
        return "PC_PHASE"
    
    def get_forbidden_actors_list(self) -> List[str]:
        """
        Get list of combatants that MUST NOT act during the current phase.
        
        During PC_PHASE: Returns all enemies and NPCs (they must wait for /end)
        During ENEMY_PHASE: Returns empty list (enemies are free to act)
        
        This creates a hard block for the LLM to prevent premature enemy narration.
        
        Returns:
            List of combatant names that are forbidden from acting
        """
        if not self.pc_phase_complete:
            # During PC phase, all enemies and NPCs are forbidden
            return [
                c.name for c in self.turn_queue 
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
            if pc != self.current_pc_name:
                return pc
        # If current PC is the only one left, return them
        return available[0] if available else None
    
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
            # Get character data if available
            char_data = party_data.get("characters", {}).get(member_name, {})
            
            hp_data = char_data.get("hp", {})
            current_hp = hp_data.get("current", hp_data.get("max", 10))
            max_hp = hp_data.get("max", 10)
            
            # Determine initial status based on HP
            if current_hp <= 0:
                status = PCStatus.INCAPACITATED
            else:
                status = PCStatus.READY
                
            # Capture any metadata (like position) from char_data
            metadata = char_data.get("metadata", {})
            if "position" in char_data:
                metadata["position"] = char_data["position"]
                
            self.pc_states[member_name] = PCCombatState(
                character_name=member_name,
                initiative_modifier=char_data.get("initiative_mod", 0),
                status=status,
                current_hp=current_hp,
                max_hp=max_hp,
                metadata=metadata
            )
        
        # Set first PC as current if none selected
        if not self.current_pc_name and self.pc_states:
            self.current_pc_name = list(self.pc_states.keys())[0]
            
    def initialize_turn_queue(self, encounter_data: Dict[str, Any]) -> None:
        """
        Build the turn queue from PC states and encounter data.
        Call this at the start of combat or when initiative changes.
        """
        self.turn_queue.clear()
        
        # Add PCs
        for name, state in self.pc_states.items():
            # Calculate initiative (d20 + mod)
            init_roll = random.randint(1, 20) + state.initiative_modifier
            self.turn_queue.append(Combatant(
                name=name,
                type=CombatantType.PC,
                initiative=init_roll,
                hp=state.current_hp,
                max_hp=state.max_hp,
                ac=10, # TODO: fetch from character sheet if available
                status=state.status.value
            ))
            
        # Add Enemies/NPCs
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
                        except Exception:
                            # Silently fall back to default if lookup fails
                            pass
                
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
        if current_actor and current_actor.type == CombatantType.PC:
            self.set_current_pc(current_actor.name)

    def get_current_actor(self) -> Optional[Combatant]:
        """Get the combatant whose turn it is."""
        if not self.turn_queue:
            return None
        return self.turn_queue[self.current_turn_index]

    def advance_turn(self) -> Combatant:
        """
        Move to the next turn in the queue.
        Skips dead combatants.
        """
        start_index = self.current_turn_index
        
        while True:
            self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_queue)
            
            # Check for round rollover
            if self.current_turn_index == 0:
                self.start_new_round()
            
            actor = self.turn_queue[self.current_turn_index]
            
            # Skip dead combatants
            if actor.status.lower() != "dead":
                if actor.type == CombatantType.PC:
                    self.set_current_pc(actor.name)
                return actor
                
            # Infinite loop safety (if everyone is dead)
            if self.current_turn_index == start_index:
                return actor

    def find_target(self, partial_name: str, encounter_data: Dict[str, Any]) -> Optional[Combatant]:
        """
        Fuzzy find a target in the encounter.
        Matches partial names (case-insensitive).
        Prioritizes enemies, then living targets.
        """
        partial_name = partial_name.lower().strip()
        candidates = []
        
        # Build list of all potential targets from encounter data to be safe
        # (TurnQueue might be stale if we don't update it constantly)
        # But TurnQueue is the source of truth for our logic, so use it.
        
        for c in self.turn_queue:
            if partial_name in c.name.lower():
                candidates.append(c)
        
        if not candidates:
            return None
            
        # Priority 1: Exact Match
        for c in candidates:
            if c.name.lower() == partial_name:
                return c
                
        # Priority 2: Living Enemies
        living_enemies = [c for c in candidates if c.type == CombatantType.ENEMY and c.status != "dead"]
        if living_enemies:
            return living_enemies[0]
            
        # Priority 3: Living Anything
        living = [c for c in candidates if c.status != "dead"]
        if living:
            return living[0]
            
        # Fallback: First candidate
        return candidates[0]

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
                         ac = c.get("armorClass", 10)
                         break
            
            if roll >= ac:
                return f"Dungeon Master: Hit! (Rolled {roll} vs AC {ac}). Roll damage.", None
            else:
                # Miss logic - pass to LLM for narration
                weapon_context = f" with {weapon_name}" if weapon_name else ""
                log_msg = f"[System: {actor_name} attacked {target.name}{weapon_context} with roll {roll} vs AC {ac} and MISSED.]"
                return f"Dungeon Master: Miss. (Rolled {roll} vs AC {ac}).\nProcessing outcome...", log_msg
                
        elif command == "/dmg":
            # Syntax: /dmg [amount] [flavor text...]
            if len(args) < 1:
                return "Dungeon Master: [SYSTEM] Usage: /dmg [amount] [optional flavor]", None
                
            try:
                amount = int(args[0])
            except ValueError:
                return "Dungeon Master: [SYSTEM] Invalid amount. Usage: /dmg [amount] [flavor]", None
            
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
                return "Dungeon Master: [SYSTEM] No target selected. Use /att first or specify target.", None
            
            # Apply Damage
            target.hp -= amount
            status_update = ""
            if target.hp <= 0:
                target.status = "dead" # or defeated/unconscious
                target.hp = 0
                status_update = " [Target Defeated]"
            elif target.hp < target.max_hp / 2:
                status_update = " [Bloodied]"
            
            log_msg = f"[System: {actor_name} dealt {amount} damage ({flavor_text}) to {target.name}. HP: {target.hp}/{target.max_hp}.{status_update}]"
            
            return f"Dungeon Master: Damage applied ({amount}). Target HP: {target.hp}/{target.max_hp}{status_update}.\nProcessing outcome...", log_msg
            
        return None, None

    # ... [Keep existing methods below] ...
    
    def roll_group_initiative(self) -> Tuple[int, int, bool]:
        """
        Roll group initiative for PC party vs enemies.
        
        Returns:
            Tuple of (party_roll, enemy_roll, party_goes_first)
        """
        # Roll d20 for each side
        party_roll = random.randint(1, 20)
        enemy_roll = random.randint(1, 20)
        
        # Add highest PC initiative modifier to party roll
        max_pc_mod = max(
            (pc.initiative_modifier for pc in self.pc_states.values()),
            default=0
        )
        self.party_initiative = party_roll + max_pc_mod
        self.enemy_initiative = enemy_roll
        
        # Determine who goes first (party wins ties)
        self.party_goes_first = self.party_initiative >= self.enemy_initiative
        
        return party_roll, enemy_roll, self.party_goes_first
    
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
    
    def complete_pc_turn(self, character_name: Optional[str] = None) -> bool:
        """
        Mark a PC's turn as complete.
        
        Args:
            character_name: PC who completed turn (uses current if None)
            
        Returns:
            True if all PCs have acted (PC phase complete)
        """
        name = character_name or self.current_pc_name
        if not name or name not in self.pc_states:
            return False
            
        self.pc_states[name].mark_acted()
        
        # Check if all PCs have acted
        available = self.get_available_pcs()
        incapacitated = self.get_incapacitated_pcs()
        
        # PC phase complete when no one left to act
        self.pc_phase_complete = len(available) == 0 and len(incapacitated) == 0
        
        return self.pc_phase_complete
    
    def force_end_pc_phase(self) -> None:
        """
        Forcefully mark all PCs as having acted this round.
        Used when the DM manually triggers the enemy phase via /end.
        This ensures the prompt context reflects that the PC phase is over.
        """
        for state in self.pc_states.values():
            if state.status == PCStatus.READY:
                state.status = PCStatus.ACTED
        
        self.pc_phase_complete = True

    def get_remaining_enemies_for_round(self) -> List[str]:
        """
        Get a list of enemies/NPCs that should act in the enemy phase.
        Uses pc_phase_complete state + initiative order (Option B approach).
        
        DETERMINISM RULE: This function MUST ignore current_turn_index.
        It returns ALL living non-PCs. The LLM then processes them in initiative order.
        
        Returns:
            List of combatant names (Enemies and NPCs) in initiative order
        """
        pending = []
        if not self.turn_queue:
            return pending
        
        # Get all living enemies and NPCs from the turn_queue
        # We ignore current_turn_index because manual PC tab selection desyncs it.
        # In ENEMY_PHASE, we want a full batch of all enemies.
        enemies_and_npcs = [
            c for c in self.turn_queue 
            if c.type in (CombatantType.ENEMY, CombatantType.NPC) and c.status.lower() != "dead"
        ]
        
        # Sort by initiative descending (highest first)
        enemies_and_npcs.sort(key=lambda x: x.initiative, reverse=True)
        
        # Return names in order
        pending = [c.name for c in enemies_and_npcs]
        
        return pending

    def start_new_round(self) -> int:
        """
        Start a new combat round.
        
        Returns:
            The new round number
        """
        self.current_round += 1
        self.pc_phase_complete = False
        self.enemy_phase_complete = False
        
        # Reset Turn Queue Pointer to the top of initiative
        self.current_turn_index = 0
        
        # Update active PC if the new first actor is a PC
        current_actor = self.get_current_actor()
        if current_actor and current_actor.type == CombatantType.PC:
            self.set_current_pc(current_actor.name)
        
        # Reset all PC states for new round
        for state in self.pc_states.values():
            state.reset_for_new_round()
            
        return self.current_round
    
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
    
    def get_combat_state_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current combat state for the UI.
        
        Returns:
            Dictionary with combat state info
        """
        return {
            "current_round": self.current_round,
            "party_initiative": self.party_initiative,
            "enemy_initiative": self.enemy_initiative,
            "party_goes_first": self.party_goes_first,
            "current_pc": self.current_pc_name,
            "pc_phase_complete": self.pc_phase_complete,
            "enemy_phase_complete": self.enemy_phase_complete,
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
                for name, state in self.pc_states.items()
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
        if pc_name not in self.pc_states:
            return ""
            
        state = self.pc_states[pc_name]
        
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
        lines = [f"=== PC PARTY TURN STATUS (Round {self.current_round}) ==="]
        
        for name, state in self.pc_states.items():
            marker = "[>]" if name == self.current_pc_name else "   "
            status_icon = {
                PCStatus.READY: "⏳ Ready",
                PCStatus.ACTED: "✓ Acted", 
                PCStatus.INCAPACITATED: "💀 Down",
                PCStatus.DEAD: "☠️ Dead",
                PCStatus.STABLE: "😴 Stable"
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
            "combat_round": self.current_round,
            "active_pc": self.current_pc_name,
            "party_initiative": self.party_initiative,
            "enemy_initiative": self.enemy_initiative,
            "party_goes_first": self.party_goes_first,
            "pc_phase_complete": self.pc_phase_complete,
            "player_characters": []
        }
        
        for name, state in self.pc_states.items():
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
        forbidden = self.get_forbidden_actors_list()
        forbidden_str = ", ".join(forbidden) if forbidden else "None"
        
        # ====================================================================
        # ENEMY_PHASE: BATCH MODE (after /end command)
        # ====================================================================
        if self.pc_phase_complete:
            pending = self.get_remaining_enemies_for_round()
            actors_str = ", ".join(pending) if pending else "remaining enemies"
            
            # Explicitly identify Player Characters to forbid them from acting
            pc_names = list(self.pc_states.keys())
            pc_forbidden_str = ", ".join(pc_names) if pc_names else "None"
            
            return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  CURRENT PHASE: ENEMY_PHASE  │  PC PHASE COMPLETE: TRUE                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MODE: ENEMY & NPC BATCH RESOLUTION                                          ║
║  RESOLVE IN ORDER: {actors_str[:60]}
╠══════════════════════════════════════════════════════════════════════════════╣
║  ⛔ FORBIDDEN ACTORS (DO NOT NARRATE):                                       ║
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

        # ====================================================================
        # PC_PHASE: STRICT TURN ISOLATION MODE
        # ====================================================================
        current_actor = self.get_current_actor()
        actor_name = current_actor.name if current_actor else "Current Actor"
        
        # Get next PC for continuation prompt
        next_pc = self.get_next_pc_to_act()
        next_pc_prompt = f'Ask: "What does {next_pc} do?"' if next_pc else 'Await /end command for enemy phase.'
        
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
║  ⛔ FORBIDDEN ACTORS (DO NOT NARRATE):                                       ║
║  {forbidden_str[:70]:<70} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  REQUIRED RESPONSE:                                                          ║
║  1. Narrate ONLY the result of {actor_name}'s declared action.               ║
║  2. FLAVOR TEXT: Treat shouts/battle cries as roleplay from {actor_name}.    ║
║  3. STOP IMMEDIATELY after this single resolution.                           ║
║  4. DO NOT narrate actions for other PCs. Await /end for enemy phase.        ║
║  4. {next_pc_prompt:<68} ║
║  5. Return structured JSON with plan, narration, combat_round, actions.      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ⚠️  VIOLATION = CRITICAL FAILURE: Narrating for forbidden actors will      ║
║      cause combat desync. Only [{actor_name}] has authority to act now.
╚══════════════════════════════════════════════════════════════════════════════╝
"""

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
        import json
        
        # Get current round
        current_round = self.current_round
        
        # Build initiative order from turn_queue
        initiative_lines = []
        tracker_lines = []
        
        # Sort turn queue by initiative (highest first)
        sorted_queue = sorted(self.turn_queue, key=lambda x: x.initiative, reverse=True)
        
        for combatant in sorted_queue:
            name = combatant.name
            init = combatant.initiative
            status = combatant.status.lower()
            
            # Determine state marker for tracker
            if status == "dead":
                marker = "[D]"
                state = "Dead"
            elif combatant.type == CombatantType.PC:
                # Check PC state
                pc_state = self.pc_states.get(name)
                if pc_state:
                    if pc_state.status == PCStatus.ACTED:
                        marker = "[X]"
                        state = "Acted"
                    elif name == self.current_pc_name:
                        marker = "[>]"
                        state = "CURRENT TURN"
                    else:
                        marker = "[ ]"
                        state = "Waiting"
                else:
                    marker = "[ ]"
                    state = "Waiting"
            else:
                # For NPCs/Enemies, mark as acted if they've been processed
                # We'll assume all non-PCs are "Waiting" unless explicitly marked
                marker = "[ ]"
                state = "Waiting"
            
            initiative_lines.append(f"- {name} ({init}) - {status}")
            tracker_lines.append(f"- {marker} {name} ({init}) - {state}")
        
        # Determine instruction block based on phase
        instruction_block = ""
        turn_window = []
        
        if self.pc_phase_complete:
            # ENEMY_PHASE: Process all remaining enemies
            pending_enemies = self.get_remaining_enemies_for_round()
            if pending_enemies:
                enemy_list = "\n".join([f"- {name}" for name in pending_enemies])
                instruction_block = f""">>> PROCESS TO END ROUND:
{enemy_list}
>>> THEN: End Round {current_round}, Start Round {current_round + 1}"""
                turn_window = pending_enemies
            else:
                # All enemies acted, round complete
                instruction_block = ">>> ROUND COMPLETE\nAll creatures have acted. Increment combat_round."
                turn_window = []
        else:
            # PC_PHASE: Find next PC and determine what to process before them
            active_pc = self.current_pc_name
            
            # Find where active PC is in initiative order
            active_pc_index = -1
            for i, combatant in enumerate(sorted_queue):
                if combatant.name == active_pc:
                    active_pc_index = i
                    break
            
            if active_pc_index >= 0:
                # Check if any non-PCs act before the active PC
                npcs_before = []
                for i in range(active_pc_index):
                    combatant = sorted_queue[i]
                    if combatant.type in (CombatantType.ENEMY, CombatantType.NPC):
                        # Check if they haven't acted yet (we'd need to track this better)
                        # For now, assume all non-PCs before active PC need to act
                        npcs_before.append(combatant.name)
                
                if npcs_before:
                    npc_list = "\n".join([f"- {name}" for name in npcs_before])
                    instruction_block = f""">>> PROCESS ALL OF THESE IN ONE RESPONSE (Initiative Order):
{npc_list}
>>> THEN STOP AT: {active_pc} (Player)"""
                    turn_window = npcs_before + [active_pc]
                else:
                    # No NPCs before this PC - it's their turn
                    instruction_block = f">>> CURRENT: {active_pc} ({sorted_queue[active_pc_index].initiative}) - PLAYER TURN (await input)"
                    turn_window = [active_pc]
        
        # Build tracker output
        tracker_output = f"""--- ROUND INFO ---
combat_round: {current_round}
player_name: {self.current_pc_name}
initiative_order:
{chr(10).join(initiative_lines)}

--- LIVE TRACKER ---
**Live Initiative Tracker:**
{chr(10).join(tracker_lines)}

{instruction_block}

```json
{{
  "combat_round": {current_round},
  "player_name": "{self.current_pc_name}",
  "turn_window": {json.dumps(turn_window)},
  "pc_phase_complete": {str(self.pc_phase_complete).lower()}
}}
```"""
        
        return tracker_output


# Global instance for combat session
_active_combat_manager: Optional[MultiPCCombatManager] = None
_combat_callback: Optional[Any] = None  # Callback for combat events (e.g., to web UI)


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
            print(f"Error in combat callback: {e}")


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
