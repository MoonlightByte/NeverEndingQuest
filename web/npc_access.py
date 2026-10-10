"""Resolve a player-visible NPC record without exposing arbitrary saved NPCs."""
from .media_paths import resolve_file_within
from .npc_projection import visible_npc_names


def _component(value):
    return (isinstance(value, str) and value not in ('', '.', '..')
            and not any(c in value for c in '/\\\x00:'))


def inspectable_npc_names(party):
    """Party, current location, and NPCs actually projected into active combat."""
    from utils.file_operations import safe_read_json
    area = {}
    world = party.get('worldConditions') or {}
    if not isinstance(world, dict):
        world = {}
    module = party.get('module') or party.get('module_name')
    module = module.replace(' ', '_') if isinstance(module, str) else None
    area_id = world.get('currentAreaId')
    if _component(module) and _component(area_id):
        path = resolve_file_within(f'modules/{module}/areas', area_id + '.json')
        area = safe_read_json(path) if path else {}
    names = visible_npc_names(party, area if isinstance(area, dict) else {})
    encounter_id = world.get('activeCombatEncounter')
    if _component(encounter_id):
        path = resolve_file_within('modules/encounters', f'encounter_{encounter_id}.json')
        encounter = safe_read_json(path) if path else None
        if isinstance(encounter, dict):
            from core.managers.combat_state import initiative_ui_projection
            # Use the same committed roster as the UI, not every creature in
            # the encounter file (typed observers are deliberately excluded).
            for actor in initiative_ui_projection(encounter):
                name = actor.get('name')
                if actor.get('type') == 'npc' and isinstance(name, str) and name:
                    names.append(name)
    return list(dict.fromkeys(names))


def load_inspectable_npc(name):
    """Keep the existing fuzzy aliases, but only among visible resolved records."""
    if not isinstance(name, str) or not name.strip() or len(name) > 512:
        return None
    from utils.file_operations import safe_read_json
    from updates.update_character_info import find_character_file_fuzzy, normalize_character_name
    party = safe_read_json('party_tracker.json')
    if not isinstance(party, dict):
        return None
    allowed = {}
    for visible in inspectable_npc_names(party):
        matched = find_character_file_fuzzy(visible)
        if not matched:
            continue
        path = resolve_file_within('characters', normalize_character_name(matched) + '.json')
        if path:
            allowed[normalize_character_name(visible)] = path
            allowed[normalize_character_name(matched)] = path
    if not allowed:
        return None
    path = allowed.get(normalize_character_name(name))
    if not path:
        matched = find_character_file_fuzzy(name)
        if matched:
            candidate = resolve_file_within('characters', normalize_character_name(matched) + '.json')
            if candidate in allowed.values():
                path = candidate
    if not path:
        return None
    character = safe_read_json(path)
    return character if isinstance(character, dict) else None
