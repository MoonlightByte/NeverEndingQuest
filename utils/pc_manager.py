#!/usr/bin/env python3
"""
PC Management utility for Tabletop Multiplayer.
Handles Player Character registration, removal, and selection.
Ensures PCs are correctly stored in party_tracker.json separate from NPCs.

TABLETOP MODE: Data Access Abstraction Layer
Provides centralized character data access with dual-check activation
for future database migration path.
"""

import os
from typing import List, Optional, Dict, Any
from utils.file_operations import safe_read_json, safe_write_json
from utils.enhanced_logger import info, error, debug

PARTY_TRACKER_FILE = "party_tracker.json"

# Experience points required for each level (for character creation)
XP_BY_LEVEL = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
    6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
    11: 85000, 12: 100000, 13: 120000, 14: 140000, 15: 165000,
    16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000,
}

# ============================================================================
# DATA ACCESS ABSTRACTION LAYER - TABLETOP MODE
# ============================================================================
#
# Architecture: Plugin-based abstraction for character data access
# 
# DUAL-CHECK ACTIVATION (TABLETOP MODE Standard):
#   1. Check config.MULTIPLAYER_MODE (global toggle)
#   2. Check len(partyMembers) > 1 (runtime activation)
#
# Current Implementation: JSON file-based with centralized access
# Future Implementation: Database backend
#
# Merge Safety:
#   - All logic contained in plugin file
#   - Upstream files can migrate gradually
#   - Fallback to direct file load if abstraction fails
# ============================================================================

# Storage backend configuration
# Future: "database", "redis", "hybrid"
CHARACTER_STORAGE_BACKEND = "json_file"

# Track data access patterns for optimization insights
_character_access_stats = {
    'single_player_calls': 0,
    'multiplayer_calls': 0,
    'errors': 0
}

# Thread lock for stats to prevent race conditions in multi-threaded web server
import threading
_stats_lock = threading.Lock()

# Lock for thread-safe config cache initialization
_cache_lock = threading.Lock()

# Cache MULTIPLAYER_MODE config to avoid repeated imports
_MULTIPLAYER_MODE_CACHE: Optional[bool] = None


def _is_multiplayer_enabled() -> bool:
    """
    Check MULTIPLAYER_MODE from config with caching.
    
    Caches the result after first check to avoid repeated imports.
    Thread-safe implementation using double-checked locking pattern.
    
    Returns:
        True if MULTIPLAYER_MODE is enabled, False otherwise
    """
    global _MULTIPLAYER_MODE_CACHE
    
    # First check without lock (fast path for cached values)
    if _MULTIPLAYER_MODE_CACHE is not None:
        return _MULTIPLAYER_MODE_CACHE
    
    # Need to initialize - acquire lock
    with _cache_lock:
        # Double-check after acquiring lock (another thread may have set it)
        if _MULTIPLAYER_MODE_CACHE is None:
            try:
                from config import MULTIPLAYER_MODE
                _MULTIPLAYER_MODE_CACHE = bool(MULTIPLAYER_MODE)
            except ImportError:
                _MULTIPLAYER_MODE_CACHE = False
    
    return _MULTIPLAYER_MODE_CACHE


def should_use_abstraction_layer(party_tracker_data: Optional[Dict[str, Any]] = None) -> bool:
    """
    DUAL-CHECK: Determine if abstraction layer should be used.
    
    TABLETOP MODE Standard Pattern:
    1. Check MULTIPLAYER_MODE from config.py (global toggle)
    2. Check party size > 1 (runtime activation)
    
    Args:
        party_tracker_data: Optional party tracker (loaded if not provided)
        
    Returns:
        True if both checks pass
    """
    # Check 1: Global feature toggle (cached)
    if not _is_multiplayer_enabled():
        return False
    
    # Check 2: Runtime party size
    if party_tracker_data is None:
        party_tracker_data = get_party_tracker()
    
    party_members = party_tracker_data.get('partyMembers', [])
    return len(party_members) > 1


def _get_character_path(character_name: str) -> str:
    """Resolve character storage location."""
    from utils.module_path_manager import ModulePathManager
    path_manager = ModulePathManager()
    normalized_name = character_name.lower().replace(' ', '_')
    return path_manager.get_character_path(normalized_name)


