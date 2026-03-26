# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Multi-PC DM Note Builder - Tabletop Mode Plugin
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.

Multi-PC DM Note enhancement for tabletop mode with [>] Active PC marker,
section-based organization, and notable items filtering.
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path

from utils.enhanced_logger import debug, info, warning
from utils.encoding_utils import safe_json_load
from utils.module_path_manager import ModulePathManager
from utils.pc_manager import should_use_abstraction_layer
from utils.authoritative_state_packet import build_authoritative_state_packet


def _normalize_display_location_name(location_name: str) -> str:
    """Strip legacy room-number prefixes from user-facing location names."""
    if not isinstance(location_name, str):
        return ""
    return location_name.split(": ", 1)[1] if location_name.lower().startswith("room ") and ": " in location_name else location_name


def should_use_multi_pc_dm_note(party_tracker_data: Optional[Dict[str, Any]]) -> bool:
    """
    Determine if multi-PC DM Note format should be used.
    
    Delegates to centralized abstraction layer check for consistency.
    
    Args:
        party_tracker_data: The party tracker data dict
        
    Returns:
        True if MULTIPLAYER_MODE is enabled AND party has more than 1 member
    """
    return should_use_abstraction_layer(party_tracker_data)


def get_notable_items(pc_data: Dict[str, Any]) -> List[str]:
    """
    Extract notable items from PC inventory for concise display.
    
    Notable items include:
    - Quest items (tagged or name contains 'quest')
    - Magic items (has magical properties or rarity)
    - Consumables (potions, scrolls, etc.)
    - Valuable items (>50gp)
    
    Args:
        pc_data: Character data dict with inventory
        
    Returns:
        List of notable item descriptions
    """
    notable_items = []
    inventory_items = []

    inventory = pc_data.get('inventory', {})
    if isinstance(inventory, dict):
        nested_items = inventory.get('items', [])
        if isinstance(nested_items, list):
            inventory_items.extend(nested_items)

    equipment = pc_data.get('equipment', [])
    if isinstance(equipment, list):
        inventory_items.extend(equipment)

    ammunition = pc_data.get('ammunition', [])
    if isinstance(ammunition, list):
        for ammo in ammunition:
            if not isinstance(ammo, dict):
                continue
            ammo_copy = dict(ammo)
            ammo_copy.setdefault('item_type', 'ammunition')
            inventory_items.append(ammo_copy)

    if not inventory_items:
        return notable_items

    items = inventory_items
    
    for item in items:
        if not isinstance(item, dict):
            continue
            
        item_name = str(item.get('item_name') or item.get('name') or '')
        quantity = item.get('quantity', 1)
        
        # Check for quest items
        if item.get('isQuestItem') or 'quest' in item_name.lower():
            notable_items.append(f"{item_name} (Quest)")
            continue
        
        # Check for magic items
        if item.get('magical') or item.get('rarity') in ['uncommon', 'rare', 'very rare', 'legendary']:
            notable_items.append(f"{item_name} (Magic)")
            continue
        
        # Check for consumables
        item_type = str(item.get('type') or item.get('item_type') or '').lower()
        if item_type in ['potion', 'scroll', 'consumable']:
            notable_items.append(f"{item_name} x{quantity}")
            continue
        
        # Check for valuable items (>50gp)
        value = item.get('value', 0)
        if value > 50:
            notable_items.append(f"{item_name} ({value}gp)")
            continue
    
    return notable_items


def _summarize_limited_resources(pc_data: Dict[str, Any], limit: int = 3) -> List[str]:
    """Return compact class feature usage summary for limited-use features."""
    summaries: List[str] = []
    class_features = pc_data.get('classFeatures', [])
    if not isinstance(class_features, list):
        return summaries

    for feature in class_features:
        if not isinstance(feature, dict):
            continue
        feature_name = str(feature.get('name') or '').strip()
        if not feature_name:
            continue

        usage = feature.get('usage')
        current = None
        maximum = None
        if isinstance(usage, dict):
            current = usage.get('current')
            maximum = usage.get('max')
        else:
            if feature.get('currentUses') is not None:
                current = feature.get('currentUses')
            elif feature.get('uses') is not None:
                current = feature.get('uses')
            if feature.get('maxUses') is not None:
                maximum = feature.get('maxUses')

        if current is None and maximum is None:
            continue

        if maximum is None:
            summaries.append(f"{feature_name}:{current}")
        else:
            summaries.append(f"{feature_name}:{current}/{maximum}")

        if len(summaries) >= limit:
            break

    return summaries


