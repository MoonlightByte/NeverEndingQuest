#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Enhanced NeverEndingQuest Wrapper Script

DEPRECATED: superseded by headless mode (run_headless.py and
core/headless/client.py), which drives the engine in-process over a
structured NDJSON protocol instead of scraping a subprocess's stdout.
See docs/HEADLESS_MODE.md. Kept only for reference.

This script creates a more robust mediator between the user and the NeverEndingQuest application,
allowing for gameplay in environments that don't support direct interactive terminals.

Features:
- Supports combat scenarios with dice roll simulation
- Handles multiple turns with state tracking
- Saves conversation history and game state to markdown files
- Provides detailed logging of game mechanics
"""

import subprocess
import sys
import time
import re
import json
import random
import argparse
import os
from pathlib import Path
from datetime import datetime

class GameState:
    """Track the current state of the game"""
    def __init__(self):
        self.turn_number = 0
        self.in_combat = False
        self.current_location = ""
        self.current_hp = 0
        self.max_hp = 0
        self.xp = 0
        self.next_level_xp = 0
        self.time = ""
        self.player_name = "Norn"  # Default player name
        self.combat_turn = 0
        self.encounter_id = ""
        
        # Load initial state from files
        self.reload_state()
    
    def reload_state(self):
        """Reload current game state from files"""
        try:
            with open("party_tracker.json", "r", encoding="utf-8") as f:
                party_data = json.load(f)
                self.current_location = party_data["worldConditions"]["currentLocation"]
                self.time = party_data["worldConditions"]["time"]
                self.player_name = party_data["partyMembers"][0]
                self.in_combat = bool(party_data["worldConditions"].get("activeCombatEncounter", ""))
                self.encounter_id = party_data["worldConditions"].get("activeCombatEncounter", "")
            
            from updates.update_character_info import normalize_character_name
            player_file = f"{normalize_character_name(self.player_name)}.json"
            with open(player_file, "r", encoding="utf-8") as f:
                player_data = json.load(f)
                self.current_hp = player_data["hitPoints"]
                self.max_hp = player_data["maxHitPoints"]
                self.xp = player_data["experience_points"]
                self.next_level_xp = player_data["exp_required_for_next_level"]
        except Exception as e:
            print(f"Warning: Could not load game state: {str(e)}")

def strip_ansi_codes(text):
    """Remove ANSI color codes from text"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def parse_args():
    parser = argparse.ArgumentParser(description="Enhanced NeverEndingQuest Wrapper")
    parser.add_argument('--turns', type=int, default=1, help='Number of turns to simulate')
    parser.add_argument('--scenario', type=str, default='puzzle', 
                        choices=['puzzle', 'combat', 'exploration'], 
                        help='Type of scenario to simulate')
    parser.add_argument('--auto-dice', action='store_true', 
                        help='Automatically roll dice when prompted')
    return parser.parse_args()

def get_scenario_commands(scenario_type):
    """Get predefined commands based on scenario type"""
    scenarios = {
        'puzzle': [
            "I examine the dwarven runes on the door carefully, looking for clues about how to solve the puzzle.",
            "I'd like to solve the puzzle. I rotate the rings to align the runes based on the clues we've found during our journey.",
            "I say the dwarven phrase 'Khazad-dûm' aloud to deactivate the stone guardian.",
            "Let's proceed through the doorway into the Dwarven Complex."
        ],
        'combat': [
            "I attack the Stone Guardian with my longsword.",
            "I use my Second Wind ability to regain some hit points.",
            "I try to flank the guardian while Gilly distracts it.",
            "I use Action Surge to attack again with my longsword."
        ],
        'exploration': [
            "I want to search the room for any hidden compartments or treasures.",
            "What can I see in this chamber? I'm looking for any signs of the Elemental Forge.",
            "I consult the worn journal to see if there's any information about this area.",
            "Let's move deeper into the complex. I lead the way with my weapon ready."
        ]
    }
    return scenarios.get(scenario_type, scenarios['puzzle'])

