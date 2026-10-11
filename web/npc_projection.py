"""Character-sheet fields for NPCs the player can currently inspect."""
import copy

SHEET_FIELDS = frozenset({
    'name', 'race', 'class', 'level', 'alignment', 'hitPoints', 'maxHitPoints',
    'armorClass', 'initiative', 'speed', 'abilities', 'savingThrows', 'skills',
    'proficiencyBonus', 'senses', 'languages', 'proficiencies', 'conditions',
    'classFeatures', 'racialTraits', 'backgroundFeature', 'background',
    'equipment', 'ammunition', 'attacksAndSpellcasting', 'spellcasting', 'currency',
    'experience_points', 'exp_required_for_next_level', 'damageVulnerabilities',
    'damageResistances', 'damageImmunities', 'conditionImmunities',
    # These already render in the expanded character sheet. Preserve public
    # biography and mechanical features while excluding DM memory/secret fields.
    'temporaryEffects', 'feats', 'personality_traits', 'ideals', 'bonds', 'flaws',
    'status', 'condition', 'deathSaves', 'spellSlots', 'currentHp', 'maxHp',
})


def visible_npc_names(party, area):
    names = []
    party_npcs = party.get('partyNPCs')
    candidates = list(party_npcs) if isinstance(party_npcs, list) else []
    world = party.get('worldConditions')
    location_id = world.get('currentLocationId') if isinstance(world, dict) else None
    locations = area.get('locations') if isinstance(area, dict) else None
    for location in locations if isinstance(locations, list) else []:
        if isinstance(location, dict) and location_id and location.get('locationId') == location_id:
            nearby = location.get('npcs')
            if isinstance(nearby, list):
                candidates.extend(nearby)
    for candidate in candidates:
        name = candidate.get('name') if isinstance(candidate, dict) else candidate
        if isinstance(name, str) and name and name.casefold() not in {n.casefold() for n in names}:
            names.append(name)
    return names


def npc_sheet_projection(character):
    # Do not send DM memories, secrets, plot roles or future-location records.
    return {key: copy.deepcopy(value) for key, value in character.items() if key in SHEET_FIELDS}
