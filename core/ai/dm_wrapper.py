#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# DM_WRAPPER.PY - AI INTEGRATION LAYER
# ============================================================================
# 
# ARCHITECTURE ROLE: AI Integration Abstraction Layer
# 
# This module abstracts OpenAI API interactions and implements our multi-model
# AI strategy. It provides a clean interface for AI-driven game management
# while maintaining strict response validation and error handling.
# 
# KEY RESPONSIBILITIES:
# - Manage OpenAI client instances and model configurations
# - Construct context-aware prompts with current game state
# - Handle API rate limiting, retries, and error recovery
# - Maintain conversation history and context management
# - Provide model-specific optimizations (temperature, tokens)
# 
# AI STRATEGY IMPLEMENTATION:
# - Primary DM Model: Main narrative and game logic
# - Validation Model: Response accuracy verification
# - Combat Model: Specialized turn-based combat management
# - Content Generation: Specialized builders for game content
# 
# ARCHITECTURAL INTEGRATION:
# - Core dependency for main.py game loop
# - Integrates with status_manager.py for user feedback
# - Uses conversation_utils.py for history management
# - Implements our "AI-First Design with Human Safety Nets" principle
# 
# VALIDATION PIPELINE:
# Prompt Construction → API Call → Response Parsing → Validation → Integration
# 
# This module embodies our philosophy of embracing AI capabilities while
# maintaining rigorous data integrity and error recovery mechanisms.
# ============================================================================
"""
NeverEndingQuest Wrapper Script

This script acts as a mediator between the user and the NeverEndingQuest application,
allowing for gameplay in environments that don't support direct interactive terminals.

Usage:
    python dm_wrapper.py [--turns N]

Options:
    --turns N    Number of turns to simulate (default: 1)
"""

import subprocess
import sys
import time
import re
import argparse
from pathlib import Path

def strip_ansi_codes(text):
    """Remove ANSI color codes from text"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def parse_args():
    parser = argparse.ArgumentParser(description="NeverEndingQuest Wrapper")
    parser.add_argument('--turns', type=int, default=1, help='Number of turns to simulate')
    return parser.parse_args()

def run_game_turn(command):
    """
    Run one turn of the game with the given command.
    
    Args:
        command: The command to send to the game
        
    Returns:
        The game's response
    """
    # Prepare the command with input
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Send input and get output
    try:
        stdout, stderr = process.communicate(input=command, timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return "ERROR: Game process timed out"
    
    # Check for errors
    if process.returncode != 0 and "EOFError" not in stderr:
        return f"ERROR: Game exited with code {process.returncode}\n{stderr}"
    
    # Clean and return the output
    clean_output = strip_ansi_codes(stdout + stderr)
    
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

def save_game_state(turn_num, command, response):
    """Save the game interaction to a markdown file"""
    output_dir = Path("game_logs")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = output_dir / f"game_turn_{turn_num}_{timestamp}.md"
    
    with open(filename, "w") as f:
        f.write(f"# NeverEndingQuest - Turn {turn_num}\n\n")
        f.write(f"## Player Command\n\n```\n{command}\n```\n\n")
        f.write(f"## Dungeon Master Response\n\n{response}\n")
    
    return filename

def main():
    args = parse_args()

    print("NeverEndingQuest Wrapper")
    print("=======================")
    print("This script will run your NeverEndingQuest application and save the output.")
    print("Using predefined commands for each turn")
    print()

    Path("game_logs").mkdir(exist_ok=True)

    # Predefined commands to try
    commands = [
        "I examine the dwarven runes on the door carefully, looking for clues about how to solve the puzzle.",
        "I'd like to solve the puzzle. I rotate the rings to align the runes based on the clues we've found during our journey.",
        "I say the dwarven phrase 'Khazad-dûm' aloud to deactivate the stone guardian and open the door.",
        "Let's proceed through the doorway into the Dwarven Complex."
    ]

    for turn in range(1, min(args.turns + 1, len(commands) + 1)):
        print(f"\n--- Turn {turn} ---")
        command = commands[turn - 1]
        print(f"\nNorn's action: {command}")

        print("\nRunning game... (this may take a few moments)")
        response = run_game_turn(command)

        # Save the interaction
        log_file = save_game_state(turn, command, response)

        print(f"\nDungeon Master's response saved to: {log_file}")
        print("\nResponse Preview:")
        print("-----------------")
        # Print a preview (first 200 chars)
        preview = response[:200] + "..." if len(response) > 200 else response
        print(preview)
    
    print("\nAll game interactions have been saved to the game_logs directory.")
    print("Thank you for playing NeverEndingQuest!")

if __name__ == "__main__":
    main()