def format_pc_full_stats(pc_data: Dict[str, Any], pc_name: str, is_active: bool = False) -> str:
    """
    Format full character stats block for Active PC.
    
    Args:
        pc_data: Full character data dict
        pc_name: Character name
        is_active: Whether this is the Active PC (adds [>] marker)
        
    Returns:
        Formatted stats string
    """
    parts = []
    
    # Header with marker if active
    level = pc_data.get('level', '?')
    class_name = pc_data.get('class', 'Unknown')
    
    if is_active:
        parts.append(f"[>] {pc_name} (Level {level} {class_name}) [ACTIVE PC]")
    else:
        parts.append(f"{pc_name} (Level {level} {class_name})")
    
    # HP and AC (with HP truth enforcement marker)
    current_hp = pc_data.get('hitPoints', 0)
    max_hp = pc_data.get('maxHitPoints', current_hp)
    ac = pc_data.get('armorClass', 10)
    
    hp_status = f"HP {current_hp}/{max_hp} [SOURCE: DM Note]"
    if current_hp <= max_hp * 0.25 and current_hp > 0:
        hp_status += " [LOW HEALTH]"
    elif current_hp == 0:
        hp_status += " [UNCONSCIOUS]"
    
    parts.append(f"  {hp_status}, AC {ac}")
    
    # Conditions (5e mechanical conditions from condition_affected)
    condition_affected = pc_data.get('condition_affected', [])
    if condition_affected:
        # Filter to actual condition strings
        conditions = [c for c in condition_affected if isinstance(c, str)]
        if conditions:
            parts.append(f"  Conditions: {', '.join(conditions)}")
    else:
        parts.append("  Conditions: None")
    
    # Ability scores (abbreviated)
    abilities = pc_data.get('abilityScores', {})
    if abilities:
        ability_strs = []
        for abbr, full_name in [('STR', 'strength'), ('DEX', 'dexterity'), ('CON', 'constitution'),
                                 ('INT', 'intelligence'), ('WIS', 'wisdom'), ('CHA', 'charisma')]:
            score = abilities.get(full_name, 10)
            mod = (score - 10) // 2
            mod_str = f"+{mod}" if mod >= 0 else f"{mod}"
            ability_strs.append(f"{abbr}:{score}({mod_str})")
        parts.append(f"  Abilities: {', '.join(ability_strs)}")
    
    # Spell slots (if applicable)
    spellcasting = pc_data.get('spellcasting', {})
    if spellcasting and 'spellSlots' in spellcasting:
        slots = spellcasting['spellSlots']
        slot_parts = []
        for level in range(1, 10):
            level_key = f'level{level}'
            if level_key in slots:
                slot_data = slots[level_key]
                current = slot_data.get('current', 0)
                maximum = slot_data.get('max', 0)
                if maximum > 0:
                    slot_parts.append(f"L{level}:{current}/{maximum}")
        if slot_parts:
            parts.append(f"  Spell Slots: {' '.join(slot_parts)}")
        
        # Concentration check
        conditions = pc_data.get('conditions', [])
        if 'concentrating' in conditions:
            parts.append("  [CONCENTRATING]")
    
    # XP
    xp = pc_data.get('xp', 0)
    next_level_xp = pc_data.get('nextLevelXP', '-')
    parts.append(f"  XP: {xp}/{next_level_xp}")
    
    # Full inventory for Active PC
    if is_active:
        inventory_count = 0
        inventory = pc_data.get('inventory', {})
        if isinstance(inventory, dict):
            nested_items = inventory.get('items', [])
            if isinstance(nested_items, list):
                inventory_count += len(nested_items)

        equipment = pc_data.get('equipment', [])
        if isinstance(equipment, list):
            inventory_count += len(equipment)

        ammunition = pc_data.get('ammunition', [])
        if isinstance(ammunition, list):
            inventory_count += len(ammunition)

        if inventory_count > 0:
            parts.append(f"  Inventory: {inventory_count} entries")
            notable = get_notable_items(pc_data)
            if notable:
                parts.append(f"    Notable: {', '.join(notable[:5])}")

        limited_resources = _summarize_limited_resources(pc_data, limit=4)
        if limited_resources:
            parts.append(f"  Resources: {', '.join(limited_resources)}")
        
        # Backstory (bounded for DM note context)
        backstory = pc_data.get('backstory', '')
        if backstory:
            # Truncate to first sentence or ~80 chars
            first_sentence = backstory.split('.')[0].strip()
            if first_sentence:
                display = first_sentence[:80] + ('...' if len(first_sentence) > 80 else '')
                parts.append(f"  Story: {display}")
    
    return '\n'.join(parts)