def simulate_dice_roll(dice_string='1d20'):
    """Simulate a dice roll based on string like '1d20' or '3d6'"""
    match = re.match(r'(\d+)d(\d+)', dice_string)
    if not match:
        return random.randint(1, 20)  # Default to d20
    
    num_dice = int(match.group(1))
    dice_type = int(match.group(2))
    
    total = sum(random.randint(1, dice_type) for _ in range(num_dice))
    return total

def detect_combat_prompt(text):
    """Detect if the game is asking for a combat action or dice roll"""
    combat_patterns = [
        r'roll a d20',
        r'roll \d+d\d+',
        r'make an? \w+ (saving throw|check)',
        r'what would you like to do\?.*\[HP:',
        r'your turn.*what do you do\?'
    ]
    
    for pattern in combat_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def detect_dice_prompt(text):
    """Extract what kind of dice roll is being requested"""
    dice_patterns = [
        (r'roll a d20', '1d20'),
        (r'roll a d(\d+)', r'1d\1'),
        (r'roll (\d+)d(\d+)', r'\1d\2')
    ]
    
    for pattern, dice in dice_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if dice.startswith(r'\1'):
                # Handle the case with capture groups
                if len(match.groups()) == 1:
                    return f"1d{match.group(1)}"
                else:
                    return f"{match.group(1)}d{match.group(2)}"
            return dice
    
    # Default to d20 if we're not sure
    return "1d20"

def generate_combat_response(text, auto_dice=True):
    """Generate an appropriate response to a combat prompt"""
    if "roll" in text.lower() or "check" in text.lower() or "saving throw" in text.lower():
        if auto_dice:
            dice_type = detect_dice_prompt(text)
            roll_result = simulate_dice_roll(dice_type)
            modifier = random.randint(1, 5)  # Simulate a typical modifier
            return f"I rolled {roll_result} + {modifier} = {roll_result + modifier}"
        else:
            return "I rolled a 15" # Fixed response for non-auto mode
    else:
        combat_actions = [
            "I attack with my longsword!",
            "I use Second Wind to heal myself!",
            "I try to dodge out of the way!",
            "I take the Dodge action!",
            "I'll use Action Surge to attack twice!",
            "I call out to Gilly to flank the enemy!"
        ]
        return random.choice(combat_actions)

