#!/usr/bin/env python3
"""
Integration module for inventory context matcher
Provides functions to enhance player inputs with inventory context before adding to conversation history
"""

from core.ai.inventory_context_matcher_v2 import InventoryContextMatcherV2
from core.ai.srd_reference import SRDContextMatcher
from utils.enhanced_logger import debug, warning

# Global matcher instance to avoid re-initialization
_inventory_matcher = None
_srd_context_matcher = None

def initialize_inventory_matcher():
    """Initialize the global inventory matcher instance"""
    global _inventory_matcher
    if _inventory_matcher is None:
        _inventory_matcher = InventoryContextMatcherV2(similarity_threshold=0.65, max_matches=5)
        debug("Inventory context matcher initialized", category="inventory_matcher")
    return _inventory_matcher


def initialize_srd_context_matcher():
    """Initialize the cached deterministic SRD matcher."""
    global _srd_context_matcher
    if _srd_context_matcher is None:
        _srd_context_matcher = SRDContextMatcher()
        debug("SRD context matcher initialized", category="srd_context")
    return _srd_context_matcher


def build_srd_context(user_input_text, character_data=None, structured_names=None):
    """Build a bounded SRD block for an explicit rule mention, if any."""
    try:
        result = initialize_srd_context_matcher().context_for(
            user_input_text,
            actor_sheet=character_data,
            structured_names=structured_names,
        )
        matches = result.get("matches") or []
        if matches:
            debug(
                "Added SRD context for rule IDs: %s"
                % ", ".join(match["ruleId"] for match in matches),
                category="srd_context",
            )
        return result.get("context") or ""
    except Exception as exc:
        warning("SRD context unavailable: %s" % exc, category="srd_context")
        return ""

def extract_character_inventory(character_data):
    """
    Extract and format inventory from character data, including combat stats
    
    Args:
        character_data: Dictionary containing character information
        
    Returns:
        List of inventory items formatted for the matcher
    """
    if not character_data:
        return []
    
    inventory = []
    equipment = character_data.get('equipment', [])
    
    # Build a lookup for attack/spell data by name
    attacks_lookup = {}
    for attack in character_data.get('attacksAndSpellcasting', []):
        attack_name = attack.get('name', '').lower()
        attacks_lookup[attack_name] = attack
    
    for item in equipment:
        item_name = item.get('item_name', '')
        inventory_item = {
            'name': item_name,
            'type': item.get('item_type', ''),
            'description': item.get('description', ''),
        }
        
        # Add equipped status if present
        if 'equipped' in item:
            inventory_item['equipped'] = item['equipped']
        
        # Look up combat stats from attacksAndSpellcasting section
        item_name_lower = item_name.lower()
        if item_name_lower in attacks_lookup:
            attack_data = attacks_lookup[item_name_lower]
            # Pass through attack data exactly as stored
            if 'attackBonus' in attack_data:
                inventory_item['attackBonus'] = attack_data['attackBonus']
            if 'damageDice' in attack_data:
                inventory_item['damageDice'] = attack_data['damageDice']
            if 'damageBonus' in attack_data:
                inventory_item['damageBonus'] = attack_data['damageBonus']
            if 'damageType' in attack_data:
                inventory_item['damageType'] = attack_data['damageType']
        
        # Pass through any existing fields from the equipment entry
        if 'ac_bonus' in item:
            inventory_item['ac_bonus'] = item['ac_bonus']
        if 'ac_base' in item:
            inventory_item['ac_base'] = item['ac_base']
        if 'dex_limit' in item:
            inventory_item['dex_limit'] = item['dex_limit']
        if 'effect' in item:
            inventory_item['effect'] = item['effect']
        if 'effects' in item:
            inventory_item['effects'] = item['effects']
        if 'range' in item:
            inventory_item['range'] = item['range']
            
        inventory.append(inventory_item)
    
    debug(f"Extracted {len(inventory)} items from character inventory", category="inventory_matcher")
    return inventory

def get_all_party_inventory(party_tracker_data, characters_data):
    """
    Get combined inventory from all party members
    
    Args:
        party_tracker_data: Dictionary with party member names
        characters_data: Dictionary of character name -> character data
        
    Returns:
        Combined inventory list from all party members
    """
    all_inventory = []
    
    if party_tracker_data and characters_data:
        def resolve_character(name):
            if isinstance(name, dict):
                name = name.get("name")
            display = str(name or "").split("(", 1)[0].strip()
            candidates = (
                display,
                display.lower().replace(" ", "_"),
                display.casefold(),
            )
            for candidate in candidates:
                if candidate in characters_data:
                    return candidate, characters_data[candidate]
            normalized = display.casefold().replace(" ", "_")
            for key, value in characters_data.items():
                if str(key).casefold().replace(" ", "_") == normalized:
                    return key, value
            return None, None

        current_members = party_tracker_data.get("partyMembers")
        if not isinstance(current_members, list):
            current_members = party_tracker_data.get("party", [])
        current_npcs = party_tracker_data.get("partyNPCs")
        if not isinstance(current_npcs, list):
            current_npcs = party_tracker_data.get("party_npcs", [])

        seen = set()
        for member_name in list(current_members or []) + list(current_npcs or []):
            key, character = resolve_character(member_name)
            identity = str(key).casefold() if key is not None else None
            if character is None or identity in seen:
                continue
            seen.add(identity)
            all_inventory.extend(extract_character_inventory(character))
    
    return all_inventory