def format_pc_condensed(pc_data: Dict[str, Any], pc_name: str) -> str:
    """
    Format condensed character stats for non-Active PCs.
    Shows only essential info + notable items.
    
    Args:
        pc_data: Character data dict
        pc_name: Character name
        
    Returns:
        Condensed stats string
    """
    parts = []
    
    # Basic info
    level = pc_data.get('level', '?')
    class_name = pc_data.get('class', 'Unknown')
    
    # HP status
    current_hp = pc_data.get('hitPoints', 0)
    max_hp = pc_data.get('maxHitPoints', current_hp)
    ac = pc_data.get('armorClass', 10)
    
    hp_indicator = ""
    if current_hp <= max_hp * 0.25 and current_hp > 0:
        hp_indicator = " [LOW HP]"
    elif current_hp == 0:
        hp_indicator = " [DOWN]"
    
    parts.append(f"{pc_name} (Lv{level} {class_name}) - HP {current_hp}/{max_hp}{hp_indicator}, AC {ac}")
    
    # Conditions (concise display)
    condition_affected = pc_data.get('condition_affected', [])
    if condition_affected:
        conditions = [c for c in condition_affected if isinstance(c, str)]
        if conditions:
            parts.append(f"  Cond: {', '.join(conditions)}")
    
    # Backstory snippet (concise)
    backstory = pc_data.get('backstory', '')
    if backstory:
        first_sentence = backstory.split('.')[0].strip()
        if first_sentence:
            display = first_sentence[:60] + ('...' if len(first_sentence) > 60 else '')
            parts.append(f"  Story: {display}")
    
    # Notable items only
    notable = get_notable_items(pc_data)
    if notable:
        parts.append(f"  Items: {', '.join(notable[:3])}")

    limited_resources = _summarize_limited_resources(pc_data, limit=2)
    if limited_resources:
        parts.append(f"  Res: {', '.join(limited_resources)}")
    
    return '\n'.join(parts)


def format_party_npcs(party_npcs: List[Dict[str, Any]]) -> str:
    """
    Format party NPC list.
    
    Args:
        party_npcs: List of party NPC dicts
        
    Returns:
        Formatted NPC list string
    """
    if not party_npcs:
        return "None"
    
    formatted = []
    for npc in party_npcs:
        name = npc.get('name', 'Unknown')
        role = npc.get('role', 'Ally')
        level = npc.get('level', '?')
        formatted.append(f"{name} (Lv{level} {role})")
    
    return '; '.join(formatted)