def get_character_state(character_name: str,
                       fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve character state with automatic mode detection.
    
    TABLETOP MODE:
    - Multi-player: Uses centralized abstraction
    - Single-player: Direct file load (backward compatible)
    
    Future: Will query database in network play mode
    
    Args:
        character_name: Character name
        fields: Optional field filter (None = all)
        
    Returns:
        Character data or None
    """
    # Validate input
    if not _validate_character_name(character_name):
        return None
    
    # DUAL-CHECK: Determine mode
    if not should_use_abstraction_layer():
        # Single-player mode: Direct file load
        # This maintains backward compatibility with upstream
        # NOTE: Code paths intentionally duplicated for clarity.
        # Both single-player and multi-player modes perform the same file I/O,
        # but are kept separate to clearly distinguish behaviors.
        # Performance impact is negligible (<10ms) compared to LLM latency (3-7s).
        with _stats_lock:
            _character_access_stats['single_player_calls'] += 1
        char_path = _get_character_path(character_name)
        data = safe_read_json(char_path)
        
        if data and fields:
            return {k: v for k, v in data.items() if k in fields}
        return data
    
    # Multi-player mode: Centralized access with logging
    with _stats_lock:
        _character_access_stats['multiplayer_calls'] += 1
    
    try:
        char_path = _get_character_path(character_name)
        data = safe_read_json(char_path)
        
        if data is None:
            debug(f"Character not found: {character_name}", 
                  category="character_access")
            return None
        
        debug(f"Character loaded: {character_name}", category="character_access")
        
        if fields:
            return {k: v for k, v in data.items() if k in fields}
        return data
        
    except Exception as e:
        with _stats_lock:
            _character_access_stats['errors'] += 1
        error(f"Failed to load {character_name}: {e}", 
              exception=e, category="character_access")
        return None


def update_character_state(character_name: str,
                          updates: Dict[str, Any]) -> bool:
    """
    Update character state with automatic mode detection.
    
    TABLETOP MODE:
    - Multi-player: Centralized update with logging
    - Single-player: Direct file write
    
    Args:
        character_name: Character to update
        updates: Fields to update
        
    Returns:
        True if successful
    """
    # Validate input
    if not _validate_character_name(character_name):
        return False
    
    if not should_use_abstraction_layer():
        # Single-player: Direct write
        char_path = _get_character_path(character_name)
        existing = safe_read_json(char_path) or {}
        existing.update(updates)
        return safe_write_json(char_path, existing)
    
    # Multi-player: Centralized with validation
    try:
        char_path = _get_character_path(character_name)
        existing = safe_read_json(char_path) or {}
        existing.update(updates)
        
        success = safe_write_json(char_path, existing)
        
        if success:
            debug(f"Character updated: {character_name} - {list(updates.keys())}",
                  category="character_access")
        return success
        
    except Exception as e:
        with _stats_lock:
            _character_access_stats['errors'] += 1
        error(f"Failed to update {character_name}: {e}",
              exception=e, category="character_access")
        return False


def _validate_character_name(character_name: str) -> bool:
    """
    Validate character name parameter.
    
    Args:
        character_name: Name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not character_name:
        error("Invalid character_name: empty or None", category="character_access")
        return False
    if not isinstance(character_name, str):
        error(f"Invalid character_name type: {type(character_name)}", category="character_access")
        return False
    return True


def get_party_character_states(party_tracker_data: Optional[Dict[str, Any]] = None
                              ) -> Dict[str, Dict[str, Any]]:
    """
    Bulk load all party member states.
    
    TABLETOP MODE: Optimized for multi-PC party management
    """
    if party_tracker_data is None:
        party_tracker_data = get_party_tracker()
    
    characters_data = {}
    party_members = party_tracker_data.get('partyMembers', [])
    
    for pc_name in party_members:
        char_data = get_character_state(pc_name)
        if char_data:
            characters_data[pc_name] = char_data
    
    return characters_data


def character_exists(character_name: str) -> bool:
    """Check if character exists."""
    char_path = _get_character_path(character_name)
    return os.path.exists(char_path)


def get_character_field(character_name: str, field_name: str) -> Any:
    """Get single field value."""
    data = get_character_state(character_name, fields=[field_name])
    return data.get(field_name) if data else None


def update_character_field(character_name: str,
                          field_name: str,
                          value: Any) -> bool:
    """Update single field."""
    return update_character_state(character_name, {field_name: value})


def get_character_access_stats() -> Dict[str, int]:
    """Get abstraction layer adoption stats."""
    return _character_access_stats.copy()


# DATABASE MIGRATION TODO:
# To migrate to database backend:
# 1. Update CHARACTER_STORAGE_BACKEND constant
# 2. Implement _get_character_path() to return DB query instead of file path
# 3. Update get_character_state() to use SQL/Mongo query
# 4. Update update_character_state() to use UPDATE operation
# 5. Add connection pooling and transaction management
# 6. Implement proper indexing for character_name lookups
# ============================================================================

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

def get_character_creation_prompt(
    module_name: str,
    character_name: str,
    party_tracker: Dict[str, Any],
    level: int = 1,
    is_mid_campaign: bool = False,
    active_pc: str = "",
    current_location: str = "",
) -> str:
    """
    Load and format the enhanced character creation prompt for web DM interview.
    
    Args:
        module_name: Current module/campaign name
        character_name: Name of the character being created
        party_tracker: Party tracker data for context
        level: Character level (default 1)
        is_mid_campaign: Whether this is mid-campaign (affects equipment/XP)
        active_pc: Currently active PC who will set the scene
        current_location: Current location for context
        
    Returns:
        Formatted prompt string with context
    """
    # Local wealth guidance function to avoid circular imports
    def get_wealth_guidance_text_local(target_level: int) -> str:
        if target_level <= 2:
            return "STARTING EQUIPMENT: Use standard class starting equipment plus background gear. No additional gold."
        elif target_level <= 4:
            gp = {3: 150, 4: 375}.get(target_level, 150)
            return f"STARTING EQUIPMENT: Standard gear plus {gp}gp for additional equipment."
        elif target_level <= 7:
            gp = {5: 650, 6: 900, 7: 1200}.get(target_level, 650)
            return f"STARTING EQUIPMENT: Standard gear plus {gp}gp. Consider uncommon magic items."
        elif target_level <= 10:
            gp = {8: 1650, 9: 2250, 10: 3000}.get(target_level, 1650)
            return f"STARTING EQUIPMENT: Standard gear plus {gp}gp. Should have rare magic items (2-3)."
        elif target_level <= 14:
            gp = {11: 4000, 12: 5250, 13: 6750, 14: 8750}.get(target_level, 4000)
            return f"STARTING EQUIPMENT: Standard gear plus {gp}gp. Should have very rare items (3-4)."
        else:
            gp = {15: 11250, 16: 14500, 17: 18750, 18: 24250, 19: 31250, 20: 40000}.get(target_level, 11250)
            return f"STARTING EQUIPMENT: Standard gear plus {gp}gp. Should have legendary items (4-5)."
    
    prompt_file = "prompts/character_creation/dm_interview_prompt.txt"
    
    # Fallback if prompt file doesn't exist
    if not os.path.exists(prompt_file):
        return (
            f"[SYSTEM] A new player '{character_name}' is joining the table at Level {level}! "
            f"Please guide them through 5e character creation. "
            f"Ask for Race, Class, Background, Ability Scores, Skills, Equipment, and Personality. "
            f"When complete, output the full character as JSON."
        )
    
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            template = f.read()
    except Exception as e:
        error(f"Failed to load character creation prompt: {e}")
        return (
            f"[SYSTEM] A new player '{character_name}' is joining the table at Level {level}! "
            f"Please guide them through 5e character creation."
        )
    
    # Get context from party tracker
    world = party_tracker.get("worldConditions", {})
    party_members = party_tracker.get("partyMembers", [])
    
    # Filter out the new character from party list (they haven't joined yet)
    existing_members = [m for m in party_members if m.lower().replace(' ', '_') != character_name.lower().replace(' ', '_')]
    
    # Get recent summary for context
    recent_summary = "The adventure continues..."
    try:
        summary_file = "modules/conversation_history/conversation_history.json"
        if os.path.exists(summary_file):
            history = safe_read_json(summary_file)
            if history and isinstance(history, list):
                for msg in reversed(history):
                    # Ensure msg is a dict before calling .get()
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        if "=== LOCATION SUMMARY ===" in content or "=== MODULE SUMMARY ===" in content:
                            recent_summary = content[:500] + "..." if len(content) > 500 else content
                            break
    except Exception:
        pass
    
    # Build level-specific context
    xp_for_level = XP_BY_LEVEL.get(level, 0)
    xp_next = XP_BY_LEVEL.get(level + 1, XP_BY_LEVEL[20]) if level < 20 else 0
    
    level_context = f"""
CHARACTER LEVEL: {level}
EXPERIENCE POINTS: {xp_for_level} (minimum for level {level})
EXPERIENCE FOR NEXT LEVEL: {xp_next}
"""
    
    # Add equipment guidance for levels above 1
    equipment_guidance = ""
    if is_mid_campaign and level > 1:
        equipment_guidance = get_wealth_guidance_text_local(level)
        level_context += f"\n{equipment_guidance}"
    
    # Add mid-campaign specific instructions
    mid_campaign_context = ""
    if is_mid_campaign:
        mid_campaign_context = f"""
MID-CAMPAIGN ADDITION:
This character is joining an ongoing adventure. The party currently consists of: {', '.join(existing_members) if existing_members else 'no one yet'}.

{active_pc} is currently the active party member at {current_location or world.get('currentLocation', 'the current location')}.

CONNECTION OPPORTUNITY:
During creation, ask if {character_name} recognizes any existing party members from their past (friend, rival, former comrade, etc.) or if they are a complete stranger. This will be woven into their entrance narrative.

IMPORTANT: This character is NOT exhausted, injured, or debilitated. They are fresh and ready for adventure at full capacity.
"""
    
    # Format the prompt
    try:
        formatted_prompt = template.format(
            character_name=character_name,
            module_name=module_name,
            location_name=current_location or world.get("currentLocation", "the current location"),
            area_name=world.get("currentArea", "the current area"),
            party_members=", ".join(existing_members) if existing_members else "none yet",
            level=level,
            recent_summary=recent_summary,
            level_context=level_context,
            mid_campaign_context=mid_campaign_context,
            active_pc=active_pc or "The party",
        )
        return formatted_prompt
    except Exception as e:
        error(f"Failed to format character creation prompt: {e}")
        # Return unformatted template as fallback
        return template

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
