# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# GENERATE_PREROLLS.PY - COMBAT DICE MANAGEMENT SYSTEM
# ============================================================================
# 
# ARCHITECTURE ROLE: Game Systems Layer - Combat Support
# 
# This module implements our solution to AI confusion about attack counts in
# combat by providing pre-rolled dice with explicit attack limitations.
# It demonstrates our "AI-First Design with Human Safety Nets" principle.
# 
# KEY RESPONSIBILITIES:
# - Generate structured dice pools for flexible combat use
# - Load actual attack counts from monster/NPC data files
# - Provide clear formatting to prevent AI misinterpretation
# - Handle schema differences between monsters and NPCs
# - Generate appropriate saving throw dice for all creatures
# - Track combat rounds and provide unique preroll IDs
# - Support round-based caching for dice consistency
# 
# PROBLEM SOLVED:
# Previously, AI would see multiple dice rolls and assume multiple attacks.
# Now we explicitly state "X attacks available" with exact counts from
# creature data files, preventing combat rule violations.
# 
# DICE ORGANIZATION:
# 1. Generic Dice Pool: For spells, abilities, and improvisation
# 2. Creature-Specific Attacks: Exact number based on actual creature data
# 3. Saving Throws: Complete set for all creatures in encounter
# 
# ARCHITECTURAL INTEGRATION:
# - Used by combat_manager.py for encounter preparation
# - Integrates with ModulePathManager for creature data loading
# - Supports both monster 'actions' and NPC 'attacksAndSpellcasting' schemas
# - Implements our "Data Integrity Above All" principle
# 
# DESIGN PATTERNS:
# - Strategy Pattern: Different data loading for monsters vs NPCs
# - Template Method: Consistent dice generation pipeline
# - Factory Pattern: Creates appropriate dice structures per creature type
# 
# This module exemplifies how we solve AI limitations through structured
# data presentation while maintaining game rule accuracy.
# ============================================================================

import random
import json
import os

from core.combat.attacks import attack_sequence

def generate_generic_dice_pool():
    """Generate a pool of various dice types for flexible use"""
    dice_pool = {
        "d4": [random.randint(1, 4) for _ in range(8)],
        "d6": [random.randint(1, 6) for _ in range(8)], 
        "d8": [random.randint(1, 8) for _ in range(6)],
        "d10": [random.randint(1, 10) for _ in range(6)],
        "d12": [random.randint(1, 12) for _ in range(4)],
        "d20": [random.randint(1, 20) for _ in range(10)]  # Extra d20s for various uses
    }
    return dice_pool

def get_monster_attacks(monster_type):
    """Load monster attack data from monster file"""
    if not monster_type:
        return [{"name": "monster attack"}], 1
        
    try:
        from utils.module_path_manager import ModulePathManager
        from utils.encoding_utils import safe_json_load
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        monster_file = path_manager.get_monster_path(monster_type)
        
        with open(monster_file, "r") as file:
            monster_data = json.load(file)
        
        # Use the same exact/safe sequence contract as the resolver. A blank
        # Multiattack marker is never itself counted as an executable attack.
        sequence = attack_sequence(monster_data)
        if not sequence:
            return [{"name": f"{monster_type} attack"}], 1

        attack_actions = [{"name": action.get("name", "attack")} for action in sequence]
        return attack_actions, len(attack_actions)
        
    except Exception as e:
        print(f"Error loading monster {monster_type}: {e}")
        return [{"name": f"{monster_type} attack"}], 1

def get_npc_attacks(npc_name):
    """Load NPC attack data from character file"""
    if not npc_name:
        return [{"name": "weapon attack"}], 1
        
    try:
        from utils.module_path_manager import ModulePathManager
        from utils.encoding_utils import safe_json_load
        from updates.update_character_info import find_character_file_fuzzy
        
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        
        # Use fuzzy matching to find the correct NPC file
        matched_name = find_character_file_fuzzy(npc_name)
        if not matched_name:
            print(f"Warning: Could not find NPC file for '{npc_name}' using fuzzy matching")
            return [{"name": "weapon attack"}], 1
            
        npc_file = path_manager.get_character_path(matched_name)
        
        with open(npc_file, "r") as file:
            npc_data = json.load(file)
        
        sequence = attack_sequence(npc_data)
        if not sequence:
            return [{"name": "weapon attack"}], 1

        attack_list = [{"name": attack.get("name", "attack")} for attack in sequence]
        return attack_list, len(attack_list)
        
    except Exception as e:
        print(f"Error loading NPC {npc_name}: {e}")
        return [{"name": "weapon attack"}], 1