def load_party_character_data(party_tracker_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Load all party member character data from files.
    
    Args:
        party_tracker_data: Party tracker with partyMembers list
        
    Returns:
        Dict mapping character names to their full data
    """
    characters_data = {}
    party_members = party_tracker_data.get('partyMembers', [])
    
    if not party_members:
        return characters_data
    
    module_name = party_tracker_data.get('module', '').replace(' ', '_')
    path_manager = ModulePathManager(module_name)
    
    for pc_name in party_members:
        try:
            # TABLETOP MODE: Use centralized character access when available
            import utils.pc_manager as pc_manager
            if pc_manager.should_use_abstraction_layer(party_tracker_data):
                char_data = pc_manager.get_character_state(pc_name)
                if char_data:
                    characters_data[pc_name] = char_data
                    debug(f"Loaded character data for {pc_name}", category="multi_pc_dm_note")
                else:
                    warning(f"Character data not found for {pc_name}", category="multi_pc_dm_note")
            else:
                # Legacy direct file loading
                normalized_name = pc_name.lower().replace(' ', '_')
                char_path = path_manager.get_character_path(normalized_name)
                
                if Path(char_path).exists():
                    char_data = safe_json_load(char_path)
                    if char_data:
                        characters_data[pc_name] = char_data
                        debug(f"Loaded character data for {pc_name}", category="multi_pc_dm_note")
                else:
                    warning(f"Character file not found for {pc_name}: {char_path}", category="multi_pc_dm_note")
        except Exception as e:
            warning(f"Error loading character data for {pc_name}: {e}", category="multi_pc_dm_note")
    
    return characters_data


def build_multi_pc_dm_note(
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]],
    world_conditions: Dict[str, Any],
    date_time_str: str,
    current_season: str,
    current_module_name: str,
    current_location_name: str,
    current_location_id: str,
    current_area_name: str,
    plot_points_str: str,
    side_quests_str: str,
    monsters_str: str,
    traps_str: str,
    connected_locations_str: str,
    module_creation_prompt: str = "",
    should_inject_creation_prompt: bool = False
) -> str:
    """
    Build enhanced DM Note for multi-PC tabletop mode.
    
    Features:
    - [>] marker for Active PC
    - Section-based organization
    - Full stats for Active PC, condensed for others
    - Notable items filtering for non-Active PCs
    - Third-person perspective guidance
    
    Args:
        party_tracker_data: Party state with partyMembers and active_character
        location_data: Current location data
        world_conditions: World state dict
        date_time_str: Current date/time string
        current_season: Current season
        current_module_name: Current module name
        current_location_name: Current location name
        current_location_id: Current location ID
        current_area_name: Current area name
        plot_points_str: Formatted plot points
        side_quests_str: Formatted side quests
        monsters_str: Formatted monster list
        traps_str: Formatted trap list
        connected_locations_str: Connected locations display string
        module_creation_prompt: Module creation prompt text (if active)
        should_inject_creation_prompt: Whether module creation mode is active
        
    Returns:
        Complete DM Note string with multi-PC enhancements
    """
    # TABLETOP MODE: Build authoritative packet so DM Note and validator use
    # the same overlapping location/party/party-NPC truth surface.
    authoritative_state_packet = build_authoritative_state_packet(party_tracker_data)
    packet_world = authoritative_state_packet.get("world", {})
    packet_party = authoritative_state_packet.get("party", {})
    packet_module = authoritative_state_packet.get("module", {})

    # Get party composition from packet truth first.
    party_members = packet_party.get("party_members", [])
    if not isinstance(party_members, list) or not party_members:
        party_members = party_tracker_data.get('partyMembers', [])

    active_pc = packet_party.get("active_character") or party_tracker_data.get('active_character')
    
    # Load all character data
    characters_data = load_party_character_data(party_tracker_data)
    
    # Identify Active PC (fallback to first party member if not set)
    if not active_pc and party_members:
        active_pc = party_members[0]
    
    # Get party NPCs
    party_npcs = packet_party.get("party_npcs", [])
    if not isinstance(party_npcs, list):
        party_npcs = party_tracker_data.get('partyNPCs', [])
    party_npcs_str = format_party_npcs(party_npcs)

    effective_module_name = packet_module.get("name") or current_module_name
    effective_location_name = _normalize_display_location_name(packet_world.get("current_location_name") or current_location_name)
    effective_location_id = packet_world.get("current_location_id") or current_location_id
    effective_area_name = packet_world.get("current_area_name") or current_area_name
    
    # Start building DM Note
    dm_note_parts = []
    
    # --- WORLD STATE SECTION ---
    dm_note_parts.append("--- WORLD STATE ---")
    dm_note_parts.append(f"Current date and time: {date_time_str}, {current_season} season")
    dm_note_parts.append(f"Current module: {effective_module_name}")
    dm_note_parts.append(f"Current location: {effective_location_name} ({effective_location_id}) in the {effective_area_name} area")
    dm_note_parts.append(f"Adjacent locations: {connected_locations_str}")
    dm_note_parts.append("")  # Blank line
    
    # --- MECHANICAL STATE SECTION ---
    dm_note_parts.append("=== MECHANICAL STATE [CURRENT TURN] ===")
    dm_note_parts.append("NARRATIVE MEMORY MAY BE STALE - USE THESE VALUES AS TRUTH:")
    for pc_name in party_members:
        if pc_name in characters_data:
            pc_data = characters_data[pc_name]
            hp = pc_data.get('hitPoints', 0)
            max_hp = pc_data.get('maxHitPoints', 1)
            conditions = pc_data.get('condition_affected', [])
            if hp == 0:
                status = "UNCONSCIOUS [HP=0]"
            else:
                status = "CONSCIOUS"
            if conditions:
                status += f" | Conditions: {', '.join(str(c) for c in conditions if isinstance(c, str))}"
            else:
                status += " | No conditions"
            dm_note_parts.append(f"  {pc_name}: {status} | HP {hp}/{max_hp}")
        else:
            dm_note_parts.append(f"  {pc_name}: [DATA UNAVAILABLE]")
    dm_note_parts.append("RULE: If narrative memory contradicts above, ABOVE WINS. HP>0 = conscious and able to act.")
    dm_note_parts.append("")
    
    # --- ACTIVE PC SECTION ---
    dm_note_parts.append("--- ACTIVE PC [>] ---")
    dm_note_parts.append("NARRATIVE GUIDANCE: Address this PC by name in THIRD PERSON for current input")
    dm_note_parts.append("")
    
    if active_pc and active_pc in characters_data:
        active_data = characters_data[active_pc]
        dm_note_parts.append(format_pc_full_stats(active_data, active_pc, is_active=True))
    else:
        dm_note_parts.append(f"[>] {active_pc} [ACTIVE PC - data unavailable]")
    
    dm_note_parts.append("")
    
    # --- PARTY MEMBERS SECTION ---
    other_members = [m for m in party_members if m != active_pc]
    
    if other_members:
        dm_note_parts.append("--- PARTY MEMBERS ---")
        dm_note_parts.append("These PCs are present; track their positions and actions:")
        dm_note_parts.append("")
        
        for pc_name in other_members:
            if pc_name in characters_data:
                pc_data = characters_data[pc_name]
                dm_note_parts.append(format_pc_condensed(pc_data, pc_name))
            else:
                dm_note_parts.append(f"{pc_name} (data unavailable)")
            dm_note_parts.append("")
    
    # --- PARTY NPCs SECTION ---
    if party_npcs:
        dm_note_parts.append("--- PARTY NPCs (DM CONTROLLED) ---")
        dm_note_parts.append(party_npcs_str)
        dm_note_parts.append("")
    
    # --- PLOT & QUESTS SECTION ---
    if not should_inject_creation_prompt:
        dm_note_parts.append("--- PLOT & QUESTS ---")
        if plot_points_str and plot_points_str != "None":
            dm_note_parts.append(f"Active plot points:\n{plot_points_str}")
        if side_quests_str and side_quests_str != "None":
            dm_note_parts.append(f"Active side quests:\n{side_quests_str}")
        dm_note_parts.append("")
    
    # --- LOCATION CONTEXT SECTION ---
    dm_note_parts.append("--- LOCATION CONTEXT ---")
    if monsters_str and monsters_str != "None":
        dm_note_parts.append(f"Monsters:\n{monsters_str}")
    if traps_str and traps_str != "None":
        dm_note_parts.append(f"Traps:\n{traps_str}")
    
    # Check if current location has been peacefully resolved
    world_conditions = party_tracker_data.get("worldConditions", {})
    resolved_map = world_conditions.get("resolvedHostilesByLocation", {})
    is_resolved_here = resolved_map.get(effective_location_id, False) if isinstance(resolved_map, dict) else False
    
    if is_resolved_here:
        dm_note_parts.append("Resolved Hostile State: Hostile guardian at this location has been appeased. Do not re-initiate this threat unless the party provokes it.")
    else:
        dm_note_parts.append("Monsters should be active threats per engagement rules.")
    dm_note_parts.append("")
    
    # --- NARRATIVE RULES ---
    dm_note_parts.append("--- NARRATIVE RULES ---")
    dm_note_parts.append(
        "NARRATIVE GUIDANCE: "
        "- Address the Active PC [>] by name in THIRD PERSON ('Valor looks around...') "
        "- Track all party members; weave brief mentions of others when relevant "
        "- If player declares action for non-Active PC, acknowledge intent but clarify which PC acts "
        "- Always specify 'PC_NAME expends resource', never generic ('uses a slot') "
        "- When switching Active PC, seamlessly transition narrative perspective "
        "- HP values shown are AUTHORITATIVE from character sheets; NEVER hallucinate different HP "
        "- Long rest (8+ hours, uninterrupted): Restore ALL HP, spell slots, class features per 5e rules"
    )
    
    if module_creation_prompt:
        dm_note_parts.append(module_creation_prompt)
    
    return '\n'.join(dm_note_parts)


def build_standard_dm_note(
    party_tracker_data: Dict[str, Any],
    world_conditions: Dict[str, Any],
    date_time_str: str,
    current_season: str,
    current_module_name: str,
    current_location_name: str,
    current_location_id: str,
    current_area_name: str,
    party_stats_str: str,
    party_npcs_str: str,
    plot_points_str: str,
    side_quests_str: str,
    monsters_str: str,
    traps_str: str,
    connected_locations_str: str,
    module_creation_prompt: str = "",
    should_inject_creation_prompt: bool = False
) -> str:
    """
    Build standard single-PC DM Note (backward compatible).
    
    This is the original DM Note format for single-PC mode,
    preserved for backward compatibility and upstream compatibility.
    
    Args:
        Same as build_multi_pc_dm_note except party_stats_str and party_npcs_str
        are pre-formatted strings (original upstream format)
        
    Returns:
        Standard DM Note string
    """
    party_members = party_tracker_data.get('partyMembers', [])
    party_members_str = ", ".join(party_members) if party_members else "None"
    
    # Check if current location has been peacefully resolved
    world_conditions = party_tracker_data.get("worldConditions", {})
    resolved_map = world_conditions.get("resolvedHostilesByLocation", {})
    is_resolved_here = resolved_map.get(current_location_id, False) if isinstance(resolved_map, dict) else False
    
    threat_guidance = (
        "Resolved Hostile State: Hostile guardian at this location has been appeased. Do not re-initiate this threat unless the party provokes it. "
        if is_resolved_here else
        "Monsters should be active threats per engagement rules. "
    )
    
    if should_inject_creation_prompt:
        # Simplified DM note for module creation - no confusing plot/quest info
        dm_note = (
            f"Dungeon Master Note: Current date and time: {date_time_str}, {current_season} season. "
            f"Current module: {current_module_name}. "
            f"Current location: {current_location_name} ({current_location_id}) in the {current_area_name} area. "
            f"Active Player Characters (User Controlled): {party_members_str}. "
            f"Accompanied by Party NPCs (DM Controlled): {party_npcs_str}. "
            f"Party stats: {party_stats_str}. "
            f"Adjacent locations in this area: {connected_locations_str}.\n"
        )
    else:
        # Normal DM note with all plot/quest/monster info
        dm_note = (
            f"Dungeon Master Note: Current date and time: {date_time_str}, {current_season} season. "
            f"Current module: {current_module_name}. "
            f"Current location: {current_location_name} ({current_location_id}) in the {current_area_name} area. "
            f"Active Player Characters (User Controlled): {party_members_str}. "
            f"Accompanied by Party NPCs (DM Controlled): {party_npcs_str}. "
            f"Party stats: {party_stats_str}. "
            f"Adjacent locations in this area: {connected_locations_str}.\n"
            f"Active plot points for this location:\n{plot_points_str}\n"
            f"Active side quests for this location:\n{side_quests_str}\n"
            f"Monsters in this location:\n{monsters_str}\n"
            f"Traps in this location:\n{traps_str}\n"
            f"{threat_guidance}"
        )
    
    # Add common instructions
    dm_note += (
        "updateCharacterInfo for player and NPC character changes (inventory, stats, abilities), "
        "updateTime for time passage, "
        "updatePlot for story progression, discovers, and new information, "
        "updatePartyNPCs for party composition changes to the party tracker, "
        "levelUp for advancement, "
        "transitionLocation should always be used when the player expresses a desire to move to a new location, "
        "Always roleplay the NPC and NPC party rolls without asking the player. "
        "Always ask the player character to roll for skill checks and other actions. "
        "Proactively narrate location NPCs, start conversations, and weave plot elements into the adventure. "
        "Use party NPCs to narrate if possible instead of always narrating from the DM's perspective, but don't overdo it. "
        "Maintain immersive and engaging storytelling similar to an adventure novel while accurately managing game mechanics. "
        "Update all relevant information immediately and confirm with the player before major actions. "
        "Consider whether the party's action trigger traps in this location. "
        "Consider updating the plot elements on every action the player and NPCs take."
    )
    
    if module_creation_prompt:
        dm_note += module_creation_prompt
    
    return dm_note
