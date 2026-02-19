# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Routes - Tabletop party management endpoints
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, jsonify, request

import utils.pc_manager as pc_manager
from updates.update_character_info import normalize_character_name
from utils.character_creator import (
    CHARACTER_CREATION_MARKER,
    backup_conversation_history,
    generate_ambiguous_transition,
    get_party_level,
    is_creation_mode_active,
    restore_conversation_history,
)
from utils.character_creation_audit import (
    AUDIT_RESULT_SCHEMA_ERROR,
    AUDIT_RESULT_SUCCESS,
    audit_character_creation,
    audit_character_readiness,
    audit_profile_readiness,
    apply_background_feature_suggestion_if_generic,
    seed_missing_appearance_fields,
)
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import error, info, warning
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_path_manager import ModulePathManager

# TABLETOP MODE: Party transition memory for retirement/return lifecycle
from core.memory.party_transition_memory import (
    build_return_memory_pack,
    record_pc_retirement,
    record_pc_return,
)


def register_tabletop_party_routes(app: Flask, user_input_queue: Any) -> None:
    """Register TABLETOP MODE party and character creation API routes."""

    def _split_csv(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(entry).strip() for entry in value if str(entry).strip()]
        return [segment.strip() for segment in str(value).split(',') if segment.strip()]

    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _normalize_lookup_name(value: str) -> str:
        return normalize_character_name(str(value or ""))

    def _extract_npc_name(entry: Any) -> str:
        if isinstance(entry, dict):
            return str(entry.get("name", "")).strip()
        return str(entry or "").strip()

    def _party_npc_names(party_tracker: Dict[str, Any]) -> List[str]:
        npc_entries = party_tracker.get("partyNPCs", [])
        npc_names: List[str] = []
        for npc_entry in npc_entries:
            npc_name = _extract_npc_name(npc_entry)
            if npc_name:
                npc_names.append(npc_name)
        return npc_names

    def _remove_npc_entry_by_name(party_tracker: Dict[str, Any], character_name: str) -> None:
        normalized_target = _normalize_lookup_name(character_name)
        filtered: List[Any] = []
        for npc_entry in party_tracker.get("partyNPCs", []):
            npc_name = _extract_npc_name(npc_entry)
            if _normalize_lookup_name(npc_name) == normalized_target:
                continue
            filtered.append(npc_entry)
        party_tracker["partyNPCs"] = filtered

    def _load_character_data(character_name: str) -> Dict[str, Any]:
        char_data = pc_manager.get_character_state(character_name)
        if isinstance(char_data, dict) and char_data:
            return char_data

        normalized_name = _normalize_lookup_name(character_name)
        fallback_path = os.path.join("characters", f"{normalized_name}.json")
        fallback_data = safe_read_json(fallback_path)
        if isinstance(fallback_data, dict):
            return fallback_data
        return {}

    def _save_character_data(character_name: str, character_data: Dict[str, Any]) -> bool:
        path_manager = ModulePathManager()
        normalized_name = _normalize_lookup_name(character_name)
        char_path = path_manager.get_character_path(normalized_name)
        return safe_write_json(char_path, character_data)

    @app.route('/api/party')
    def get_party() -> Any:
        """Get current party members and active character (tabletop mode)."""
        try:
            party_tracker = safe_read_json("party_tracker.json")
            if not party_tracker:
                return jsonify({'error': 'Party tracker not found'}), 404

            return jsonify({
                'partyMembers': party_tracker.get('partyMembers', []),
                'active_character': party_tracker.get('active_character'),
                'partyNPCs': party_tracker.get('partyNPCs', []),
            })
        except Exception as route_error:
            error(f"TABLETOP: Failed to get party info: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/set_active', methods=['POST'])
    def set_active_character() -> Any:
        """Switch active character (tabletop mode)."""
        try:
            data = request.get_json(silent=True) or {}
            character_name = data.get('character')

            if not character_name:
                return jsonify({'error': 'Character name required'}), 400

            party_tracker = safe_read_json("party_tracker.json")
            if not party_tracker:
                return jsonify({'error': 'Party tracker not found'}), 404

            if character_name not in party_tracker.get('partyMembers', []):
                return jsonify({'error': 'Character not in party'}), 400

            party_tracker['active_character'] = character_name
            safe_write_json("party_tracker.json", party_tracker)

            info(f"TABLETOP: Active character set to {character_name}")
            return jsonify({'success': True, 'active_character': character_name})
        except Exception as route_error:
            error(f"TABLETOP: Failed to set active character: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/characters')
    def get_party_characters_list() -> Any:
        """List Add Existing candidates by source mode."""
        try:
            party_tracker = safe_read_json("party_tracker.json") or {}
            current_module = (party_tracker.get("module") or "").replace(" ", "_") or None
            source_mode = str(request.args.get("source", "players")).strip().lower()
            if source_mode not in ("players", "npc_companions", "all"):
                source_mode = "players"

            party_members = set(party_tracker.get("partyMembers", []))
            normalized_party_members = {normalize_character_name(member) for member in party_members}

            available_characters: list[dict[str, Any]] = []
            seen_names: set[str] = set()

            def is_player(char_data: Any) -> bool:
                if not char_data:
                    return False
                if not isinstance(char_data, dict):
                    return False
                char_type = (char_data.get("type") or char_data.get("character_type") or "").lower()
                if char_type == "npc":
                    return False
                return char_type in ("player", "pc", "")

            def scan_dir(directory: str, module_specific: bool = False) -> None:
                if not os.path.exists(directory):
                    return

                for filename in os.listdir(directory):
                    if not filename.endswith('.json'):
                        continue
                    if '.backup' in filename or '.bak' in filename:
                        continue
                    try:
                        char_path = os.path.join(directory, filename)
                        char_data = safe_read_json(char_path)
                        if is_player(char_data):
                            if not isinstance(char_data, dict):
                                continue
                            character_name = char_data.get('name', filename.replace('.json', ''))
                            normalized_lookup_name = normalize_character_name(character_name)
                            if (
                                character_name in party_members
                                or normalized_lookup_name in normalized_party_members
                                or normalized_lookup_name in seen_names
                            ):
                                continue
                            seen_names.add(normalized_lookup_name)
                            available_characters.append({
                                'filename': filename,
                                'name': character_name,
                                'level': char_data.get('level', 1),
                                'class': char_data.get('class', 'Unknown'),
                                'module_specific': module_specific,
                                'source': 'players',
                                'candidate_type': 'player',
                                'action': 'add',
                                'before_role': 'player',
                                'after_role': 'player',
                            })
                    except Exception:
                        continue

            if source_mode in ("players", "all"):
                scan_dir('characters', module_specific=False)

                if current_module:
                    try:
                        path_manager = ModulePathManager(current_module)
                        scan_dir(os.path.join(path_manager.module_dir, "characters"), module_specific=True)
                    except Exception:
                        pass

            if source_mode in ("npc_companions", "all"):
                npc_names = _party_npc_names(party_tracker)
                for npc_name in npc_names:
                    normalized_lookup_name = _normalize_lookup_name(npc_name)
                    if (
                        not npc_name
                        or normalized_lookup_name in normalized_party_members
                        or normalized_lookup_name in seen_names
                    ):
                        continue

                    npc_data = _load_character_data(npc_name)
                    seen_names.add(normalized_lookup_name)
                    available_characters.append({
                        'filename': f"{normalized_lookup_name}.json",
                        'name': npc_name,
                        'level': npc_data.get('level', 1),
                        'class': npc_data.get('class', 'Unknown'),
                        'module_specific': True,
                        'source': 'npc_companions',
                        'candidate_type': 'npc_companion',
                        'action': 'promote',
                        'before_role': 'npc',
                        'after_role': 'player',
                        'has_character_id': bool(str(npc_data.get('character_id', '')).strip()),
                        'has_role_history': isinstance(npc_data.get('_tabletop_role_history'), list),
                    })

            return jsonify({'characters': available_characters, 'source': source_mode})
        except Exception as route_error:
            error(f"TABLETOP: Failed to list characters: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/create_player', methods=['POST'])
    def create_party_player() -> Any:
        """Create a new player character with DM assistance."""
        try:
            data = request.get_json(silent=True) or {}
            name = data.get('name', '').strip()
            target_level = data.get('level', None)

            if not name:
                return jsonify({'error': 'Character name is required'}), 400

            char_filename = name.lower().replace(' ', '_') + ".json"
            char_path = os.path.join('characters', char_filename)
            if os.path.exists(char_path):
                return jsonify({'error': f'Character file {char_filename} already exists!'}), 400

            party_tracker = pc_manager.get_party_tracker()
            if target_level is None:
                target_level = get_party_level(party_tracker)
            else:
                target_level = max(1, min(20, int(target_level)))

            active_pc = party_tracker.get("active_character", "")
            if not active_pc and party_tracker.get("partyMembers"):
                active_pc = party_tracker["partyMembers"][0]

            current_location = party_tracker.get("worldConditions", {}).get("currentLocation", "current location")
            module_name = party_tracker.get("module", "the current adventure")

            info(f"TABLETOP: Starting narrative-aware character creation for {name} at Level {target_level}")

            backup_success = backup_conversation_history()
            if not backup_success:
                warning("Failed to backup conversation history, proceeding anyway", category="character_creation")

            try:
                creation_prompt = pc_manager.get_character_creation_prompt(
                    module_name=module_name,
                    character_name=name,
                    party_tracker=party_tracker,
                    level=target_level,
                    is_mid_campaign=True,
                    active_pc=active_pc,
                    current_location=current_location,
                )
            except Exception as prompt_error:
                error(f"TABLETOP: Failed to load creation prompt: {prompt_error}")
                creation_prompt = (
                    f"[SYSTEM] A new player '{name}' is joining the table at Level {target_level}! "
                    "Please guide them through 5e character creation. "
                    "Ask for Race, Class, Background, Ability Scores, Skills, Equipment, and Personality. "
                    "When complete, output the full character as JSON."
                )

            safe_write_json(CHARACTER_CREATION_MARKER, {
                "active": True,
                "character_name": name,
                "target_level": target_level,
                "started_at": datetime.now().isoformat(),
                "active_pc": active_pc,
                "current_location": current_location,
            })

            user_input_queue.put(creation_prompt)

            info(f"TABLETOP: Character creation mode activated for {name} (Level {target_level})")
            return jsonify({
                'success': True,
                'message': f'Character creation started for {name} at Level {target_level}. Narrative paused.',
                'creation_mode': True,
                'character_name': name,
                'target_level': target_level,
            })
        except Exception as route_error:
            error(f"TABLETOP: Failed to start player creation: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/finalize_creation', methods=['POST'])
    def finalize_character_creation() -> Any:
        """Finalize character creation after LLM outputs JSON."""
        try:
            data = request.get_json(silent=True) or {}
            character_json = data.get('character_data')

            if not character_json:
                return jsonify({'error': 'Character data required'}), 400

            audit_result = audit_character_creation(
                character_json,
                source="tabletop_route_finalize_creation",
                enable_enrichment=True,
            )
            if audit_result.result_type != AUDIT_RESULT_SUCCESS:
                return jsonify({
                    'error': 'Character data failed validation',
                    'result_type': audit_result.result_type,
                    'errors': audit_result.errors,
                    'missing_paths': audit_result.missing_paths,
                }), 400

            character_data = audit_result.normalized_data
            character_name = character_data.get('name', 'Unknown')

            char_filename = normalize_character_name(character_name) + ".json"
            char_path = os.path.join('characters', char_filename)

            success = safe_write_json(char_path, character_data)
            if not success:
                return jsonify({'error': 'Failed to save character file'}), 500

            pc_manager.add_pc(character_name)

            creation_context = safe_json_load(CHARACTER_CREATION_MARKER) or {}
            active_pc = creation_context.get('active_pc', '')
            current_location = creation_context.get('current_location', 'current location')

            restore_success = restore_conversation_history()
            if not restore_success:
                warning("Failed to restore conversation history", category="character_creation")

            transition = generate_ambiguous_transition(
                character_data=character_data,
                active_pc_name=active_pc or character_name,
                location_context={"location": current_location},
            )
            user_input_queue.put(transition)

            pc_manager.set_active_pc(character_name)

            if os.path.exists(CHARACTER_CREATION_MARKER):
                os.remove(CHARACTER_CREATION_MARKER)

            info(f"TABLETOP: Character creation complete for {character_name}. Narrative resumed.")
            return jsonify({
                'success': True,
                'message': f'Character {character_name} created successfully!',
                'character_name': character_name,
                'transition_injected': True,
            })
        except Exception as route_error:
            error(f"TABLETOP: Failed to finalize character creation: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/creation_status', methods=['GET'])
    def get_creation_status() -> Any:
        """Get current character creation mode status."""
        try:
            is_active = is_creation_mode_active()
            if is_active:
                context = safe_json_load(CHARACTER_CREATION_MARKER) or {}
                return jsonify({
                    'creation_mode_active': True,
                    'character_name': context.get('character_name'),
                    'target_level': context.get('target_level'),
                    'started_at': context.get('started_at'),
                    'active_pc': context.get('active_pc'),
                })

            return jsonify({'creation_mode_active': False})
        except Exception as route_error:
            error(f"TABLETOP: Failed to get creation status: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/add_character', methods=['POST'])
    def add_party_character() -> Any:
        """Add existing character to party (tabletop mode)."""
        try:
            data = request.get_json(silent=True) or {}
            character_name = data.get('character')

            if not character_name:
                return jsonify({'error': 'Character name required'}), 400

            # TABLETOP MODE: Snapshot pre-add party membership to detect rejoins
            party_tracker_pre = pc_manager.get_party_tracker()
            normalized_target = _normalize_lookup_name(character_name)
            pre_membership = {_normalize_lookup_name(name) for name in party_tracker_pre.get('partyMembers', [])}
            was_previously_member = normalized_target in pre_membership

            success = pc_manager.add_pc(character_name)
            if not success:
                return jsonify({'error': f"Failed to add '{character_name}' to party. Ensure the character file exists."}), 400

            party_tracker = pc_manager.get_party_tracker()

            # TABLETOP MODE: Load character data early to detect return vs first-add
            char_data = _load_character_data(character_name) or {}

            # TABLETOP MODE: Helper to detect prior retirement for return classification
            def _has_prior_retirement_history(character_data: Dict[str, Any]) -> bool:
                """Check if character was previously retired (has retirement history)."""
                history = character_data.get("_tabletop_role_history")
                if not isinstance(history, list):
                    return False
                for event in history:
                    if not isinstance(event, dict):
                        continue
                    # Retirement markers: action=retired_from_party OR to_role=retired_player
                    if event.get("action") == "retired_from_party":
                        return True
                    if event.get("to_role") == "retired_player":
                        return True
                return False

            # TABLETOP MODE: Determine if this is a true return (rejoin after retirement) or first-time add
            is_true_return = (not was_previously_member) and _has_prior_retirement_history(char_data)

            # TABLETOP MODE: Persist return transition for true rejoins only (fail-open)
            if is_true_return:
                try:
                    return_result = record_pc_return(
                        character_name=character_name,
                        party_tracker=party_tracker
                    )
                    if return_result.get('status') == 'success':
                        info(
                            f"MEMORY_TRANSITION event=return character={character_name} status=success event_id={return_result.get('event_id')}",
                            category="memory_ingest"
                        )
                    else:
                        warning(
                            f"MEMORY_TRANSITION event=return character={character_name} status=degraded reason=persistence_error fallback=enabled message={return_result.get('message')}",
                            category="memory_ingest"
                        )
                except Exception as memory_error:
                    warning(
                        f"MEMORY_TRANSITION event=return character={character_name} status=degraded reason=exception fallback=enabled error={memory_error}",
                        category="memory_ingest"
                    )

            # TABLETOP MODE: Build exactly ONE narration prompt (return OR entrance, never both)
            narration_prompt = ""
            if is_true_return:
                # Return path: use memory pack with continuity
                try:
                    memory_pack = build_return_memory_pack(
                        character_name=character_name,
                        party_tracker=party_tracker
                    )
                    if memory_pack.get('status') == 'success':
                        snippets = memory_pack.get('continuity_snippets', [])
                        if snippets:
                            # Build bounded continuity summary (max 3 entries)
                            continuity_lines = []
                            for snippet in snippets[:3]:
                                summary = snippet.get('summary', '')
                                if summary:
                                    continuity_lines.append(f"- {summary}")
                            continuity_text = "\n".join(continuity_lines) if continuity_lines else "No prior continuity available."
                            narration_prompt = (
                                f"[SYSTEM] {character_name} has returned to the party. "
                                f"Prior continuity:\n{continuity_text}\n"
                                f"Please narrate their rejoining with appropriate NPC reactions referencing this history."
                            )
                        else:
                            narration_prompt = (
                                f"[SYSTEM] {character_name} has returned to the party. "
                                f"Please narrate their rejoining with appropriate NPC reactions."
                            )
                    else:
                        # Pack returned error status
                        narration_prompt = (
                            f"[SYSTEM] {character_name} has returned to the party. "
                            f"Please narrate their rejoining with appropriate NPC reactions."
                        )
                except Exception as pack_error:
                    warning(
                        f"TABLETOP: Return memory pack build failed for '{character_name}' (using fallback): {pack_error}",
                        category="memory_retrieval"
                    )
                    # Fallback when pack fails entirely
                    narration_prompt = (
                        f"[SYSTEM] {character_name} has returned to the party. "
                        f"Please narrate their rejoining with appropriate NPC reactions."
                    )
            elif not was_previously_member:
                # First-time add path: use entrance prompt
                narration_prompt = pc_manager.get_entrance_prompt(character_name, char_data, party_tracker)

            # Enqueue exactly one narration prompt (if non-empty)
            if narration_prompt:
                user_input_queue.put(narration_prompt)

            # TABLETOP MODE: Append return lifecycle metadata to character file for true returns only (fail-open)
            if is_true_return:
                try:
                    # Preserve canonical identity
                    pc_manager.ensure_stable_character_id(char_data)
                    # Append role history event
                    updated_data = pc_manager.append_role_history_event(
                        char_data,
                        action='returned_to_party',
                        from_role='retired_player',
                        to_role='player',
                        source='manage_party_add_character',
                        actor='dm',
                    )
                    if _save_character_data(character_name, updated_data):
                        info(
                            f"TABLETOP: Return lifecycle metadata appended for '{character_name}'",
                            category="tabletop_mode"
                        )
                    else:
                        warning(
                            f"TABLETOP: Failed to save return lifecycle metadata for '{character_name}'",
                            category="tabletop_mode"
                        )
                except Exception as lifecycle_error:
                    warning(
                        f"TABLETOP: Return lifecycle metadata append failed for '{character_name}' (proceeding anyway): {lifecycle_error}",
                        category="tabletop_mode"
                    )

            return jsonify({'success': True, 'partyMembers': party_tracker.get('partyMembers', [])})
        except Exception as route_error:
            error(f"TABLETOP: Failed to add character: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/remove_character', methods=['POST'])
    def remove_party_character() -> Any:
        """Remove character from party (tabletop mode)."""
        try:
            data = request.get_json(silent=True) or {}
            character_name = data.get('character')
            departure_text = data.get('departure_text', '')

            if not character_name:
                return jsonify({'error': 'Character name required'}), 400

            # TABLETOP MODE: Load party state snapshot for guard checks
            party_tracker = pc_manager.get_party_tracker()
            world_conditions = party_tracker.get('worldConditions', {})

            # TABLETOP MODE: Guard - block retirement during active combat
            active_combat = world_conditions.get('activeCombatEncounter', '')
            if active_combat:
                return jsonify({'error': 'Cannot retire character during active combat'}), 400

            # TABLETOP MODE: Guard - block retirement of final party member
            party_members = party_tracker.get('partyMembers', [])
            normalized_target = _normalize_lookup_name(character_name)
            normalized_members = [_normalize_lookup_name(name) for name in party_members]

            if normalized_target in normalized_members:
                # Check if this is the last member
                remaining_after_remove = [
                    name for name in party_members
                    if _normalize_lookup_name(name) != normalized_target
                ]
                if not remaining_after_remove:
                    return jsonify({'error': 'Cannot retire the final party member'}), 400

            # TABLETOP MODE: Snapshot pre-mutation party context for memory continuity
            pre_mutation_tracker = deepcopy(party_tracker)

            # TABLETOP MODE: Persist retirement transition to world memory (fail-open)
            try:
                retirement_result = record_pc_retirement(
                    character_name=character_name,
                    party_tracker=pre_mutation_tracker,
                    departure_text=departure_text
                )
                if retirement_result.get('status') == 'success':
                    info(
                        f"MEMORY_TRANSITION event=retirement character={character_name} status=success event_id={retirement_result.get('event_id')}",
                        category="memory_ingest"
                    )
                else:
                    warning(
                        f"MEMORY_TRANSITION event=retirement character={character_name} status=degraded reason=persistence_error fallback=enabled message={retirement_result.get('message')}",
                        category="memory_ingest"
                    )
            except Exception as memory_error:
                warning(
                    f"MEMORY_TRANSITION event=retirement character={character_name} status=degraded reason=exception fallback=enabled error={memory_error}",
                    category="memory_ingest"
                )

            # TABLETOP MODE: Append retirement lifecycle metadata to character file (fail-open)
            try:
                character_data = _load_character_data(character_name)
                if character_data:
                    updated_data = pc_manager.append_role_history_event(
                        character_data,
                        action='retired_from_party',
                        from_role='player',
                        to_role='retired_player',
                        source='manage_party_remove_character',
                        actor='dm',
                    )
                    if _save_character_data(character_name, updated_data):
                        info(
                            f"TABLETOP: Retirement lifecycle metadata appended for '{character_name}'",
                            category="tabletop_mode"
                        )
                    else:
                        warning(
                            f"TABLETOP: Failed to save retirement lifecycle metadata for '{character_name}'",
                            category="tabletop_mode"
                        )
            except Exception as lifecycle_error:
                warning(
                    f"TABLETOP: Retirement lifecycle metadata append failed for '{character_name}' (proceeding anyway): {lifecycle_error}",
                    category="tabletop_mode"
                )

            success = pc_manager.remove_pc(character_name)
            if not success:
                return jsonify({'error': f"Failed to remove '{character_name}' from party."}), 400

            # TABLETOP MODE: Enqueue retirement narration with farewell vs mysterious branch
            if departure_text and str(departure_text).strip():
                # Explicit farewell provided
                farewell_narration = (
                    f"[SYSTEM] {character_name} is retiring from the party. "
                    f"Their parting words: '{str(departure_text).strip()}'. "
                    f"Please narrate their graceful departure with appropriate NPC reactions."
                )
            else:
                # Mysterious departure (no text provided)
                farewell_narration = (
                    f"[SYSTEM] {character_name} has mysteriously departed from the party. "
                    f"Please narrate their sudden absence with appropriate NPC confusion or concern."
                )
            user_input_queue.put(farewell_narration)

            party_tracker = pc_manager.get_party_tracker()
            return jsonify({'success': True, 'partyMembers': party_tracker.get('partyMembers', [])})
        except Exception as route_error:
            error(f"TABLETOP: Failed to remove character: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/promotion/preview', methods=['POST'])
    def preview_npc_promotion() -> Any:
        """Preview NPC companion promotion to PC without writing state."""
        data = request.get_json(silent=True) or {}
        character_name = str(data.get('character', '')).strip()
        if not character_name:
            return jsonify({'error': 'Character name required'}), 400

        try:
            party_tracker = pc_manager.get_party_tracker()
            npc_names = _party_npc_names(party_tracker)
            normalized_npc_names = {_normalize_lookup_name(name) for name in npc_names}
            normalized_party_members = {
                _normalize_lookup_name(name) for name in party_tracker.get('partyMembers', [])
            }
            normalized_character = _normalize_lookup_name(character_name)

            if normalized_character in normalized_party_members:
                return jsonify({'error': 'Character is already a party member'}), 400
            if normalized_character not in normalized_npc_names:
                return jsonify({'error': 'Character is not a promotable party NPC companion'}), 400

            character_data = _load_character_data(character_name)
            if not character_data:
                error(
                    f"TABLETOP_PROMOTION action=preview character={character_name} status=failed reason=missing_character_file",
                    category="tabletop_mode"
                )
                return jsonify({'error': 'Character data not found'}), 404

            preview_data = deepcopy(character_data)
            had_character_id = bool(str(preview_data.get('character_id', '')).strip())
            pc_manager.ensure_stable_character_id(preview_data)
            pc_manager.normalize_character_role_fields(preview_data, 'player')

            # TABLETOP MODE: Profile readiness for promotion (non-blocking warnings)
            profile_readiness = audit_profile_readiness(preview_data)
            profile_warnings = profile_readiness.get('warnings', [])

            # Legacy readiness for mechanical/schema issues
            readiness = audit_character_readiness(preview_data)
            readiness_warnings = readiness.get('warnings', []) if isinstance(readiness, dict) else []
            
            # Combine warnings: profile first, then mechanical
            warnings = profile_warnings + readiness_warnings

            expected_changes = {
                'character_id': 'unchanged' if had_character_id else 'will_generate',
                'role_fields': {
                    'type': 'player',
                    'character_type': 'player',
                    'character_role': 'player',
                },
                'party_transition': {
                    'remove_from': 'partyNPCs',
                    'add_to': 'partyMembers',
                    'active_character_unchanged': True,
                },
                'lifecycle_event': {
                    'action': 'promoted_to_pc',
                    'from_role': 'npc',
                    'to_role': 'player',
                    'source': 'manage_party_add_existing',
                }
            }

            info(
                f"TABLETOP_PROMOTION action=preview character={character_name} status=success warnings={len(warnings)}",
                category="tabletop_mode"
            )
            return jsonify({
                'success': True,
                'character': {
                    'name': preview_data.get('name', character_name),
                    'level': preview_data.get('level', 1),
                    'class': preview_data.get('class', 'Unknown'),
                    'before_role': 'npc',
                    'after_role': 'player',
                    'character_id': preview_data.get('character_id', ''),
                },
                'expected_changes': expected_changes,
                'warnings': warnings,
                'requires_confirmation': True,
            })
        except Exception as route_error:
            error(
                f"TABLETOP_PROMOTION action=preview character={character_name} status=failed reason={route_error}",
                category="tabletop_mode"
            )
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/promotion/apply', methods=['POST'])
    def apply_npc_promotion() -> Any:
        """Apply confirmed NPC companion promotion to PC."""
        data = request.get_json(silent=True) or {}
        character_name = str(data.get('character', '')).strip()
        confirmed = bool(data.get('confirm', False))

        if not character_name:
            return jsonify({'error': 'Character name required'}), 400
        if not confirmed:
            return jsonify({'error': 'Promotion confirmation required'}), 400

        try:
            party_tracker = pc_manager.get_party_tracker()
            original_active_character = party_tracker.get('active_character', '')

            npc_names = _party_npc_names(party_tracker)
            normalized_npc_names = {_normalize_lookup_name(name) for name in npc_names}
            normalized_party_members = {
                _normalize_lookup_name(name) for name in party_tracker.get('partyMembers', [])
            }
            normalized_character = _normalize_lookup_name(character_name)

            if normalized_character in normalized_party_members:
                return jsonify({'error': 'Character is already a party member'}), 400
            if normalized_character not in normalized_npc_names:
                return jsonify({'error': 'Character is not a promotable party NPC companion'}), 400

            character_data = _load_character_data(character_name)
            if not character_data:
                error(
                    f"TABLETOP_PROMOTION action=apply character={character_name} status=failed reason=missing_character_file",
                    category="tabletop_mode"
                )
                return jsonify({'error': 'Character data not found'}), 404

            updated_data = deepcopy(character_data)
            generated_character_id = not bool(str(updated_data.get('character_id', '')).strip())
            pc_manager.ensure_stable_character_id(updated_data)
            pc_manager.normalize_character_role_fields(updated_data, 'player')
            pc_manager.append_role_history_event(
                updated_data,
                action='promoted_to_pc',
                from_role='npc',
                to_role='player',
                source='manage_party_add_existing',
                actor='dm',
            )

            # TABLETOP MODE: Seed missing appearance keys for low-baggage promotion (11.3)
            updated_data = seed_missing_appearance_fields(updated_data)

            audit_result = audit_character_creation(
                updated_data,
                source='tabletop_npc_promotion_apply',
                enable_enrichment=False,
            )
            if audit_result.result_type == AUDIT_RESULT_SCHEMA_ERROR:
                error(
                    f"TABLETOP_PROMOTION action=apply character={character_name} status=failed reason=schema_validation",
                    category="tabletop_mode"
                )
                return jsonify({
                    'error': 'Promotion blocked by critical validation failure',
                    'result_type': audit_result.result_type,
                    'errors': audit_result.errors,
                    'missing_paths': audit_result.missing_paths,
                }), 400

            # TABLETOP MODE: Profile readiness for promotion (non-blocking warnings) (11.2)
            profile_readiness = audit_profile_readiness(updated_data)
            profile_warnings = profile_readiness.get('warnings', [])

            # Legacy readiness for mechanical/schema issues
            readiness = audit_character_readiness(updated_data)
            readiness_warnings = readiness.get('warnings', []) if isinstance(readiness, dict) else []
            
            # Combine warnings: profile first, then mechanical
            warnings = profile_warnings + readiness_warnings

            if not _save_character_data(character_name, updated_data):
                error(
                    f"TABLETOP_PROMOTION action=apply character={character_name} status=failed reason=character_write_failed",
                    category="tabletop_mode"
                )
                return jsonify({'error': 'Failed to save promoted character data'}), 500

            _remove_npc_entry_by_name(party_tracker, character_name)

            if character_name not in party_tracker.get('partyMembers', []):
                party_tracker.setdefault('partyMembers', []).append(character_name)

            # TABLETOP MODE: Promotion apply should not auto-switch active_character.
            party_tracker['active_character'] = original_active_character

            if not safe_write_json('party_tracker.json', party_tracker):
                error(
                    f"TABLETOP_PROMOTION action=apply character={character_name} status=failed reason=party_tracker_write_failed",
                    category="tabletop_mode"
                )
                return jsonify({'error': 'Failed to save party tracker updates'}), 500

            info(
                f"TABLETOP_PROMOTION action=apply character={character_name} status=success warnings={len(warnings)} generated_character_id={generated_character_id}",
                category="tabletop_mode"
            )
            return jsonify({
                'success': True,
                'character_name': character_name,
                'warnings': warnings,
                'generated_character_id': generated_character_id,
                'active_character': party_tracker.get('active_character', ''),
                'partyMembers': party_tracker.get('partyMembers', []),
            })
        except Exception as route_error:
            error(
                f"TABLETOP_PROMOTION action=apply character={character_name} status=failed reason={route_error}",
                category="tabletop_mode"
            )
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/create_manual', methods=['POST'])
    def create_manual_character() -> Any:
        """Manually create a character from form data and add to party."""
        try:
            data = request.get_json(silent=True) or {}
            name = data.get('name')
            if not name:
                return jsonify({'error': 'Character name is required'}), 400

            new_char_payload = {
                "character_role": "player",
                "character_type": "player",
                "name": name,
                "type": "player",
                "size": "Medium",
                "level": _safe_int(data.get('level', 1), 1),
                "race": data.get('race', 'Human'),
                "class": data.get('class', 'Fighter'),
                "alignment": str(data.get('alignment', 'neutral')).strip().lower(),
                "background": data.get('background', 'Adventurer'),
                "status": "alive",
                "condition": "none",
                "condition_affected": [],
                "hitPoints": _safe_int(data.get('hp', 10), 10),
                "maxHitPoints": _safe_int(data.get('max_hp', data.get('hp', 10)), _safe_int(data.get('hp', 10), 10)),
                "armorClass": _safe_int(data.get('ac', 10), 10),
                "initiative": _safe_int(data.get('initiative', 0), 0),
                "speed": _safe_int(data.get('speed', 30), 30),
                "abilities": {
                    "strength": _safe_int(data.get('str', 10), 10),
                    "dexterity": _safe_int(data.get('dex', 10), 10),
                    "constitution": _safe_int(data.get('con', 10), 10),
                    "intelligence": _safe_int(data.get('int', 10), 10),
                    "wisdom": _safe_int(data.get('wis', 10), 10),
                    "charisma": _safe_int(data.get('cha', 10), 10),
                },
                "savingThrows": _split_csv(data.get('saving_throws', '')),
                "skills": _split_csv(data.get('skills', '')),
                "proficiencyBonus": 2,
                "senses": {"darkvision": 0, "passivePerception": 10},
                "languages": _split_csv(data.get('languages', 'Common')),
                "proficiencies": {
                    "armor": _split_csv(data.get('prof_armor', '')),
                    "weapons": _split_csv(data.get('prof_weapons', '')),
                    "tools": _split_csv(data.get('prof_tools', '')),
                },
                "damageVulnerabilities": [],
                "damageResistances": [],
                "damageImmunities": [],
                "conditionImmunities": [],
                "classFeatures": [],
                "racialTraits": [],
                # TABLETOP MODE: Apply deterministic background feature suggestions for known backgrounds
                # Only fills blank/generic placeholder values, preserves authored input
                "backgroundFeature": (
                    lambda bg, name, desc: {
                        "name": apply_background_feature_suggestion_if_generic(bg, name, desc)["name"],
                        "description": apply_background_feature_suggestion_if_generic(bg, name, desc)["description"],
                        "source": "SRD 5.2.1",
                    }
                )(
                    data.get('background', 'Adventurer'),
                    data.get('background_feature_name', ''),
                    data.get('background_feature_description', '')
                ),
                "temporaryEffects": [],
                "injuries": [],
                "equipment_effects": [],
                "feats": [],
                "equipment": [
                    {
                        "item_name": item_name,
                        "item_type": "equipment",
                        "item_subtype": "other",
                        "description": "Manual entry",
                        "quantity": 1,
                    }
                    for item_name in _split_csv(data.get('equipment', ''))
                ],
                "attacksAndSpellcasting": [
                    {
                        "name": attack_name,
                        "attackBonus": 0,
                        "damageDice": "1d4",
                        "damageBonus": 0,
                        "damageType": "bludgeoning",
                        "type": "melee",
                        "description": "Manual attack entry",
                    }
                    for attack_name in _split_csv(data.get('attacks', ''))
                ],
                "spellcasting": {
                    "ability": data.get('spellcasting_ability', 'none'),
                    "spellSaveDC": _safe_int(data.get('spell_dc', 8), 8),
                    "spellAttackBonus": _safe_int(data.get('spell_attack_bonus', 0), 0),
                    "spells": {
                        "cantrips": _split_csv(data.get('cantrips', '')),
                        "level1": _split_csv(data.get('level1_spells', '')),
                        "level2": [],
                        "level3": [],
                        "level4": [],
                        "level5": [],
                        "level6": [],
                        "level7": [],
                        "level8": [],
                        "level9": [],
                    },
                    "spellSlots": {
                        "level1": {"current": 0, "max": 0},
                        "level2": {"current": 0, "max": 0},
                        "level3": {"current": 0, "max": 0},
                        "level4": {"current": 0, "max": 0},
                        "level5": {"current": 0, "max": 0},
                        "level6": {"current": 0, "max": 0},
                        "level7": {"current": 0, "max": 0},
                        "level8": {"current": 0, "max": 0},
                        "level9": {"current": 0, "max": 0},
                    },
                    "preparedSpells": [],
                },
                "currency": {"gold": 0, "silver": 0, "copper": 0},
                "experience_points": 0,
                "exp_required_for_next_level": 300,
                "personality_traits": data.get('personality_traits', ''),
                "ideals": data.get('ideals', ''),
                "bonds": data.get('bonds', ''),
                "flaws": data.get('flaws', ''),
                "age": data.get('age', ''),
                "height": data.get('height', ''),
                "weight": data.get('weight', ''),
                "eyes": data.get('eyes', ''),
                "skin": data.get('skin', ''),
                "hair": data.get('hair', ''),
            }

            audit_result = audit_character_creation(
                new_char_payload,
                source="tabletop_route_roll_your_own",
                enable_enrichment=True,
            )
            if audit_result.result_type != AUDIT_RESULT_SUCCESS:
                return jsonify({
                    'error': 'Manual character validation failed',
                    'result_type': audit_result.result_type,
                    'errors': audit_result.errors,
                    'missing_paths': audit_result.missing_paths,
                }), 400

            new_char = audit_result.normalized_data

            char_filename = name.lower().replace(' ', '_') + ".json"
            char_path = os.path.join('characters', char_filename)

            if os.path.exists(char_path):
                return jsonify({'error': f'Character file {char_filename} already exists!'}), 400

            success = safe_write_json(char_path, new_char)
            if not success:
                return jsonify({'error': 'Failed to save character file'}), 500

            pc_manager.add_pc(name)

            intro_prompt = pc_manager.get_entrance_prompt(name, new_char, pc_manager.get_party_tracker())
            user_input_queue.put(intro_prompt)

            info(f"TABLETOP: Manually created character {name}")
            return jsonify({'success': True, 'name': name})
        except Exception as route_error:
            error(f"TABLETOP: Failed to create manual character: {route_error}")
            return jsonify({'error': str(route_error)}), 500