def generate_prerolls(encounter_data, round_num=None):
    """Generate organized dice rolls with generic pool and creature-specific attacks.
    
    Args:
        encounter_data: The encounter data dictionary
        round_num: The current combat round number (defaults to 1 if not specified)
    
    Returns:
        str: Formatted preroll text with round tracking
    """
    # Determine round number
    if round_num is None:
        round_num = encounter_data.get('current_round', 1)
    
    # Generate preroll ID for tracking
    preroll_id = f"{round_num}-{random.randint(1000,9999)}"
    
    preroll_lines = []
    preroll_lines.append(f"DM Note: COMBAT ROUND {round_num} - DICE AVAILABLE:")
    preroll_lines.append(f"Preroll Set ID: {preroll_id} (Generated at round start)")
    preroll_lines.append("")
    
    # Add critical dice usage instructions
    preroll_lines.append("CRITICAL DICE USAGE:")
    preroll_lines.append("- For NPC/Monster ATTACKS, you MUST use a die from the \"CREATURE ATTACKS\" list for that specific creature.")
    preroll_lines.append("- For NPC/Monster SAVING THROWS, you MUST use a die from the \"SAVING THROWS\" list.")
    preroll_lines.append("- The \"GENERIC DICE\" pool is ONLY for damage rolls, spell effects, or other non-attack/non-save rolls.")
    preroll_lines.append("- FAILURE TO USE THE CORRECT POOL IS A CRITICAL ERROR.")
    preroll_lines.append("")
    
    # Generate generic dice pool
    dice_pool = generate_generic_dice_pool()
    preroll_lines.append("=== GENERIC DICE (use for spells, abilities, improvisation) ===")
    dice_line_parts = []
    for die_type, rolls in dice_pool.items():
        rolls_str = ",".join(map(str, rolls))
        dice_line_parts.append(f"{die_type}: [{rolls_str}]")
    preroll_lines.append(" | ".join(dice_line_parts))
    preroll_lines.append("")
    
    # Find player name for context
    player_name = "Unknown Player"
    for creature in encounter_data.get("creatures", []):
        if creature.get("type") == "player":
            player_name = creature.get("name", "Unknown Player")
            break
    
    # Generate creature-specific attack rolls
    preroll_lines.append("=== CREATURE ATTACKS (exact number per creature) ===")
    preroll_lines.append(f"[PLAYER: {player_name}] Must make own rolls")
    
    attack_creatures = []
    saving_throw_creatures = []
    
    for creature in encounter_data.get("creatures", []):
        if creature.get("type") == "player":
            continue
            
        creature_name = creature.get("name", "Unknown Creature")
        creature_type = creature.get("type", "unknown").upper()
        
        # Get attack information from encounter data OR load from files
        num_attacks = creature.get("numAttacks")
        attacks_info = creature.get("attacks", [])
        
        # If encounter doesn't have attack info, load from monster/NPC files
        if num_attacks is None or not attacks_info:
            try:
                if creature.get("type") == "enemy":
                    # Load monster file to get actions
                    monster_type = creature.get("monsterType", "")
                    attacks_info, num_attacks = get_monster_attacks(monster_type)
                elif creature.get("type") == "npc":
                    # Load NPC file to get attacksAndSpellcasting  
                    from utils.module_path_manager import ModulePathManager
                    path_manager = ModulePathManager()
                    npc_name = path_manager.format_filename(creature_name)
                    attacks_info, num_attacks = get_npc_attacks(npc_name)
            except Exception as e:
                print(f"Warning: Could not load attack data for {creature_name}: {e}")
                # Fallback defaults
                num_attacks = 1
                creature_type_name = creature.get("monsterType", creature.get("type", "creature"))
                attacks_info = [{"name": f"{creature_type_name} attack"}]
        
        # Final fallback if still no data
        if not num_attacks:
            num_attacks = 1
        if not attacks_info:
            creature_type_name = creature.get("monsterType", creature.get("type", "creature"))
            attacks_info = [{"name": f"{creature_type_name} attack"}]
        
        # Generate exact number of attack rolls needed
        attack_rolls = [random.randint(1, 20) for _ in range(num_attacks)]
        
        # Format attack information
        if num_attacks == 1:
            attack_desc = f"Attack[{attack_rolls[0]}] (1 attack available"
            if attacks_info:
                attack_name = attacks_info[0].get("name", "attack")
                attack_desc += f": {attack_name}"
            attack_desc += ")"
        else:
            attack_rolls_str = "], Attack[".join(map(str, attack_rolls))
            attack_desc = f"Attack[{attack_rolls_str}] ({num_attacks} attacks available"
            if attacks_info:
                attack_names = [attack.get("name", "attack") for attack in attacks_info[:num_attacks]]
                attack_desc += f": {', '.join(attack_names)}"
            attack_desc += ")"
        
        attack_creatures.append(f"{creature_name}: {attack_desc}")
        
        # Generate saving throws for this creature
        save_rolls = {
            "STR": random.randint(1, 20),
            "DEX": random.randint(1, 20), 
            "CON": random.randint(1, 20),
            "INT": random.randint(1, 20),
            "WIS": random.randint(1, 20),
            "CHA": random.randint(1, 20)
        }
        save_rolls_str = ", ".join([f"{ability}:{roll}" for ability, roll in save_rolls.items()])
        saving_throw_creatures.append(f"{creature_name}: {save_rolls_str}")
    
    # Add attack information
    for attack_line in attack_creatures:
        preroll_lines.append(attack_line)
    
    preroll_lines.append("")
    preroll_lines.append("=== SAVING THROWS ===")
    for save_line in saving_throw_creatures:
        preroll_lines.append(save_line)
    
    preroll_lines.append("")
    preroll_lines.append("IMPORTANT: Each creature can only make the number of attacks listed above.")
    preroll_lines.append("Use generic dice pool for damage rolls, spells, and other abilities.")
    preroll_lines.append("Apply all appropriate modifiers (ability scores, proficiency, weapon bonuses, etc.).")
    preroll_lines.append(f"Note: {player_name} must make their own rolls.")
    preroll_lines.append("")
    preroll_lines.append("COMBAT TRACKING: You MUST include \"combat_round\" field in your JSON response.")
    preroll_lines.append("Track combat rounds: increment ONLY when ALL alive creatures have completed their turns in initiative order.")
    preroll_lines.append(f"These dice remain constant throughout the current round.")
    
    return "\n".join(preroll_lines)

def test_generate_prerolls():
    """Test function for generate_prerolls"""
    # Create a sample encounter with the new structure
    sample_encounter = {
        "encounterId": "test_encounter",
        "creatures": [
            {
                "type": "player",
                "name": "Norn"
            },
            {
                "type": "enemy",
                "name": "Goblin 1",
                "monsterType": "goblin",
                "numAttacks": 1,
                "attacks": [{"name": "Scimitar", "attackBonus": 4, "damageDice": "1d6+2"}]
            },
            {
                "type": "enemy", 
                "name": "Orc Chief",
                "monsterType": "orc",
                "numAttacks": 2,
                "attacks": [
                    {"name": "Battleaxe", "attackBonus": 6, "damageDice": "1d8+4"},
                    {"name": "Handaxe", "attackBonus": 6, "damageDice": "1d6+4"}
                ]
            },
            {
                "type": "npc",
                "name": "Elara",
                "numAttacks": 1,
                "attacks": [{"name": "Longbow", "attackBonus": 5, "damageDice": "1d8+3"}]
            }
        ]
    }
    
    prerolls = generate_prerolls(sample_encounter)
    print(prerolls)

if __name__ == "__main__":
    test_generate_prerolls()
