# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# CHARACTER_EFFECTS_VALIDATOR.PY - CHARACTER EFFECTS UPKEEP
# ============================================================================
#
# ARCHITECTURE ROLE: Validation Layer - Character Effects
#
# Runs after a character sheet update; no model is called here. Effects V2
# owns categorization and expiry for a migrated campaign. An unmigrated
# campaign keeps its legacy temporaryEffects where they are until it migrates
# (T050's re-sort was retired in keyword validation V5).
#
# KEY RESPONSIBILITIES:
# - Equipment effects and armor class through the engine's projection
# - Time-based expiry of legacy temporary effects (unmigrated campaigns)
#

"""Character effects upkeep after a sheet update: equipment effects and armor
class, expiry of legacy temporary effects."""

import json
import logging
import copy
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from utils.file_operations import safe_read_json, safe_write_json
from utils.capture.live_provider_call import LiveProviderSuperseded


class AICharacterEffectsValidator:
    def __init__(self, *, commit_guard=None, provider_scope=None, provider_status=None):
        """Initialize AI-powered effects validator"""
        self.commit_guard = commit_guard
        self.provider_scope = provider_scope
        # Optional caller-owned status sink for provider heartbeats (level-up
        # phase reporting); None keeps the ordinary global transport status.
        self.provider_status = provider_status
        self.require_complete = bool(provider_scope is not None and provider_scope.completion_required)
        self.logger = logging.getLogger(__name__)
        self.corrections_made = []
        
    def validate_and_correct_effects(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI-powered validation and correction of character effects
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Corrected character data
        """
        self.corrections_made = []

        # Effects V2 owns categorization and expiry through its classifier and
        # deterministic lifecycle. An unmigrated campaign keeps its legacy
        # temporaryEffects where they are until it migrates (#1128); T050's
        # re-sort is retired (keyword validation V5, owner Q-V4 b).
        try:
            from core.managers.effects_state import campaign_effects_migrated

            if campaign_effects_migrated():
                corrected_data = copy.deepcopy(character_data)
                corrected_data = self.calculate_equipment_effects(corrected_data)
                return corrected_data
        except Exception as exc:
            if self.require_complete:
                raise
            self.logger.warning(
                "Could not determine effects pipeline mode; preserving effects: %s",
                exc,
            )
            return copy.deepcopy(character_data)
        
        # Get current game time from party tracker
        game_time = self.get_current_game_time()
        
        # Step 1: the effect arrays exist
        corrected_data = character_data
        corrected_data.setdefault('injuries', [])
        corrected_data.setdefault('equipment_effects', [])
        
        # Step 2: Calculate equipment effects
        corrected_data = self.calculate_equipment_effects(corrected_data)
        
        # Step 3: Expire outdated temporary effects
        corrected_data = self.expire_temporary_effects(corrected_data, game_time)

        # Use pools come from the SRD tables (raised in calculate_equipment_effects,
        # #704) and a writer's typed usage; none is read from description text
        # (keyword validation V6).
        
        return corrected_data
    
    def get_current_game_time(self) -> Dict[str, Any]:
        """Get current game time from party tracker"""
        try:
            party_data = safe_read_json("party_tracker.json")
            if party_data and 'worldConditions' in party_data:
                world = party_data['worldConditions']
                return {
                    'year': world.get('year', 1492),
                    'month': world.get('month', 'Springmonth'),
                    'day': world.get('day', 1),
                    'time': world.get('time', '00:00:00')
                }
        except Exception as e:
            self.logger.error(f"Could not load game time: {str(e)}")
        
        # Default time if not found
        return {'year': 1492, 'month': 'Springmonth', 'day': 1, 'time': '00:00:00'}
    
    def calculate_equipment_effects(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate equipment effects from equipped items
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with calculated equipment_effects
        """
        equipment_effects = []
        
        # Check all equipped items for effects
        if 'equipment' in character_data:
            for item in character_data['equipment']:
                if item.get('equipped', False) and 'effects' in item:
                    # Add each effect from the equipped item
                    for effect in item['effects']:
                        equipment_effect = {
                            'name': f"{item['item_name']} - {effect.get('type', 'effect').title()}",
                            'type': effect.get('type', 'other'),
                            'target': effect.get('target', ''),
                            'value': effect.get('value'),
                            'description': effect.get('description', ''),
                            'source': item['item_name']
                        }
                        equipment_effects.append(equipment_effect)
        
        # Armor class contributors (shield, fighting style, armor base) are
        # engine-owned: core/nql/armor_class.py rewrites armorClass and the
        # AC-target entries after the prose entries above are collected. The
        # former shield and Fighting Style arithmetic here is retired.
        # Update character data
        character_data['equipment_effects'] = equipment_effects
        
        if len(equipment_effects) > 0:
            self.corrections_made.append(f"Calculated {len(equipment_effects)} equipment effects")

        # Use pools and spell slots below the class table are raised (never
        # lowered, current untouched) before the projection (#704).
        from core.leveling import tables

        for note in tables.raise_to_tables(character_data):
            self.corrections_made.append(note)

        from core.nql import armor_class

        projection = armor_class.project(character_data)
        if projection.applied:
            if projection.changed:
                self.corrections_made.append(
                    f"armorClass {projection.previous_armor_class} -> {projection.armor_class} (engine explanation)")
            ac_entries = [e for e in projection.sheet.get('equipment_effects', []) if e.get('target') == armor_class.AC_TARGET]
            if ac_entries:
                self.corrections_made.append(f"Engine explained {len(ac_entries)} AC contributor(s)")
            return projection.sheet
        self.logger.warning("AC projection left the sheet unchanged: %s", projection.reason)
        return character_data
    
    def expire_temporary_effects(self, character_data: Dict[str, Any], game_time: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove expired temporary effects based on game time
        
        Args:
            character_data: Character JSON data
            game_time: Current game time
            
        Returns:
            Character data with expired effects removed
        """
        if 'temporaryEffects' not in character_data:
            return character_data
        
        current_datetime = self.game_time_to_datetime(game_time)
        active_effects = []
        expired_count = 0
        
        for effect in character_data['temporaryEffects']:
            if 'expiration' in effect:
                try:
                    expiration_dt = datetime.fromisoformat(effect['expiration'].replace('Z', '+00:00'))
                    if expiration_dt > current_datetime:
                        active_effects.append(effect)
                    else:
                        expired_count += 1
                        self.logger.info(f"Expired effect: {effect['name']}")
                except Exception as e:
                    self.logger.warning(f"Could not parse expiration for {effect['name']}: {str(e)}")
                    active_effects.append(effect)
            else:
                # Keep effects without expiration
                active_effects.append(effect)
        
        character_data['temporaryEffects'] = active_effects
        
        if expired_count > 0:
            self.corrections_made.append(f"Removed {expired_count} expired temporary effects")
        
        return character_data
    
    def game_time_to_datetime(self, game_time: Dict[str, Any]) -> datetime:
        """Convert game time to datetime object"""
        # Month conversion (SRD-compliant fantasy calendar)
        month_map = {
            'Firstmonth': 1, 'Coldmonth': 2, 'Thawmonth': 3, 'Springmonth': 4,
            'Bloommonth': 5, 'Sunmonth': 6, 'Heatmonth': 7, 'Harvestmonth': 8,
            'Autumnmonth': 9, 'Fademonth': 10, 'Frostmonth': 11, 'Yearend': 12
        }
        
        month_num = month_map.get(game_time['month'], 4)  # Default to Springmonth
        time_parts = game_time['time'].split(':')
        
        return datetime(
            year=game_time['year'],
            month=month_num,
            day=game_time['day'],
            hour=int(time_parts[0]),
            minute=int(time_parts[1]),
            second=int(time_parts[2]) if len(time_parts) > 2 else 0
        )
    
    def validate_character_effects_safe(self, file_path: str) -> tuple[Dict[str, Any], bool]:
        """
        Validate character effects using atomic file operations
        
        Args:
            file_path: Path to character JSON file
            
        Returns:
            Tuple of (character_data, success_flag)
        """
        try:
            if self.commit_guard is not None:
                with self.commit_guard():
                    pass
            # Load character data
            character_data = safe_read_json(file_path)
            if character_data is None:
                self.logger.error(f"Could not read character file {file_path}")
                return {}, False
            
            # AI validation and correction
            corrected_data = self.validate_and_correct_effects(character_data)
            
            # Save if corrections were made
            if self.corrections_made:
                success = safe_write_json(file_path, corrected_data, commit_guard=self.commit_guard)
                if success:
                    self.logger.info(f"Character effects validated and corrected: {file_path}")
                    return corrected_data, True
                else:
                    self.logger.error(f"Failed to save corrected character data to {file_path}")
                    return character_data, False
            else:
                if self.commit_guard is not None:
                    with self.commit_guard():
                        pass
                self.logger.debug(f"Character effects validated - no corrections needed: {file_path}")
                return corrected_data, True
                
        except Exception as e:
            if self.commit_guard is not None and isinstance(e, LiveProviderSuperseded):
                raise
            self.logger.error(f"Error validating character effects {file_path}: {str(e)}")
            return {}, False


def validate_character_effects(file_path: str) -> bool:
    """
    Convenience function to validate character effects
    
    Args:
        file_path: Path to character JSON file
        
    Returns:
        True if validation successful, False otherwise
    """
    try:
        validator = AICharacterEffectsValidator()
        _, success = validator.validate_character_effects_safe(file_path)
        
        if validator.corrections_made:
            print(f"Effects corrections made: {validator.corrections_made}")
        else:
            print("No effects corrections needed")
            
        return success
        
    except Exception as e:
        print(f"Error validating character effects: {str(e)}")
        return False


if __name__ == "__main__":
    # Test with character file
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        validate_character_effects(file_path)
    else:
        # Test with Norn
        validate_character_effects("modules/Keep_of_Doom/characters/norn.json")
