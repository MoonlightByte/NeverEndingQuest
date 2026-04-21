# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Tabletop socket handlers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
from typing import Callable, Dict, List, Any, Optional


# TABLETOP MODE: Image version metadata helpers for deterministic portrait cache coherence
# These helpers compute versioned asset metadata to enable consistent refresh across
# Character Sheet, initiative queue, and party strip surfaces.


def _normalize_character_slug(character_name: str) -> str:
    """Normalize character name to safe filename/slug format.

    Matches backend normalize_character_name semantics:
    - Lowercase
    - Spaces -> underscores
    - Apostrophes -> underscores
    - Other non-alphanumeric -> underscores
    - Collapse consecutive underscores
    - Strip leading/trailing underscores

    Args:
        character_name: Raw character name (e.g., "Mac'Davier")

    Returns:
        Normalized slug (e.g., "mac_davier")
    """
    import re
    name = character_name.strip().lower()
    name = name.replace(" ", "_")
    name = name.replace("'", "_")
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    return name


def _get_image_candidate_paths(
    slug: str,
    module_name: Optional[str] = None,
    media_type: str = "npc",
) -> List[str]:
    """Build list of candidate portrait/media file paths for version detection.

    Candidate chain (in priority order):
    - For npc:
      1. web/static/portraits/<slug>.png (PC portrait location)
      2. modules/<module>/media/npcs/<slug>_thumb.jpg (module NPC thumbnail)
      3. modules/<module>/media/npcs/<slug>.jpg (module NPC full)
      4. modules/<module>/media/npcs/<slug>.png (module NPC PNG)
      5. web/static/media/npcs/<slug>_thumb.jpg (static NPC thumbnail)
      6. web/static/media/npcs/<slug>.jpg (static NPC full)
      7. web/static/media/npcs/<slug>.png (static NPC PNG)
    - For monster:
      1. modules/<module>/media/monsters/<slug>_thumb.jpg
      2. modules/<module>/media/monsters/<slug>_thumb.png
      3. modules/<module>/media/monsters/<slug>.jpg
      4. modules/<module>/media/monsters/<slug>.png
      5. web/static/media/monsters/<slug>_thumb.jpg
      6. web/static/media/monsters/<slug>_thumb.png
      7. web/static/media/monsters/<slug>.jpg
      8. web/static/media/monsters/<slug>.png

    Args:
        slug: Normalized character/entity slug
        module_name: Optional current module name for module-specific paths
        media_type: "npc" or "monster" candidate chain selector

    Returns:
        List of candidate file paths (may include non-existent paths)
    """
    candidates: List[str] = []

    normalized_media_type = (media_type or "npc").strip().lower()

    # TABLETOP MODE: Hostile scene-presence cards should resolve against monster media,
    # not NPC media. Keep npc chain as default for existing player/NPC behavior.
    if normalized_media_type == "monster":
        if module_name:
            module_base = os.path.join("modules", module_name, "media", "monsters")
            candidates.append(os.path.join(module_base, f"{slug}_thumb.jpg"))
            candidates.append(os.path.join(module_base, f"{slug}_thumb.png"))
            candidates.append(os.path.join(module_base, f"{slug}.jpg"))
            candidates.append(os.path.join(module_base, f"{slug}.png"))

        static_base = os.path.join("web", "static", "media", "monsters")
        candidates.append(os.path.join(static_base, f"{slug}_thumb.jpg"))
        candidates.append(os.path.join(static_base, f"{slug}_thumb.png"))
        candidates.append(os.path.join(static_base, f"{slug}.jpg"))
        candidates.append(os.path.join(static_base, f"{slug}.png"))
        return candidates

    # Primary PC portrait location
    candidates.append(os.path.join("web", "static", "portraits", f"{slug}.png"))

    # Module-specific NPC media paths (only if module context provided)
    if module_name:
        module_base = os.path.join("modules", module_name, "media", "npcs")
        candidates.append(os.path.join(module_base, f"{slug}_thumb.jpg"))
        candidates.append(os.path.join(module_base, f"{slug}.jpg"))
        candidates.append(os.path.join(module_base, f"{slug}.png"))

    # Static fallback NPC media paths
    static_base = os.path.join("web", "static", "media", "npcs")
    candidates.append(os.path.join(static_base, f"{slug}_thumb.jpg"))
    candidates.append(os.path.join(static_base, f"{slug}.jpg"))
    candidates.append(os.path.join(static_base, f"{slug}.png"))

    return candidates


