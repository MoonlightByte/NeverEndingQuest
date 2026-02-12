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
from datetime import datetime
from typing import Any

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
    sanitize_character_data,
)
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import error, info, warning
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_path_manager import ModulePathManager


def register_tabletop_party_routes(app: Flask, user_input_queue: Any) -> None:
    """Register TABLETOP MODE party and character creation API routes."""

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
        """List available player characters from global and module paths."""
        try:
            party_tracker = safe_read_json("party_tracker.json") or {}
            current_module = (party_tracker.get("module") or "").replace(" ", "_") or None

            available_characters = []

            def is_player(char_data: dict) -> bool:
                if not char_data:
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
                            available_characters.append({
                                'filename': filename,
                                'name': char_data.get('name', filename.replace('.json', '')),
                                'level': char_data.get('level', 1),
                                'class': char_data.get('class', 'Unknown'),
                                'module_specific': module_specific,
                            })
                    except Exception:
                        continue

            scan_dir('characters', module_specific=False)

            if current_module:
                try:
                    path_manager = ModulePathManager(current_module)
                    scan_dir(path_manager.get_characters_dir(), module_specific=True)
                except Exception:
                    pass

            return jsonify({'characters': available_characters})
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

            character_data = sanitize_character_data(character_json)
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

            success = pc_manager.add_pc(character_name)
            if not success:
                return jsonify({'error': f"Failed to add '{character_name}' to party. Ensure the character file exists."}), 400

            party_tracker = pc_manager.get_party_tracker()

            try:
                char_data = safe_read_json(os.path.join('characters', f"{character_name}.json"))
                if not char_data:
                    char_data = {}
            except Exception:
                char_data = {}

            intro_prompt = pc_manager.get_entrance_prompt(character_name, char_data, party_tracker)
            user_input_queue.put(intro_prompt)

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

            if not character_name:
                return jsonify({'error': 'Character name required'}), 400

            success = pc_manager.remove_pc(character_name)
            if not success:
                return jsonify({'error': f"Failed to remove '{character_name}' from party."}), 400

            party_tracker = pc_manager.get_party_tracker()
            return jsonify({'success': True, 'partyMembers': party_tracker.get('partyMembers', [])})
        except Exception as route_error:
            error(f"TABLETOP: Failed to remove character: {route_error}")
            return jsonify({'error': str(route_error)}), 500

    @app.route('/api/party/create_manual', methods=['POST'])
    def create_manual_character() -> Any:
        """Manually create a character from form data and add to party."""
        try:
            data = request.get_json(silent=True) or {}
            name = data.get('name')
            if not name:
                return jsonify({'error': 'Character name is required'}), 400

            new_char = {
                "character_role": "player",
                "character_type": "player",
                "name": name,
                "type": "player",
                "size": "Medium",
                "level": int(data.get('level', 1)),
                "race": data.get('race', 'Human'),
                "class": data.get('class', 'Fighter'),
                "alignment": data.get('alignment', 'neutral'),
                "background": data.get('background', 'Adventurer'),
                "status": "alive",
                "condition": "none",
                "condition_affected": [],
                "hitPoints": int(data.get('hp', 10)),
                "maxHitPoints": int(data.get('hp', 10)),
                "armorClass": int(data.get('ac', 10)),
                "initiative": int(data.get('initiative', 0)),
                "speed": int(data.get('speed', 30)),
                "abilities": {
                    "strength": int(data.get('str', 10)),
                    "dexterity": int(data.get('dex', 10)),
                    "constitution": int(data.get('con', 10)),
                    "intelligence": int(data.get('int', 10)),
                    "wisdom": int(data.get('wis', 10)),
                    "charisma": int(data.get('cha', 10)),
                },
                "savingThrows": [],
                "skills": [],
                "proficiencyBonus": 2,
                "senses": {"darkvision": 0, "passivePerception": 10},
                "languages": ["Common"],
                "proficiencies": {"armor": [], "weapons": [], "tools": []},
                "damageVulnerabilities": [],
                "damageResistances": [],
                "damageImmunities": [],
                "conditionImmunities": [],
                "classFeatures": [],
                "racialTraits": [],
                "backgroundFeature": {"name": "Feature", "description": "Standard background feature"},
                "temporaryEffects": [],
                "injuries": [],
                "equipment_effects": [],
                "feats": [],
                "equipment": [],
                "attacksAndSpellcasting": [],
                "spellcasting": {
                    "ability": "none",
                    "spellSaveDC": 8,
                    "spellAttackBonus": 0,
                    "spells": {},
                    "spellSlots": {},
                },
                "currency": {"gold": 0, "silver": 0, "copper": 0},
                "experience_points": 0,
                "exp_required_for_next_level": 300,
                "personality_traits": "",
                "ideals": "",
                "bonds": "",
                "flaws": "",
            }

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
