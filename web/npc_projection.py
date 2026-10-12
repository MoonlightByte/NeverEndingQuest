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


def _people_here(party, location_id):
    # The engine's view of who is here, as the party panel reads it (P4-f).
    # None while that view is unavailable: callers then use the authored list.
    module = party.get('module')
    if not (isinstance(module, str) and module and location_id):
        return None
    try:
        from core.nql import occupants
        here = occupants.place_roster(module.replace(' ', '_'), location_id)
    except Exception:
        return None
    people = here.get('people') if isinstance(here, dict) else None
    return list(people) if isinstance(people, list) else None


def visible_npc_names(party, area):
    names = []
    party_npcs = party.get('partyNPCs')
    candidates = list(party_npcs) if isinstance(party_npcs, list) else []
    world = party.get('worldConditions')
    location_id = world.get('currentLocationId') if isinstance(world, dict) else None
    people = _people_here(party, location_id)
    if people is not None:
        candidates.extend(people)
    else:
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