def _compute_image_version_from_paths(paths: List[str]) -> Optional[str]:
    """Compute deterministic image version from candidate file mtimes.

    Returns the maximum mtime among existing files as a stable version string.
    Fail-open: returns None if no files exist or stat errors occur.

    Args:
        paths: List of candidate file paths

    Returns:
        Version string (max mtime as integer string) or None if no files exist
    """
    max_mtime: Optional[float] = None

    for path in paths:
        try:
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                if max_mtime is None or mtime > max_mtime:
                    max_mtime = mtime
        except Exception:
            # Fail-open: ignore stat errors for individual candidates
            continue

    if max_mtime is None:
        return None

    # Return as integer string for deterministic URL versioning
    return str(int(max_mtime))


def _build_image_metadata(
    slug: str,
    module_name: Optional[str] = None,
    media_type: str = "npc",
) -> Dict[str, Any]:
    """Build image metadata dict with slug and deterministic version.

    This is the primary public helper for payload builders to get versioned
    image metadata for entities.

    Args:
        slug: Normalized character/entity slug
        module_name: Optional current module name for module-specific paths
        media_type: "npc" or "monster" candidate chain selector

    Returns:
        Dict with keys:
        - image_slug: str (normalized identity)
        - image_version: Optional[str] (max mtime version or None if no files)
    """
    candidates = _get_image_candidate_paths(slug, module_name, media_type=media_type)
    version = _compute_image_version_from_paths(candidates)

    return {
        "image_slug": slug,
        "image_version": version
    }


def _dedupe_party_member_names_for_emit(party_members: List[Any]) -> List[str]:
    """Dedupe party member names by normalized identity, preserving first label."""
    from updates.update_character_info import normalize_character_name

    deduped: List[str] = []
    seen = set()
    for member in party_members or []:
        member_str = str(member or "").strip()
        normalized = normalize_character_name(member_str)
        if not normalized or normalized in seen:
            continue
        deduped.append(member_str)
        seen.add(normalized)
    return deduped


