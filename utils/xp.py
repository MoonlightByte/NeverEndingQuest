# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

import json
import os
from .module_path_manager import ModulePathManager

# CR to XP mapping (updated to include fractional CRs)
cr_to_xp = {
    0: 10, 0.125: 25, 0.25: 50, 0.5: 100, 1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
    6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900, 11: 7200, 12: 8400, 13: 10000,
    14: 11500, 15: 13000, 16: 15000, 17: 18000, 18: 20000, 19: 22000, 20: 25000,
    21: 33000, 22: 41000, 23: 50000, 24: 62000, 25: 75000, 26: 90000, 27: 105000,
    28: 120000, 29: 135000, 30: 155000
}

def load_json_file(filename):
    with open(filename, 'r') as file:
        return json.load(file)

def get_xp_for_cr(cr):
    if isinstance(cr, str):
        if '/' in cr:
            numerator, denominator = map(int, cr.split('/'))
            cr = numerator / denominator
        else:
            cr = float(cr)
    return cr_to_xp.get(cr, 0)  # Return 0 if CR not found in the dictionary

def is_defeated(status):
    return status.lower() in ['dead', 'defeated', 'unconscious']

def _left_by_resolution(creature):
    """A typed flee or yield (resolver, #466). The sheet keeps its own status,
    so a sync can put the encounter status back; the resolution stays."""
    return creature.get('resolution') in ('fled', 'yielded')

def _hostile_person_sheet(creature, encounter, path_manager):
    """The sheet of a person on the hostile side (#1470): the scene row's
    sourceRef when it names a sheet, else the character path for the name.
    None for a pending observer (no sheet) or a missing file."""
    if creature.get('statsPending'):
        return None
    paths = []
    for row in (encounter.get('sceneFacts') or {}).get('participants') or []:
        if (isinstance(row, dict) and row.get('combatantId') == creature.get('combatantId')
                and row.get('sourceKind') == 'character' and isinstance(row.get('sourceRef'), str)):
            paths.append(row['sourceRef'])
    paths.append(path_manager.get_character_path(creature['name']))
    for path in paths:
        if os.path.exists(path):
            return load_json_file(path)
    return None

def calculate_xp(encounter, party_tracker):
    total_xp = 0
    defeated_count = 0
    monster_cache = {}
    xp_breakdown = []
    # Get current module from party tracker for consistent path resolution
    current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
    path_manager = ModulePathManager(current_module)

    for creature in encounter['creatures']:
        if creature['type'] == 'enemy' and is_defeated(creature['status']):
            defeated_count += 1
            monster_type = creature['monsterType'].lower()
            if monster_type not in monster_cache:
                monster_file = path_manager.get_monster_path(monster_type)
                if os.path.exists(monster_file):
                    monster = load_json_file(monster_file)
                    monster_cache[monster_type] = monster
                else:
                    print(f"Warning: Monster file {monster_file} not found.")
                    continue
            
            monster = monster_cache[monster_type]
            cr = monster['challengeRating']
            xp = get_xp_for_cr(cr)
            total_xp += xp
            xp_breakdown.append((monster['name'], cr, xp))
        elif (creature['type'] == 'npc' and creature.get('faction') == 'hostile'
              and (is_defeated(str(creature.get('status') or '')) or _left_by_resolution(creature))):
            # #1470: a person on the hostile side pays like a monster (owner
            # ruling on #1403), a yield or flight as a defeat (#466), from
            # the challengeRating on their own sheet; never guessed.
            sheet = _hostile_person_sheet(creature, encounter, path_manager)
            if sheet is None:
                continue
            cr = sheet.get('challengeRating')
            try:
                xp = get_xp_for_cr(cr) if cr is not None else 0
            except (TypeError, ValueError, ZeroDivisionError):
                xp = 0
            if not xp:
                print(f"XP: {creature['name']} has no usable challengeRating ({cr!r}); no XP")
                continue
            defeated_count += 1
            total_xp += xp
            xp_breakdown.append((sheet.get('name') or creature['name'], cr, xp))

    # Count player characters and party NPCs
    num_players = len(party_tracker['partyMembers'])
    num_npcs = len(party_tracker['partyNPCs'])
    total_participants = num_players + num_npcs

    return total_xp, defeated_count, xp_breakdown, total_participants

def main():
    # Load party tracker
    party_tracker = load_json_file('party_tracker.json')

    # Get the active encounter ID
    active_encounter_id = party_tracker['worldConditions']['activeCombatEncounter']
    
    if not active_encounter_id:
        return "No active combat encounter found.", 0

    # Load the active encounter
    encounter_filename = f"modules/encounters/encounter_{active_encounter_id}.json"
    if not os.path.exists(encounter_filename):
        return f"Encounter file {encounter_filename} not found.", 0

    encounter = load_json_file(encounter_filename)

    # Calculate XP
    total_xp, defeated_count, xp_breakdown, total_participants = calculate_xp(encounter, party_tracker)

    if total_participants == 0:
        return "No players or party NPCs found.", 0

    # Create a single narrative sentence
    player_names = ", ".join(party_tracker['partyMembers'])
    npc_names = ", ".join([npc['name'] for npc in party_tracker['partyNPCs']])
    all_participants = f"{player_names} and their companions {npc_names}" if npc_names else player_names

    if defeated_count == 0:
        narrative = f"{all_participants} faced enemies in an encounter at {encounter['encounterSummary']}, but no experience was awarded as no monsters were defeated."
        xp_awarded = 0
    else:
        xp_per_participant = total_xp // total_participants
        enemy_description = f"{defeated_count} enemy" if defeated_count == 1 else f"{defeated_count} enemies"
        xp_details = ", ".join([f"{monster} (CR {cr}, {xp} XP)" for monster, cr, xp in xp_breakdown])
        
        narrative = f"{all_participants} defeated {enemy_description} ({xp_details}) in an encounter at {encounter['encounterSummary']}, "
        narrative += f"resulting in a total of {total_xp} XP, which was divided among {total_participants} participant(s) "
        narrative += f"({len(party_tracker['partyMembers'])} player(s) and {len(party_tracker['partyNPCs'])} party NPC(s)), "
        narrative += f"awarding each participant {xp_per_participant} experience points."
        xp_awarded = xp_per_participant

    return narrative, xp_awarded

if __name__ == "__main__":
    narrative, xp = main()
    print(narrative)
    print(f"XP awarded per participant: {xp}")