def enhance_player_input_with_inventory(user_input_text, character_data=None, party_tracker_data=None, 
                                       characters_data=None, in_combat=False):
    """
    Enhance player input with inventory context
    
    Args:
        user_input_text: The player's raw input
        character_data: Current player character data (for single character)
        party_tracker_data: Party tracker data (for getting all party members)
        characters_data: Dictionary of all character data
        in_combat: Boolean indicating if currently in combat
        
    Returns:
        Enhanced input string with inventory context appended
    """
    # Initialize matcher if needed
    matcher = initialize_inventory_matcher()
    
    # Determine context
    context = 'combat' if in_combat else 'general'
    
    # Get inventory
    inventory = []
    
    # Try to get party-wide inventory first
    if party_tracker_data and characters_data:
        inventory = get_all_party_inventory(party_tracker_data, characters_data)
    # Fall back to single character inventory
    elif character_data:
        inventory = extract_character_inventory(character_data)
    
    if not inventory:
        debug("No inventory found, returning unmodified input", category="inventory_matcher")
        return user_input_text
    
    # Process the input through the matcher
    try:
        enriched_input = matcher.process_player_text(user_input_text, inventory, context)
        
        # Log if context was added
        if enriched_input != user_input_text:
            debug(f"Added inventory context for: {user_input_text[:50]}...", category="inventory_matcher")
        
        return enriched_input
        
    except Exception as e:
        warning(f"Error enhancing input with inventory: {e}", category="inventory_matcher")
        return user_input_text

def build_enhanced_dm_note(
    dm_note, user_input_text, character_data=None, party_tracker_data=None,
    characters_data=None, in_combat=False, srd_context=None,
):
    """
    Build the complete DM note with inventory-enhanced player input
    
    Args:
        dm_note: The DM note string
        user_input_text: The player's raw input
        character_data: Current player character data (can be None)
        party_tracker_data: Party tracker data (has party member names)
        characters_data: Dictionary of all character data (can be None)
        in_combat: Boolean indicating if currently in combat
        
    Returns:
        Complete string ready to add to conversation history
    """
    # If we don't have character data but have party tracker, load it
    if not character_data and party_tracker_data:
        try:
            # Get the primary character name from party tracker
            party_members = party_tracker_data.get('partyMembers', [])
            if party_members:
                primary_char = party_members[0]
                # Load character data from file
                import json
                from utils.module_path_manager import ModulePathManager
                path_manager = ModulePathManager()
                char_path = path_manager.get_character_path(primary_char)
                
                try:
                    with open(char_path, 'r', encoding='utf-8') as f:
                        character_data = json.load(f)
                    debug(f"Loaded character data for {primary_char}", category="inventory_matcher")
                except:
                    debug(f"Could not load character data from {char_path}", category="inventory_matcher")
        except Exception as e:
            warning(f"Error loading character data: {e}", category="inventory_matcher")
    
    # Enhance the player input
    enriched_input = enhance_player_input_with_inventory(
        user_input_text, 
        character_data, 
        party_tracker_data,
        characters_data,
        in_combat
    )

    # Match only the raw player text. Inventory descriptions can contain rule
    # names and must never create a false authoritative SRD match.
    if srd_context is None:
        srd_context = build_srd_context(user_input_text, character_data)
    if srd_context:
        enriched_input = "%s\n\n%s" % (enriched_input, srd_context)
    
    # Build the final message
    return f"{dm_note} Player: {enriched_input}"


# Integration point for main.py
# Around line 2920, replace:
#   user_input_with_note = f"{dm_note} Player: {user_input_text}"
# 
# With:
#   from inventory_context_integration import build_enhanced_dm_note
#   
#   # Determine if in combat (check for active encounter or combat flag)
#   in_combat = False
#   if party_tracker_data and party_tracker_data.get('encounter_id'):
#       in_combat = True
#   
#   # Build enhanced DM note with inventory context
#   user_input_with_note = build_enhanced_dm_note(
#       dm_note,
#       user_input_text,
#       character_data,
#       party_tracker_data,
#       characters_data,
#       in_combat
#   )