def _extract_visible_location_hostiles(location_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return explicitly visible hostile scene actors for the non-combat strip.

    Generic location `monsters` data represents encounter seeds or possible threats,
    which may be off-screen, behind doors, or otherwise not currently visible to the
    party. To avoid leaking hidden threats into the top-strip UI, pre-combat hostile
    cards are emitted only from explicit scene-visibility metadata.

    Supported additive metadata keys:
    - `visibleHostiles`
    - `hostileSceneRoster`
    - `sceneHostiles`
    - `preCombatHostiles`
    """
    explicit_roster = None
    for key in ("visibleHostiles", "hostileSceneRoster", "sceneHostiles", "preCombatHostiles"):
        roster_value = location_data.get(key)
        if isinstance(roster_value, list):
            explicit_roster = roster_value
            break

    if not explicit_roster:
        return []

    visible_hostiles: List[Dict[str, str]] = []
    for hostile_entry in explicit_roster:
        hostile_name = ""
        hostile_monster_type = ""

        if isinstance(hostile_entry, dict):
            hostile_name = str(hostile_entry.get("name") or "").strip()
            hostile_monster_type = str(hostile_entry.get("monsterType") or hostile_name).strip()
        elif isinstance(hostile_entry, str):
            hostile_name = hostile_entry.strip()
            hostile_monster_type = hostile_name

        if not hostile_name:
            continue

        visible_hostiles.append({
            "name": hostile_name,
            "monsterType": hostile_monster_type or hostile_name,
        })

    return visible_hostiles


def handle_party_data_request_impl(emit_fn: Callable[..., None], error_fn: Callable[..., None]) -> None:
    """Handle requests for party member display and current location NPCs (non-combat)."""
    try:
        from utils.file_operations import safe_read_json
        from utils.module_path_manager import ModulePathManager
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy

        party_tracker = safe_read_json("party_tracker.json")
        if not party_tracker:
            emit_fn('party_data_response', {
                'members': [],
                'location_npcs': [],
                'location_hostiles': [],
                'party_members': [],
                'active_character': None,
            })
            return

        current_module = party_tracker.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(current_module)

        party_members = []

        active_name = party_tracker.get('active_character')
        if not active_name and party_tracker.get('partyMembers'):
            active_name = party_tracker['partyMembers'][0]

        if active_name:
            player_name = normalize_character_name(active_name)

            try:
                player_file = path_manager.get_character_path(player_name)
                if os.path.exists(player_file):
                    player_data = safe_read_json(player_file)
                    if player_data:
                        spells_by_level = {}
                        spellcasting = player_data.get('spellcasting', {})
                        if spellcasting.get('spells'):
                            spells_data = spellcasting['spells']
                            if spells_data.get('cantrips') and len(spells_data['cantrips']) > 0:
                                spells_by_level[0] = spells_data['cantrips']
                            for i in range(1, 10):
                                key = f'level{i}'
                                if spells_data.get(key) and len(spells_data[key]) > 0:
                                    spells_by_level[i] = spells_data[key]

                        class_features = []
                        for feature in player_data.get('classFeatures', []):
                            feature_info = {'name': feature.get('name', '')}
                            if 'usage' in feature:
                                usage = feature['usage']
                                if usage.get('current') is not None and usage.get('max'):
                                    feature_info['usage'] = f"{usage['current']}/{usage['max']}"
                            class_features.append(feature_info)

                        primary_attack = {'bonus': 0, 'damage': '1d4'}
                        attacks = player_data.get('attacksAndSpellcasting', [])
                        if attacks and isinstance(attacks, list) and len(attacks) > 0:
                            first_attack = attacks[0]
                            damage_dice = first_attack.get('damageDice', '1d4')
                            damage_bonus = first_attack.get('damageBonus', 0)
                            if damage_bonus > 0:
                                damage_str = f"{damage_dice}+{damage_bonus}"
                            elif damage_bonus < 0:
                                damage_str = f"{damage_dice}{damage_bonus}"
                            else:
                                damage_str = damage_dice
                            primary_attack = {
                                'bonus': first_attack.get('attackBonus', 0),
                                'damage': damage_str,
                                'name': first_attack.get('name', 'Attack')
                            }

                        # TABLETOP MODE: Add image metadata for portrait cache coherence
                        player_slug = _normalize_character_slug(player_data.get('name', player_name))
                        player_image_meta = _build_image_metadata(player_slug, current_module)

                        party_members.append({
                            'name': player_data.get('name', player_name),
                            'type': 'player',
                            'currentHp': player_data.get('hitPoints', player_data.get('currentHp', 0)),
                            'maxHp': player_data.get('maxHitPoints', player_data.get('maxHp', 0)),
                            'level': player_data.get('level', 1),
                            'class': player_data.get('class', 'Unknown'),
                            'ac': player_data.get('armorClass', 10),
                            'speed': player_data.get('speed', 30),
                            'initiative': player_data.get('initiative', 0),
                            'primaryAttack': primary_attack,
                            'spellSlots': spellcasting.get('spellSlots', player_data.get('spellSlots', {})),
                            'spells': spells_by_level,
                            'conditions': player_data.get('conditions', []),
                            'classFeatures': class_features,
                            'image_slug': player_image_meta.get('image_slug'),
                            'image_version': player_image_meta.get('image_version'),
                        })
            except Exception:
                # TABLETOP MODE: Add image metadata for portrait cache coherence (minimal fallback)
                player_slug = _normalize_character_slug(player_name)
                player_image_meta = _build_image_metadata(player_slug, current_module)
                party_members.append({
                    'name': player_name,
                    'type': 'player',
                    'image_slug': player_image_meta.get('image_slug'),
                    'image_version': player_image_meta.get('image_version'),
                })

        for npc_info in party_tracker.get('partyNPCs', []):
            npc_name = npc_info['name']

            try:
                matched_name = find_character_file_fuzzy(npc_name)
                if matched_name:
                    npc_file = path_manager.get_character_path(matched_name)
                    if os.path.exists(npc_file):
                        npc_data = safe_read_json(npc_file)
                        if npc_data:
                            spells_by_level = {}
                            spellcasting = npc_data.get('spellcasting', {})
                            if spellcasting.get('spells'):
                                spells_data = spellcasting['spells']
                                if spells_data.get('cantrips') and len(spells_data['cantrips']) > 0:
                                    spells_by_level[0] = spells_data['cantrips']
                                for i in range(1, 10):
                                    key = f'level{i}'
                                    if spells_data.get(key) and len(spells_data[key]) > 0:
                                        spells_by_level[i] = spells_data[key]

                            class_features = []
                            for feature in npc_data.get('classFeatures', []):
                                feature_info = {'name': feature.get('name', '')}
                                if 'usage' in feature:
                                    usage = feature['usage']
                                    if usage.get('current') is not None and usage.get('max'):
                                        feature_info['usage'] = f"{usage['current']}/{usage['max']}"
                                class_features.append(feature_info)

                            primary_attack = {'bonus': 0, 'damage': '1d4'}
                            attacks = npc_data.get('attacksAndSpellcasting', [])
                            if attacks and isinstance(attacks, list) and len(attacks) > 0:
                                first_attack = attacks[0]
                                damage_dice = first_attack.get('damageDice', '1d4')
                                damage_bonus = first_attack.get('damageBonus', 0)
                                if damage_bonus > 0:
                                    damage_str = f"{damage_dice}+{damage_bonus}"
                                elif damage_bonus < 0:
                                    damage_str = f"{damage_dice}{damage_bonus}"
                                else:
                                    damage_str = damage_dice
                                primary_attack = {
                                    'bonus': first_attack.get('attackBonus', 0),
                                    'damage': damage_str,
                                    'name': first_attack.get('name', 'Attack')
                                }

                            ammunition_info = []
                            ammunition = npc_data.get('ammunition', [])
                            if ammunition:
                                for ammo in ammunition:
                                    if isinstance(ammo, dict):
                                        ammo_name = ammo.get('name', 'Unknown')
                                        ammo_qty = ammo.get('quantity', 0)
                                        ammunition_info.append({'name': ammo_name, 'quantity': ammo_qty})

                            # TABLETOP MODE: Add image metadata for portrait cache coherence
                            npc_slug = _normalize_character_slug(npc_data.get('name', npc_name))
                            npc_image_meta = _build_image_metadata(npc_slug, current_module)

                            party_members.append({
                                'name': npc_data.get('name', npc_name),
                                'type': 'npc',
                                'currentHp': npc_data.get('hitPoints', npc_data.get('currentHp', 0)),
                                'maxHp': npc_data.get('maxHitPoints', npc_data.get('maxHp', 0)),
                                'level': npc_data.get('level', 1),
                                'class': npc_data.get('class', 'Unknown'),
                                'ac': npc_data.get('armorClass', 10),
                                'speed': npc_data.get('speed', 30),
                                'initiative': npc_data.get('initiative', 0),
                                'primaryAttack': primary_attack,
                                'ammunition': ammunition_info,
                                'spellSlots': spellcasting.get('spellSlots', npc_data.get('spellSlots', {})),
                                'spells': spells_by_level,
                                'conditions': npc_data.get('conditions', []),
                                'classFeatures': class_features,
                                'image_slug': npc_image_meta.get('image_slug'),
                                'image_version': npc_image_meta.get('image_version'),
                            })
                            continue
            except Exception:
                pass

            # TABLETOP MODE: Add image metadata for portrait cache coherence (minimal fallback)
            npc_slug = _normalize_character_slug(npc_name)
            npc_image_meta = _build_image_metadata(npc_slug, current_module)
            party_members.append({
                'name': npc_name,
                'type': 'npc',
                'image_slug': npc_image_meta.get('image_slug'),
                'image_version': npc_image_meta.get('image_version'),
            })

        location_npcs = []
        location_hostiles = []
        world_conditions = party_tracker.get("worldConditions", {})
        current_area_id = world_conditions.get("currentAreaId")
        current_location_id = world_conditions.get("currentLocationId")
        active_encounter_id = world_conditions.get("activeCombatEncounter")

        if current_module and current_area_id and current_location_id:
            areas_dir = os.path.join("modules", current_module, "areas")
            area_file_path = os.path.join(areas_dir, f"{current_area_id}.json")

            if os.path.exists(area_file_path):
                area_data = safe_read_json(area_file_path)
                if area_data and 'locations' in area_data:
                    current_location_data = next(
                        (loc for loc in area_data['locations'] if loc.get('locationId') == current_location_id),
                        None,
                    )

                    if current_location_data and 'npcs' in current_location_data:
                        # TABLETOP MODE: Use canonical equality matching for dedupe to prevent substring false positives
                        # (e.g., "Ansel" should not suppress "Anselara")
                        def _canonical_name_for_dedupe(name: str) -> str:
                            """Normalize name to canonical form for equality comparison."""
                            return name.lower().strip().replace("'", "").replace(" ", "_")

                        canonical_party_names = {_canonical_name_for_dedupe(member['name']) for member in party_members}

                        for npc in current_location_data['npcs']:
                            npc_name = npc.get('name') if isinstance(npc, dict) else npc
                            if npc_name:
                                if _canonical_name_for_dedupe(npc_name) not in canonical_party_names:
                                    npc_data_dict = {'name': npc_name, 'type': 'location_npc'}
                                    try:
                                        matched_name = find_character_file_fuzzy(npc_name)
                                        if matched_name:
                                            npc_file = path_manager.get_character_path(matched_name)
                                            if os.path.exists(npc_file):
                                                npc_data = safe_read_json(npc_file)
                                                if npc_data:
                                                    npc_data_dict['currentHp'] = npc_data.get('hitPoints', npc_data.get('currentHp', 0))
                                                    npc_data_dict['maxHp'] = npc_data.get('maxHitPoints', npc_data.get('maxHp', 0))
                                    except Exception:
                                        pass
                                    # TABLETOP MODE: Add image metadata for portrait cache coherence
                                    location_npc_slug = _normalize_character_slug(npc_name)
                                    location_npc_image_meta = _build_image_metadata(location_npc_slug, current_module)
                                    npc_data_dict['image_slug'] = location_npc_image_meta.get('image_slug')
                                    npc_data_dict['image_version'] = location_npc_image_meta.get('image_version')
                                    location_npcs.append(npc_data_dict)

                    # TABLETOP MODE: Surface only explicitly visible hostile scene presence pre-combat.
                    # Do not leak generic location monster seeds into the player-visible top strip.
                    if not active_encounter_id and current_location_data:
                        for monster_entry in _extract_visible_location_hostiles(current_location_data):
                            monster_name = str(monster_entry.get('name') or '').strip()
                            if not monster_name:
                                continue

                            monster_asset_key = str(monster_entry.get('monsterType') or monster_name).strip()

                            monster_data_dict = {
                                'name': monster_name,
                                'type': 'location_hostile',
                                'monsterType': monster_asset_key,
                            }
                            hostile_slug = _normalize_character_slug(monster_asset_key)
                            hostile_image_meta = _build_image_metadata(
                                hostile_slug,
                                current_module,
                                media_type="monster",
                            )
                            monster_data_dict['image_slug'] = hostile_image_meta.get('image_slug')
                            monster_data_dict['image_version'] = hostile_image_meta.get('image_version')
                            location_hostiles.append(monster_data_dict)

        emit_fn('party_data_response', {
            'members': party_members,
            'location_npcs': location_npcs,
            'location_hostiles': location_hostiles,
            'party_members': _dedupe_party_member_names_for_emit(party_tracker.get('partyMembers', [])),
            'active_character': party_tracker.get('active_character'),
        })

    except Exception as request_error:
        error_fn(f"Failed to get party data: {str(request_error)}", exception=request_error, category="web_interface")
        emit_fn('party_data_response', {
            'members': [],
            'location_npcs': [],
            'location_hostiles': [],
            'party_members': [],
            'active_character': None,
        })


def handle_initiative_data_request_impl(emit_fn: Callable[..., None], error_fn: Callable[..., None]) -> None:
    """Handle requests for current combat initiative order."""
    try:
        from utils.file_operations import safe_read_json

        party_tracker = safe_read_json("party_tracker.json")
        if not party_tracker:
            emit_fn('initiative_data_response', {'active': False, 'combatants': []})
            return

        active_encounter_id = party_tracker.get("worldConditions", {}).get("activeCombatEncounter")
        if not active_encounter_id:
            emit_fn('initiative_data_response', {'active': False, 'combatants': []})
            return

        encounter_file = f"modules/encounters/encounter_{active_encounter_id}.json"
        encounter_data = safe_read_json(encounter_file)
        if not encounter_data or "creatures" not in encounter_data:
            emit_fn('initiative_data_response', {'active': False, 'combatants': []})
            return

        # TABLETOP MODE: Section 3.1 - Keep player combatants visible during active combat,
        # including unconscious/incapacitated states, to avoid false missing-player UI.
        visible_combatants = []
        for creature in encounter_data["creatures"]:
            creature_type = str(creature.get("type", "")).lower()
            status = str(creature.get("status", "unknown")).lower()
            try:
                current_hp = int(creature.get("currentHitPoints", 0))
            except (TypeError, ValueError):
                current_hp = 0

            if creature_type == "player":
                # Include all non-dead players so incapacitated/unconscious PCs remain in initiative UI.
                if status != "dead":
                    visible_combatants.append(creature)
            else:
                # Preserve existing behavior for non-player combatants.
                if status == "alive" and current_hp > 0:
                    visible_combatants.append(creature)

        if not visible_combatants:
            emit_fn('initiative_data_response', {'active': False, 'combatants': []})
            return

        sorted_combatants = sorted(
            visible_combatants,
            key=lambda item: item.get("initiative", 0),
            reverse=True,
        )

        from utils.module_path_manager import ModulePathManager
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy

        party_tracker = safe_read_json("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else ""
        path_manager = ModulePathManager(current_module) if current_module else None

        combatant_list = []
        for combatant in sorted_combatants:
            combatant_data = {
                "name": combatant.get("name"),
                "type": combatant.get("type"),
                "status": combatant.get("status"),
                "initiative": combatant.get("initiative"),
                "currentHp": combatant.get("currentHitPoints"),
                "maxHp": combatant.get("maxHitPoints"),
                "monsterType": combatant.get("monsterType"),
                "class": combatant.get("class"),
            }

            if path_manager and combatant.get("type") in ['player', 'npc']:
                try:
                    character_name = normalize_character_name(combatant.get("name", ""))

                    if combatant.get("type") == 'npc':
                        matched_name = find_character_file_fuzzy(character_name)
                        if matched_name:
                            char_file = path_manager.get_character_path(matched_name)
                        else:
                            char_file = None
                    else:
                        char_file = path_manager.get_character_path(character_name)

                    if char_file and os.path.exists(char_file):
                        char_data = safe_read_json(char_file)
                        if char_data:
                            spells_by_level = {}
                            spellcasting = char_data.get('spellcasting', {})
                            if spellcasting.get('spells'):
                                spells_data = spellcasting['spells']
                                if spells_data.get('cantrips') and len(spells_data['cantrips']) > 0:
                                    spells_by_level[0] = spells_data['cantrips']
                                for i in range(1, 10):
                                    key = f'level{i}'
                                    if spells_data.get(key) and len(spells_data[key]) > 0:
                                        spells_by_level[i] = spells_data[key]

                            class_features = []
                            for feature in char_data.get('classFeatures', []):
                                feature_info = {'name': feature.get('name', '')}
                                if 'usage' in feature:
                                    usage = feature['usage']
                                    if usage.get('current') is not None and usage.get('max'):
                                        feature_info['usage'] = f"{usage['current']}/{usage['max']}"
                                class_features.append(feature_info)

                            primary_attack = {'bonus': 0, 'damage': '1d4'}
                            attacks = char_data.get('attacksAndSpellcasting', [])
                            if attacks and isinstance(attacks, list) and len(attacks) > 0:
                                first_attack = attacks[0]
                                damage_dice = first_attack.get('damageDice', '1d4')
                                damage_bonus = first_attack.get('damageBonus', 0)
                                if damage_bonus > 0:
                                    damage_str = f"{damage_dice}+{damage_bonus}"
                                elif damage_bonus < 0:
                                    damage_str = f"{damage_dice}{damage_bonus}"
                                else:
                                    damage_str = damage_dice
                                primary_attack = {
                                    'bonus': first_attack.get('attackBonus', 0),
                                    'damage': damage_str,
                                    'name': first_attack.get('name', 'Attack')
                                }

                            ammunition_info = []
                            ammunition = char_data.get('ammunition', [])
                            if ammunition:
                                for ammo in ammunition:
                                    if isinstance(ammo, dict):
                                        ammo_name = ammo.get('name', 'Unknown')
                                        ammo_qty = ammo.get('quantity', 0)
                                        ammunition_info.append({'name': ammo_name, 'quantity': ammo_qty})

                            combatant_data.update({
                                'level': char_data.get('level', 1),
                                'ac': char_data.get('armorClass', 10),
                                'speed': char_data.get('speed', 30),
                                'primaryAttack': primary_attack,
                                'ammunition': ammunition_info,
                                'spellSlots': spellcasting.get('spellSlots', char_data.get('spellSlots', {})),
                                'spells': spells_by_level,
                                'conditions': char_data.get('conditions', []),
                                'classFeatures': class_features,
                                'abilities': char_data.get('abilities', {}),
                            })

                            # TABLETOP MODE: Add image metadata for portrait cache coherence
                            # TABLETOP MODE: Prefer stable monsterType slug for enemies to avoid
                            # display-name variants breaking portrait/media linkage.
                            slug_source = combatant.get("monsterType") or combatant.get("name", "")
                            combatant_slug = _normalize_character_slug(slug_source)
                            media_type = "monster" if str(combatant.get("type", "")).lower() in {"enemy", "monster"} else "npc"
                            combatant_image_meta = _build_image_metadata(combatant_slug, current_module, media_type=media_type)
                            combatant_data['image_slug'] = combatant_image_meta.get('image_slug')
                            combatant_data['image_version'] = combatant_image_meta.get('image_version')
                except Exception as load_error:
                    error_fn(
                        f"Error loading character data for {combatant.get('name', 'unknown')}: {load_error}",
                        category="web_interface",
                    )

            # TABLETOP MODE: Ensure image metadata for combatants even when char data load failed
            if 'image_slug' not in combatant_data:
                slug_source = combatant.get("monsterType") or combatant.get("name", "")
                combatant_slug = _normalize_character_slug(slug_source)
                media_type = "monster" if str(combatant.get("type", "")).lower() in {"enemy", "monster"} else "npc"
                combatant_image_meta = _build_image_metadata(combatant_slug, current_module, media_type=media_type)
                combatant_data['image_slug'] = combatant_image_meta.get('image_slug')
                combatant_data['image_version'] = combatant_image_meta.get('image_version')

            combatant_list.append(combatant_data)

        emit_fn('initiative_data_response', {
            'active': True,
            'combatants': combatant_list,
            'round': encounter_data.get('combat_round', 1),
        })

    except Exception as request_error:
        error_fn(f"Error handling initiative data request: {request_error}", exception=request_error, category="web_interface")
        emit_fn('initiative_data_response', {'active': False, 'combatants': []})


def handle_plot_data_request_impl(emit_fn: Callable[..., None], debug_fn: Callable[..., None]) -> None:
    """Handle requests for the current module's plot data."""
    try:
        party_tracker_path = 'party_tracker.json'
        if not os.path.exists(party_tracker_path):
            emit_fn('plot_data_response', {'data': None, 'error': 'Party tracker not found'})
            return

        with open(party_tracker_path, 'r', encoding='utf-8') as tracker_file:
            party_tracker = json.load(tracker_file)

        current_module = party_tracker.get("module", "").replace(" ", "_")
        if not current_module:
            emit_fn('plot_data_response', {'data': None, 'error': 'Current module not set in party tracker'})
            return

        from utils.module_path_manager import ModulePathManager
        from utils.quest_player_formatter import ensure_player_quests_file

        path_manager = ModulePathManager(current_module)
        ensure_result = ensure_player_quests_file(current_module)
        player_quests_path = ensure_result.get(
            "path",
            os.path.join(path_manager.module_dir, f"player_quests_{current_module}.json"),
        )

        if ensure_result.get("status") == "regenerated":
            debug_fn(
                f"WEB_INTERFACE: Regenerated player-friendly quests for {current_module}",
                category="web_interface",
            )

        use_plot_fallback = False
        if os.path.exists(player_quests_path):
            try:
                with open(player_quests_path, 'r', encoding='utf-8') as quests_file:
                    player_quests_data = json.load(quests_file)

                plot_data = {"plotPoints": []}

                for quest_data in player_quests_data.get("quests", {}).values():
                    plot_point = {
                        "id": quest_data.get("id"),
                        "title": quest_data.get("title"),
                        "description": quest_data.get("playerDescription", quest_data.get("originalDescription", "")),
                        "status": quest_data.get("status"),
                        "sideQuests": []
                    }

                    for sq_data in quest_data.get("sideQuests", {}).values():
                        plot_point["sideQuests"].append({
                            "id": sq_data.get("id"),
                            "title": sq_data.get("title"),
                            "description": sq_data.get("playerDescription", ""),
                            "status": sq_data.get("status")
                        })

                    plot_data["plotPoints"].append(plot_point)

                debug_fn(f"WEB_INTERFACE: Using player-friendly quests for {current_module}", category="web_interface")
            except Exception as player_quests_error:
                debug_fn(
                    f"WEB_INTERFACE: Player quest load failed for {current_module}, falling back to module plot ({player_quests_error})",
                    category="web_interface",
                )
                use_plot_fallback = True
        else:
            use_plot_fallback = True

        if use_plot_fallback:
            plot_file_path = path_manager.get_plot_path()

            if not os.path.exists(plot_file_path):
                emit_fn('plot_data_response', {'data': None, 'error': f'Plot file not found for module: {current_module}'})
                return

            with open(plot_file_path, 'r', encoding='utf-8') as plot_file:
                plot_data = json.load(plot_file)

            debug_fn(
                f"WEB_INTERFACE: Using original plot data for {current_module} (player quests unavailable)",
                category="web_interface"
            )

        emit_fn('plot_data_response', {'data': plot_data})

    except Exception as request_error:
        emit_fn('plot_data_response', {'data': None, 'error': str(request_error)})


def handle_storage_data_request_impl(
    emit_fn: Callable[..., None],
    debug_fn: Callable[..., None],
    error_fn: Callable[..., None]
) -> None:
    """Handle requests to view all player storage."""
    debug_fn("WEB_REQUEST: Received request for storage data from client", category="web_interface")
    try:
        from core.managers.storage_manager import get_storage_manager
        manager = get_storage_manager()
        storage_data = manager.view_storage()

        if storage_data.get("success"):
            emit_fn('storage_data_response', {'data': storage_data})
        else:
            emit_fn('error', {'message': 'Failed to retrieve storage data.'})

    except Exception as request_error:
        error_fn(
            f"ERROR handling storage request: {request_error}",
            exception=request_error,
            category="web_interface"
        )
        emit_fn('error', {'message': 'An internal error occurred while fetching storage data.'})