def run_game_turn(command, state, auto_dice=False):
    """
    Run one turn of the game with the given command.
    
    Args:
        command: The command to send to the game
        state: GameState object tracking current state
        auto_dice: Whether to automatically generate dice rolls
        
    Returns:
        The game's response
    """
    # Prepare the command with input
    try:
        process = subprocess.Popen(
            ["python", "main.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send initial input
        stdout_data, stderr_data = b"", b""
        
        # Write the command to stdin
        process.stdin.write(f"{command}\n")
        process.stdin.flush()
        
        # Set a timeout
        max_wait_time = 30
        start_time = time.time()
        
        # Buffer for collecting output
        output_buffer = ""
        
        # Handle potential combat interaction
        while process.poll() is None and time.time() - start_time < max_wait_time:
            # Check if there's data to read from stdout or stderr
            stdout_chunk = process.stdout.readline()
            stderr_chunk = process.stderr.readline()
            
            if stdout_chunk:
                output_buffer += stdout_chunk
            if stderr_chunk:
                output_buffer += stderr_chunk
            
            # Check if we're being prompted for combat input
            if state.in_combat or detect_combat_prompt(output_buffer):
                state.in_combat = True
                combat_response = generate_combat_response(output_buffer, auto_dice)
                # Log what's happening
                print(f"Combat detected! Responding with: {combat_response}")
                try:
                    # Send the combat response
                    process.stdin.write(f"{combat_response}\n")
                    process.stdin.flush()
                except:
                    # If the process has ended, just break the loop
                    break
            
            # Small delay to prevent CPU hammering
            time.sleep(0.1)
        
        # Attempt to get any remaining output
        try:
            remaining_stdout, remaining_stderr = process.communicate(timeout=2)
            output_buffer += remaining_stdout + remaining_stderr
        except subprocess.TimeoutExpired:
            process.kill()
            remaining_stdout, remaining_stderr = process.communicate()
            output_buffer += remaining_stdout + remaining_stderr
            
    except Exception as e:
        return f"ERROR: Exception running game: {str(e)}"
    
    # Update state based on what happened
    state.turn_number += 1
    state.reload_state()  # Reload state from files
    
    # Clean and return the output
    clean_output = strip_ansi_codes(output_buffer)
    
    # Extract the DM's narration
    narration_matches = re.findall(r'Dungeon Master: (.*?)(?:\[\w+\]|\n\n|$)', clean_output, re.DOTALL)
    
    # Return the gameplay content
    if narration_matches:
        # Join multiple narration segments if they exist
        narration = "\n\n".join(narration_matches).strip()
        return narration
    else:
        # If we can't extract narration, return everything
        return clean_output

def save_game_state(turn_num, command, response, state):
    """Save the game interaction to a markdown file"""
    output_dir = Path("game_logs")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = output_dir / f"game_turn_{turn_num}_{timestamp}.md"
    
    with open(filename, "w") as f:
        f.write(f"# NeverEndingQuest - Turn {turn_num}\n\n")
        f.write(f"## Game State\n\n")
        f.write(f"- **Location:** {state.current_location}\n")
        f.write(f"- **Time:** {state.time}\n")
        f.write(f"- **Player:** {state.player_name} (HP: {state.current_hp}/{state.max_hp})\n")
        f.write(f"- **XP:** {state.xp}/{state.next_level_xp}\n")
        f.write(f"- **Combat:** {'Active' if state.in_combat else 'Inactive'}\n")
        if state.in_combat:
            f.write(f"- **Encounter:** {state.encounter_id}\n")
        f.write(f"\n## Player Command\n\n```\n{command}\n```\n\n")
        f.write(f"## Dungeon Master Response\n\n{response}\n")
    
    return filename

def main():
    args = parse_args()
    
    print("Enhanced NeverEndingQuest Wrapper")
    print("================================")
    print("This script will run your NeverEndingQuest application with automatic responses.")
    print(f"Scenario: {args.scenario}")
    print(f"Auto-dice: {'Enabled' if args.auto_dice else 'Disabled'}")
    print()
    
    Path("game_logs").mkdir(exist_ok=True)
    
    # Get the appropriate commands for the scenario
    commands = get_scenario_commands(args.scenario)
    
    # Initialize game state
    state = GameState()
    
    for turn in range(1, min(args.turns + 1, len(commands) + 1)):
        print(f"\n--- Turn {turn} ---")
        command = commands[turn - 1]
        print(f"\n{state.player_name}'s action: {command}")
        
        print("\nRunning game... (this may take a few moments)")
        response = run_game_turn(command, state, args.auto_dice)
        
        # Reload state after the turn
        state.reload_state()
        
        # Save the interaction
        log_file = save_game_state(turn, command, response, state)
        
        print(f"\nDungeon Master's response saved to: {log_file}")
        print("\nResponse Preview:")
        print("-----------------")
        # Print a preview (first 200 chars)
        preview = response[:200] + "..." if len(response) > 200 else response
        print(preview)
        
        print(f"\nCurrent state: {state.player_name} at {state.current_location} [HP: {state.current_hp}/{state.max_hp}]")
        if state.in_combat:
            print(f"In combat: Encounter {state.encounter_id}")
    
    print("\nAll game interactions have been saved to the game_logs directory.")
    print("Thank you for playing NeverEndingQuest!")

if __name__ == "__main__":
    main()