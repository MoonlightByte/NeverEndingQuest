#!/usr/bin/env python3
"""
PC Management utility for Tabletop Multiplayer.
Handles Player Character registration, removal, and selection.
Ensures PCs are correctly stored in party_tracker.json separate from NPCs.
"""

import os
from typing import List, Optional, Dict, Any
from utils.file_operations import safe_read_json, safe_write_json
from utils.enhanced_logger import info, error, debug

PARTY_TRACKER_FILE = "party_tracker.json"

def get_party_tracker() -> Dict[str, Any]:
    """Load the party tracker, initializing it if necessary."""
    data = safe_read_json(PARTY_TRACKER_FILE)
    if data is None:
        data = {
            "module": "Unknown",
            "partyMembers": [],
            "partyNPCs": [],
            "active_character": "",
            "worldConditions": {}
        }
    
    # Ensure necessary keys exist
    if "partyMembers" not in data:
        data["partyMembers"] = []
    if "partyNPCs" not in data:
        data["partyNPCs"] = []
    if "active_character" not in data:
        data["active_character"] = data["partyMembers"][0] if data["partyMembers"] else ""
        
    return data

def save_party_tracker(data: Dict[str, Any]) -> bool:
    """Save the party tracker data."""
    return safe_write_json(PARTY_TRACKER_FILE, data)

def add_pc(character_name: str) -> bool:
    """
    Explicitly add a Player Character to the party.
    This bypasses LLM guessing and hard-wires the categorization.
    """
    if not character_name:
        return False
        
    data = get_party_tracker()
    
    if character_name in data["partyMembers"]:
        info(f"PC '{character_name}' is already in the party.")
        return True
    
    # Check if they were accidentally added as an NPC
    npc_names = [npc.get("name") for npc in data["partyNPCs"]]
    if character_name in npc_names:
        info(f"Moving '{character_name}' from NPCs to PCs.")
        data["partyNPCs"] = [npc for npc in data["partyNPCs"] if npc.get("name") != character_name]
    
    data["partyMembers"].append(character_name)
    
    # Set as active character if none is set
    if not data.get("active_character"):
        data["active_character"] = character_name
        
    success = save_party_tracker(data)
    if success:
        info(f"Successfully added PC '{character_name}' to the party.")
    else:
        error(f"Failed to add PC '{character_name}' to the party tracker.")
    return success

def remove_pc(character_name: str) -> bool:
    """Remove a Player Character from the party."""
    data = get_party_tracker()
    
    if character_name not in data["partyMembers"]:
        info(f"PC '{character_name}' is not in the party.")
        return True
        
    data["partyMembers"].remove(character_name)
    
    # Update active character if necessary
    if data.get("active_character") == character_name:
        data["active_character"] = data["partyMembers"][0] if data["partyMembers"] else ""
        
    success = save_party_tracker(data)
    if success:
        info(f"Successfully removed PC '{character_name}' from the party.")
    return success

def set_active_pc(character_name: str) -> bool:
    """Set the currently active PC for input context."""
    data = get_party_tracker()
    
    if character_name not in data["partyMembers"]:
        error(f"Cannot set active character to '{character_name}': Not a party member.")
        return False
        
    data["active_character"] = character_name
    success = save_party_tracker(data)
    if success:
        debug(f"Active character set to '{character_name}'.")
    return success

def get_active_pc() -> str:
    """Get the currently active PC name."""
    data = get_party_tracker()
    return data.get("active_character", "")

def sync_pc_list(character_names: List[str]) -> bool:
    """Sync the partyMembers list with a provided list of names."""
    data = get_party_tracker()
    data["partyMembers"] = character_names
    
    # Validate active character
    if data.get("active_character") not in character_names:
        data["active_character"] = character_names[0] if character_names else ""
        
    return save_party_tracker(data)

def get_entrance_prompt(character_name: str, character_data: Dict[str, Any], party_tracker: Dict[str, Any]) -> str:
    """
    Build a rich prompt for the LLM to narrate a character's entrance.
    """
    prompt_file = "prompts/tabletop/entrance_narration.txt"
    if not os.path.exists(prompt_file):
        return f"[SYSTEM] A new hero named '{character_name}' has joined the party. Please narrate their dramatic entrance."

    with open(prompt_file, 'r', encoding='utf-8') as f:
        template = f.read()

    # Get recent summary if available
    recent_summary = "The adventure continues..."
    try:
        summary_file = "modules/conversation_history/conversation_history.json"
        if os.path.exists(summary_file):
            history = safe_read_json(summary_file)
            if history:
                # Look for last summary or just take last few messages
                for msg in reversed(history):
                    if "=== LOCATION SUMMARY ===" in msg.get("content", "") or "=== MODULE SUMMARY ===" in msg.get("content", ""):
                        recent_summary = msg.get("content", "")[:500] + "..."
                        break
    except:
        pass

    world = party_tracker.get("worldConditions", {})
    
    return template.format(
        character_name=character_name,
        race=character_data.get("race", "Unknown"),
        class_name=character_data.get("class", "Unknown"),
        level=character_data.get("level", 1),
        description=character_data.get("personality_traits", character_data.get("description", "A mysterious traveler")),
        location_name=world.get("currentLocation", "the current location"),
        area_name=world.get("currentArea", "the current area"),
        party_members=", ".join(party_tracker.get("partyMembers", [])),
        recent_summary=recent_summary
    )

if __name__ == "__main__":
    # Test script
    test_name = "TestHero"
    print(f"Adding PC: {test_name}")
    add_pc(test_name)
    print(f"Active PC: {get_active_pc()}")
    print(f"Setting active PC: {test_name}")
    set_active_pc(test_name)
    print(f"Removing PC: {test_name}")
    remove_pc(test_name)
