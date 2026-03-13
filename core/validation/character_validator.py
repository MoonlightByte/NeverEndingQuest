# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Community Tools - Character Validator
Copyright (c) 2024 MoonlightByte
Licensed under Apache License 2.0

See LICENSE-APACHE file for full terms.
"""

# ============================================================================
# CHARACTER_VALIDATOR.PY - AI-POWERED CHARACTER DATA VALIDATION
# ============================================================================
#
# ARCHITECTURE ROLE: AI Integration Layer - Character Data Validation
#
# This module provides intelligent AI-powered character validation ensuring data
# integrity and 5th edition rule compliance through GPT-4 reasoning and validation,
# with automatic correction capabilities for common data inconsistencies.
#
# KEY RESPONSIBILITIES:
# - AI-driven character data validation with 5th edition rule compliance
# - Intelligent armor class calculation verification and correction
# - Inventory item categorization and equipment conflict resolution
# - Currency consolidation preserving player agency over containers
# - Automatic data format standardization and correction
# - Character sheet integrity validation across all character components
# - Integration with character effects validation for comprehensive validation
#

"""
AI-Powered Character Validator

An intelligent validation system that uses AI to ensure character data integrity
based on the 5th edition of the world's most popular role playing game rules.

Uses GPT-4.1 to intelligently validate and auto-correct:
- Armor Class calculations
- Inventory item categorization (prevents arrows as "miscellaneous", etc.)
- Currency consolidation (consolidates loose coins while preserving valuables)
- Equipment conflicts  
- Temporary effects (future)
- Stat bonuses (future)

INVENTORY VALIDATION SYSTEM:
Solves GitHub issue #45 - inconsistent ration storage format across characters.
Two-pronged approach:
1. PREVENTIVE: Enhanced AI prompts prevent future categorization errors
2. CORRECTIVE: AI validation fixes existing miscategorized items

The system uses the same deep merge strategy as the main character updater,
ensuring atomic file operations and preventing data corruption.

The AI reasons through the rules rather than following hardcoded logic,
making it flexible and adaptable to any character structure or edge case.
"""

import json
import copy
import logging
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from openai import OpenAI
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T051", "core/validation/character_validator.py", 963)
register_callsite("T052", "core/validation/character_validator.py", 1049)
register_callsite("T053", "core/validation/character_validator.py", 1625)
register_callsite("T054", "core/validation/character_validator.py", 2015)

CHARACTER_VALIDATOR_SCHEMA = {
    "required": [
        "validated_character_data",
        "corrections_made",
        "ac_calculation_breakdown",
    ],
    "properties": {
        "validated_character_data": {"type": "object"},
        "corrections_made": {"type": "array"},
        "ac_calculation_breakdown": {
            "type": "object",
            "required": [
                "base_armor",
                "dex_modifier",
                "shield_bonus",
                "fighting_style_bonus",
                "total_ac",
            ],
            "properties": {
                "base_armor": {"type": "string"},
                "dex_modifier": {"type": ["string", "integer", "number"]},
                "shield_bonus": {"type": ["string", "integer", "number"]},
                "fighting_style_bonus": {"type": ["string", "integer", "number"]},
                "total_ac": {"type": ["string", "integer", "number"]},
            },
        },
    },
}


def _is_valid_type(value: Any, expected_type: Union[str, list]) -> bool:
    if isinstance(expected_type, list):
        return any(_is_valid_type(value, t) for t in expected_type)

    type_map = {
        "object": dict,
        "dict": dict,
        "array": list,
        "list": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }

    expected_python = type_map.get(expected_type)
    if expected_python is None:
        return True

    if isinstance(expected_python, tuple):
        return isinstance(value, expected_python)
    return isinstance(value, expected_python)


def validate_schema(data: Any, schema: dict, path: str = "root") -> list[str]:
    errors: list[str] = []

    if schema.get("type") and not _is_valid_type(data, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']}, got {type(data).__name__}")

    if not isinstance(data, dict):
        return errors

    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"{path}: missing required field '{field}'")

    for field, subschema in schema.get("properties", {}).items():
        if field in data:
            nested = data[field]
            errors.extend(validate_schema(nested, subschema, f"{path}.{field}"))

    return errors

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass
from config import OPENAI_API_KEY, CHARACTER_VALIDATOR_MODEL
from utils.file_operations import safe_read_json, safe_write_json
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name(__name__)

class AICharacterValidator:
    def __init__(self):
        """Initialize AI-powered validator with caching"""
        self.logger = logging.getLogger(__name__)
        try:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            # Handle OpenAI client initialization error
            error(f"Failed to initialize OpenAI client: {str(e)}", exception=e, category="character_validation")
            error(f"OpenAI client initialization failed. This is likely an environment issue.", category="character_validation")
            error(f"Error details: {type(e).__name__}: {str(e)}", category="character_validation")
            info("Possible solutions:", category="character_validation")
            info("1. Check if OpenAI library is properly installed: pip install openai==1.30.3", category="character_validation")
            info("2. There may be a proxy or environment configuration issue", category="character_validation")
            info("3. Try running in a different environment", category="character_validation")
            raise
        self.corrections_made = []
        
        # Load prompts from external files
        self.ac_prompt = self._load_prompt('character_validator_ac.txt')
        self.inventory_prompt = self._load_prompt('character_validator_inventory.txt')
        
        # Initialize validation cache
        self.cache_file = os.path.join('modules', 'validation_cache.json')
        self.validation_cache = self._load_cache()
    
    def _load_prompt(self, filename: str) -> str:
        """
        Load a prompt from an external file
        
        Args:
            filename: Name of the prompt file
            
        Returns:
            Content of the prompt file
        """
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'prompts', filename)
        
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
                debug(f"Loaded prompt from {filename}: {len(prompt)} characters", category="character_validation")
                return prompt
        except FileNotFoundError:
            error(f"Prompt file not found: {prompt_path}", category="character_validation")
            # Fall back to empty prompt if file not found
            return ""
        except Exception as e:
            error(f"Error loading prompt from {filename}: {str(e)}", category="character_validation")
            return ""
    
    def extract_ac_relevant_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only the fields relevant for AC validation.
        This dramatically reduces token usage from ~7800 to ~500-800.
        
        Based on Gemini consultation, includes all D&D 5e AC-affecting fields:
        - Core context (class, race) for AC rules
        - All ability scores needed for Unarmored Defense
        - Equipment effects array with structured AC data
        - Racial traits and feats that could affect AC
        - Armor proficiencies for validation
        
        Args:
            character_data: Full character JSON data
            
        Returns:
            Minimal data needed for AC validation
        """
        # Start with essential fields including class and race for context
        ac_data = {
            'name': character_data.get('name', 'Unknown'),
            'armorClass': character_data.get('armorClass', 10),
            'class': character_data.get('class', 'Unknown'),  # Critical for Unarmored Defense rules
            'race': character_data.get('race', 'Unknown'),    # Critical for natural armor (Tortle, etc.)
            'abilities': {
                'dexterity': character_data.get('abilities', {}).get('dexterity', 10),
                'constitution': character_data.get('abilities', {}).get('constitution', 10),  # Barbarian Unarmored Defense
                'wisdom': character_data.get('abilities', {}).get('wisdom', 10)  # Monk Unarmored Defense
            }
        }
        
        # Include armor proficiencies to validate proper armor usage
        proficiencies = character_data.get('proficiencies', {})
        if 'armor' in proficiencies:
            ac_data['proficiencies'] = {'armor': proficiencies['armor']}
        
        # Process equipment_effects array - HIGH PRIORITY (structured AC data)
        equipment_effects = character_data.get('equipment_effects', [])
        ac_equipment_effects = []
        for effect in equipment_effects:
            # Include effects that explicitly target AC
            if effect.get('target', '').upper() == 'AC' or 'ac' in effect.get('target', '').lower():
                ac_equipment_effects.append(effect)
        
        if ac_equipment_effects:
            ac_data['equipment_effects'] = ac_equipment_effects
        
        # Filter equipment to only AC-relevant items (refined logic)
        equipment = character_data.get('equipment', [])
        ac_relevant_equipment = []
        
        for item in equipment:
            item_name = item.get('item_name', '').lower()
            item_type = item.get('item_type', '').lower()
            description = item.get('description', '').lower()
            equipped = item.get('equipped', False)
            
            # Include if it's armor, shield, or potentially magical AC item
            include_item = False
            
            # Always include armor and shields
            if item_type == 'armor' or 'armor' in item_name or 'shield' in item_name:
                include_item = True
            
            # Check for explicit AC bonuses in item fields
            elif 'ac_base' in item or 'ac_bonus' in item:
                include_item = True
            
            # Include equipped items with specific AC patterns in description
            elif equipped:
                # Look for explicit AC bonuses like "+1 to AC", "bonus to AC"
                if any(pattern in description for pattern in ['+1 to ac', '+2 to ac', 'bonus to ac', 'armor class']):
                    include_item = True
                # Check known AC-boosting item names
                elif any(ac_item in item_name for ac_item in ['ring of protection', 'cloak of protection', 'bracers of defense']):
                    include_item = True
            
            if include_item:
                # Include all armor-related fields for proper validation
                item_data = {
                    'item_name': item.get('item_name'),
                    'item_type': item.get('item_type'),
                    'equipped': item.get('equipped', False),
                    'description': item.get('description', '')[:200]  # Limit description length
                }
                
                # Include armor-specific fields if present
                for field in ['ac_base', 'ac_bonus', 'dex_limit', 'armor_category', 'stealth_disadvantage']:
                    if field in item:
                        item_data[field] = item[field]
                
                ac_relevant_equipment.append(item_data)
        
        ac_data['equipment'] = ac_relevant_equipment
        
        # Include class features that might affect AC (like Defense fighting style, Unarmored Defense)
        class_features = character_data.get('classFeatures', [])
        ac_relevant_features = []
        
        for feature in class_features:
            feature_name = feature.get('name', '').lower()
            feature_desc = feature.get('description', '').lower()
            # Expanded keywords to catch Unarmored Defense and other AC features
            if any(keyword in feature_name for keyword in ['defense', 'armor', 'ac', 'protection', 'shield', 'unarmored']):
                ac_relevant_features.append(feature)
            # Also check description for AC mentions
            elif any(keyword in feature_desc for keyword in ['armor class', 'ac equal', 'ac bonus']):
                ac_relevant_features.append(feature)
        
        if ac_relevant_features:
            ac_data['classFeatures'] = ac_relevant_features
        
        # Include racial traits (for natural armor like Tortle)
        racial_traits = character_data.get('racialTraits', [])
        ac_relevant_traits = []
        
        for trait in racial_traits:
            trait_name = trait.get('name', '').lower()
            trait_desc = trait.get('description', '').lower()
            if any(keyword in trait_name + trait_desc for keyword in ['armor', 'ac', 'natural armor', 'protection']):
                ac_relevant_traits.append(trait)
        
        if ac_relevant_traits:
            ac_data['racialTraits'] = ac_relevant_traits
        
        # Include feats (for Defensive Duelist, Medium Armor Master, etc.)
        feats = character_data.get('feats', [])
        ac_relevant_feats = []
        
        for feat in feats:
            # If feat is a string, check the name
            if isinstance(feat, str):
                feat_lower = feat.lower()
                if any(keyword in feat_lower for keyword in ['defense', 'armor', 'ac', 'duelist']):
                    ac_relevant_feats.append(feat)
            # If feat is a dict, check name and description
            elif isinstance(feat, dict):
                feat_name = feat.get('name', '').lower()
                feat_desc = feat.get('description', '').lower()
                if any(keyword in feat_name + feat_desc for keyword in ['defense', 'armor', 'ac', 'duelist']):
                    ac_relevant_feats.append(feat)
        
        if ac_relevant_feats:
            ac_data['feats'] = ac_relevant_feats
        
        # Include active effects if present (mage armor, shield spell, etc.)
        active_effects = character_data.get('activeEffects', [])
        if active_effects:
            ac_data['activeEffects'] = active_effects
        
        # Log the reduction
        original_size = len(json.dumps(character_data))
        reduced_size = len(json.dumps(ac_data))
        reduction_pct = (1 - reduced_size/original_size) * 100
        
        debug(f"[AC Extraction] Reduced data from {original_size:,} to {reduced_size:,} chars ({reduction_pct:.1f}% reduction)", category="character_validation")
        debug(f"[AC Extraction] Equipment: {len(equipment)} -> {len(ac_relevant_equipment)} items", category="character_validation")
        debug(f"[AC Extraction] Equipment effects: {len(equipment_effects)} -> {len(ac_equipment_effects)} AC-relevant", category="character_validation")
        debug(f"[AC Extraction] Included: {len(ac_relevant_features)} class features, {len(ac_relevant_traits)} racial traits, {len(ac_relevant_feats)} feats", category="character_validation")
        
        return ac_data
    
    def extract_inventory_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only inventory-relevant data for validation.
        Focus on items that commonly have categorization issues.
        
        Based on Gemini consultation:
        - Check equipment items that might be miscategorized as miscellaneous
        - Exclude high-confidence miscellaneous items
        - Include ambiguous items like scrolls regardless of type
        
        Args:
            character_data: Full character JSON data
            
        Returns:
            Minimal data needed for inventory validation
        """
        inventory_data = {
            'name': character_data.get('name', 'Unknown'),
            'equipment': []
        }
        
        equipment = character_data.get('equipment', [])
        
        # Filter to items most likely to need validation
        for item in equipment:
            item_name = item.get('item_name', '').lower()
            item_type = item.get('item_type', '').lower()
            description = item.get('description', '').lower()
            
            include = False
            
            # 1. Check miscellaneous items (but exclude high-confidence ones)
            if item_type == 'miscellaneous':
                # Exclude items that are almost certainly correct miscellaneous
                high_confidence_misc = ['gemstone', 'coin', 'gold', 'silver', 'copper', 
                                       'signet', 'deed', 'letter', 'page', 'parchment',
                                       'medallion', 'brooch', 'locket', 'chalice', 'goblet',
                                       'crown', 'ingot', 'relic']
                
                # Don't validate if it's a high-confidence miscellaneous item
                if not any(keyword in item_name for keyword in high_confidence_misc):
                    # But DO include if it might be something else
                    if any(keyword in item_name for keyword in ['arrow', 'bolt', 'bullet', 'dart']):
                        include = True  # Likely ammunition
                    elif any(keyword in item_name for keyword in ['ration', 'food', 'bread', 'meat', 'potion', 'scroll', 'elixir']):
                        include = True  # Likely consumable
                    elif any(keyword in item_name for keyword in ['torch', 'rope', 'tools', 'kit', 'pack', 'bedroll', 'tent']):
                        include = True  # Likely equipment
                    else:
                        # Include other miscellaneous for review (but not high-confidence ones)
                        include = True
            
            # 2. Check equipment items that might be miscellaneous (rings, amulets, etc)
            elif item_type == 'equipment':
                # These are often miscategorized as equipment when they should be miscellaneous
                if any(keyword in item_name for keyword in ['ring', 'amulet', 'talisman', 'symbol', 'pendant', 'necklace']):
                    include = True  # Often should be miscellaneous
                # Check for scrolls which are ambiguous
                elif 'scroll' in item_name:
                    include = True  # Could be consumable or equipment
                # Include items with special/magical effects that might be miscellaneous
                elif any(keyword in description for keyword in ['summon', 'magical', 'enchanted', 'artifact']):
                    include = True  # Might be miscellaneous
            
            # 3. Check weapons that might be ammunition
            elif item_type == 'weapon' and any(keyword in item_name for keyword in ['arrow', 'bolt', 'bullet', 'dart']):
                include = True  # Ammunition miscategorized as weapon
            
            # 4. Check for consumables miscategorized as other types
            elif item_type != 'consumable' and any(keyword in item_name for keyword in ['potion', 'elixir', 'ration', 'food', 'water', 'ale', 'wine']):
                include = True  # Should be consumable
            
            # 5. Check for equipment miscategorized as other types  
            elif item_type != 'equipment' and any(keyword in item_name for keyword in ['rope', 'torch', 'lantern', 'tools', 'kit', 'pack', 'bedroll', 'tent', 'map']):
                include = True  # Should be equipment
            
            # 6. Always check items with "scroll" regardless of current type (ambiguous)
            elif 'scroll' in item_name:
                include = True  # Scrolls are ambiguous - could be consumable or equipment/misc
            
            if include:
                # Only include necessary fields
                inventory_data['equipment'].append({
                    'item_name': item.get('item_name'),
                    'item_type': item.get('item_type'),
                    'description': item.get('description', '')[:150],  # Slightly longer for context
                    'quantity': item.get('quantity', 1)
                })
        
        # Log the reduction
        original_count = len(equipment)
        filtered_count = len(inventory_data['equipment'])
        
        debug(f"[Inventory Extraction] Filtered items from {original_count} to {filtered_count} for validation", category="character_validation")
        
        return inventory_data
    
    def extract_currency_consolidation_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only items relevant for currency and ammunition consolidation.
        Focus on items that might be loose coins or ammunition to consolidate.
        
        Enhanced based on Gemini consultation:
        - Expanded exclusion list for false positives
        - Added locked/sealed container detection
        - Improved container keywords
        - Consolidated ammunition checks
        
        Args:
            character_data: Full character JSON data
            
        Returns:
            Minimal data needed for consolidation validation
        """
        consolidation_data = {
            'name': character_data.get('name', 'Unknown'),
            'currency': character_data.get('currency', {}),
            'ammunition': character_data.get('ammunition', []),
            'equipment': []
        }
        
        equipment = character_data.get('equipment', [])
        
        # Filter to items that might need consolidation
        for item in equipment:
            item_name = item.get('item_name', '').lower()
            item_type = item.get('item_type', '').lower()
            description = item.get('description', '').lower()
            
            include = False
            
            # Skip locked/sealed containers upfront (Gemini recommendation)
            if any(lock_word in item_name for lock_word in ['locked', 'sealed', 'trapped']):
                continue  # Skip this item entirely
            
            # 1. Check for loose currency items
            currency_keywords = ['coin', 'gold', 'silver', 'copper', 'platinum', 'electrum', 
                               'gp', 'sp', 'cp', 'pp', 'ep', 'piece', 'pieces']
            if any(keyword in item_name for keyword in currency_keywords):
                # Expanded exclusion list based on Gemini's recommendations
                exclude_valuables = ['ring', 'medallion', 'necklace', 'brooch', 'crown', 
                                   'goblet', 'chalice', 'whistle', 'mirror', 'ingot', 
                                   'flask', 'reliquary', 'icon', 'locket', 'statue',
                                   'pendant', 'amulet', 'jewel', 'gem', 'pearl']
                if not any(exclude in item_name for exclude in exclude_valuables):
                    # Also check if description indicates it's a valuable (not loose coins)
                    if not any(value_phrase in description for value_phrase in ['valued at', 'worth', 'value of']):
                        include = True
            
            # 2. Check for bags/pouches that might contain coins
            # Added 'coinpurse' per Gemini's recommendation
            elif any(container in item_name for container in ['bag', 'pouch', 'purse', 'sack', 'coinpurse']):
                # Only if not locked/sealed (already filtered above) and mentions coins
                if any(curr in description for curr in ['coin', 'gold', 'silver', 'copper', 'gp', 'sp', 'cp']):
                    include = True
            
            # 3. Consolidated ammunition check (Gemini recommendation)
            # Check both name and description in one pass
            ammo_keywords = ['arrow', 'bolt', 'bullet', 'dart', 'shot', 'quiver', 
                           'case', 'sling', 'stone', 'needle', 'ammunition', 'projectile']
            if not include:  # Only check if not already included
                if any(keyword in item_name for keyword in ammo_keywords):
                    include = True
                elif any(keyword in description for keyword in ammo_keywords):
                    include = True
            
            if include:
                # Only include necessary fields
                consolidation_data['equipment'].append({
                    'item_name': item.get('item_name'),
                    'item_type': item.get('item_type'),
                    'description': item.get('description', ''),  # Full description needed for parsing amounts
                    'quantity': item.get('quantity', 1)
                })
        
        # Log the reduction
        original_count = len(equipment)
        filtered_count = len(consolidation_data['equipment'])
        
        debug(f"[Currency Extraction] Filtered items from {original_count} to {filtered_count} for consolidation", category="character_validation")
        
        return consolidation_data
    
    def _load_cache(self) -> Dict[str, Any]:
        """
        Load validation cache from file
        
        Returns:
            Cache dictionary or empty dict if not found
        """
        if os.path.exists(self.cache_file):
            cache = safe_read_json(self.cache_file)
            if cache:
                debug(f"[Validation Cache] Loaded cache with {len(cache)} entries", category="character_validation")
                return cache
        return {}
    
    def _save_cache(self):
        """Save validation cache to file"""
        try:
            safe_write_json(self.cache_file, self.validation_cache)
            debug(f"[Validation Cache] Saved cache with {len(self.validation_cache)} entries", category="character_validation")
        except Exception as e:
            error(f"Failed to save validation cache: {str(e)}", category="character_validation")
    
    def _compute_ac_hash(self, ac_data: Dict[str, Any]) -> str:
        """
        Compute a hash of AC-relevant data for caching
        
        Args:
            ac_data: AC-relevant data extracted from character
            
        Returns:
            SHA-256 hash of the data
        """
        # Create a stable JSON representation for hashing
        json_str = json.dumps(ac_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _is_ac_validation_cached(self, character_name: str, ac_hash: str) -> bool:
        """
        Check if AC validation is cached and still valid
        
        Args:
            character_name: Name of the character
            ac_hash: Hash of current AC-relevant data
            
        Returns:
            True if cached and unchanged, False otherwise
        """
        if character_name not in self.validation_cache:
            return False
        
        cache_entry = self.validation_cache[character_name]
        
        # Check if AC data has changed
        if cache_entry.get('ac_hash') != ac_hash:
            debug(f"[Validation Cache] AC data changed for {character_name}", category="character_validation")
            return False
        
        # Check if cache is still fresh (optional: add time-based expiry)
        # For now, we'll keep cache valid indefinitely until data changes
        
        debug(f"[Validation Cache] Using cached AC validation for {character_name}", category="character_validation")
        return True
    
    def _update_ac_cache(self, character_name: str, ac_hash: str, validated_data: Dict[str, Any]):
        """
        Update cache with new AC validation results
        
        Args:
            character_name: Name of the character
            ac_hash: Hash of AC-relevant data
            validated_data: Validated character data
        """
        if character_name not in self.validation_cache:
            self.validation_cache[character_name] = {}
        
        self.validation_cache[character_name].update({
            'ac_hash': ac_hash,
            'last_ac_validation': datetime.now().isoformat(),
            'ac_value': validated_data.get('armorClass', 10)
        })
        
        self._save_cache()
        debug(f"[Validation Cache] Updated AC cache for {character_name}", category="character_validation")
    
    def _compute_inventory_hash(self, inventory_data: Dict[str, Any]) -> str:
        """
        Compute a hash of inventory data for caching
        
        Args:
            inventory_data: Inventory-relevant data extracted from character
            
        Returns:
            SHA-256 hash of the data
        """
        # Create a stable JSON representation for hashing
        json_str = json.dumps(inventory_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _is_inventory_validation_cached(self, character_name: str, inventory_hash: str) -> bool:
        """
        Check if inventory validation is cached and still valid
        
        Args:
            character_name: Name of the character
            inventory_hash: Hash of current inventory data
            
        Returns:
            True if cached and unchanged, False otherwise
        """
        if character_name not in self.validation_cache:
            return False
        
        cache_entry = self.validation_cache[character_name]
        
        # Check if inventory data has changed
        if cache_entry.get('inventory_hash') != inventory_hash:
            debug(f"[Validation Cache] Inventory data changed for {character_name}", category="character_validation")
            return False
        
        debug(f"[Validation Cache] Using cached inventory validation for {character_name}", category="character_validation")
        return True
    
    def _update_inventory_cache(self, character_name: str, inventory_hash: str):
        """
        Update cache with new inventory validation results
        
        Args:
            character_name: Name of the character
            inventory_hash: Hash of inventory data
        """
        if character_name not in self.validation_cache:
            self.validation_cache[character_name] = {}
        
        self.validation_cache[character_name].update({
            'inventory_hash': inventory_hash,
            'last_inventory_validation': datetime.now().isoformat()
        })
        
        self._save_cache()
        debug(f"[Validation Cache] Updated inventory cache for {character_name}", category="character_validation")
    
    def _compute_currency_hash(self, consolidation_data: Dict[str, Any]) -> str:
        """
        Compute a hash of currency consolidation data for caching
        
        Args:
            consolidation_data: Currency-relevant data extracted from character
            
        Returns:
            SHA-256 hash of the data
        """
        # Create a stable JSON representation for hashing
        json_str = json.dumps(consolidation_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _is_currency_validation_cached(self, character_name: str, currency_hash: str) -> bool:
        """
        Check if currency consolidation is cached and still valid
        
        Args:
            character_name: Name of the character
            currency_hash: Hash of current currency consolidation data
            
        Returns:
            True if cached and unchanged, False otherwise
        """
        if character_name not in self.validation_cache:
            return False
        
        cache_entry = self.validation_cache[character_name]
        
        # Check if currency data has changed
        if cache_entry.get('currency_hash') != currency_hash:
            debug(f"[Validation Cache] Currency data changed for {character_name}", category="character_validation")
            return False
        
        debug(f"[Validation Cache] Using cached currency consolidation for {character_name}", category="character_validation")
        return True
    
    def _update_currency_cache(self, character_name: str, currency_hash: str):
        """
        Update cache with new currency consolidation results
        
        Args:
            character_name: Name of the character
            currency_hash: Hash of currency consolidation data
        """
        if character_name not in self.validation_cache:
            self.validation_cache[character_name] = {}
        
        self.validation_cache[character_name].update({
            'currency_hash': currency_hash,
            'last_currency_validation': datetime.now().isoformat()
        })
        
        self._save_cache()
        debug(f"[Validation Cache] Updated currency cache for {character_name}", category="character_validation")
        
    def validate_and_correct_character(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI-powered validation and correction of character data
        
        Args:
            character_data: Character JSON data
            
        Returns:
            AI-corrected character data with proper AC calculation
        """
        self.corrections_made = []
        
        # Log activation message for user visibility in debug window
        character_name = character_data.get('name', 'Unknown')
        # Use print for immediate visibility in debug tab
        print(f"DEBUG: [AI Validator] Activating character validator for {character_name}...")
        info(f"[AI Validator] Activating character validator for {character_name}...", category="character_validation")
        
        # OPTIMIZATION: Batch all validations into a single AI call
        corrected_data = self.ai_validate_all_batched(character_data)
        
        # Validate status-condition consistency (non-AI validation)
        corrected_data = self.validate_status_condition_consistency(corrected_data)
        
        # CRITICAL: Ensure currency object always has all required fields
        corrected_data = self.ensure_currency_integrity(corrected_data)
        
        # CRITICAL: Consolidate duplicate ammunition entries (exact matches only)
        corrected_data = self.consolidate_ammunition(corrected_data)
        
        # Future: Add other AI validations here
        # - Temporary effects expiration  
        # - Attack bonus calculation
        # - Saving throw bonuses
        
        # Log completion message
        if self.corrections_made:
            print(f"DEBUG: [AI Validator] Character validation complete for {character_name}: {len(self.corrections_made)} corrections made")
            info(f"[AI Validator] Character validation complete for {character_name}: {len(self.corrections_made)} corrections made", category="character_validation")
            for correction in self.corrections_made:
                print(f"DEBUG:   - {correction}")
                info(f"  - {correction}", category="character_validation")
        else:
            print(f"DEBUG: [AI Validator] Character validation complete for {character_name}: No corrections needed")
            info(f"[AI Validator] Character validation complete for {character_name}: No corrections needed", category="character_validation")
        
        return corrected_data
    
    def check_validation_needs(self, character_data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check which validations actually need API calls (not cached)
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Dictionary indicating which validations need API calls
        """
        character_name = character_data.get('name', 'Unknown')
        needs_validation = {
            'ac': False,
            'inventory': False,
            'currency': False,
            'class_features': False  # Always validate for now (no caching yet)
        }
        
        # Extract data for each validator
        ac_data = self.extract_ac_relevant_data(character_data)
        ac_hash = self._compute_ac_hash(ac_data)
        
        inventory_data = self.extract_inventory_data(character_data)
        inventory_hash = self._compute_inventory_hash(inventory_data)
        
        currency_data = self.extract_currency_consolidation_data(character_data)
        currency_hash = self._compute_currency_hash(currency_data)
        
        # Check cache for each
        if not self._is_ac_validation_cached(character_name, ac_hash):
            needs_validation['ac'] = True
            debug(f"[Smart Batch] {character_name} needs AC validation", category="character_validation")
        
        if len(inventory_data['equipment']) > 0 and not self._is_inventory_validation_cached(character_name, inventory_hash):
            needs_validation['inventory'] = True
            debug(f"[Smart Batch] {character_name} needs inventory validation", category="character_validation")
        
        if len(currency_data['equipment']) > 0 and not self._is_currency_validation_cached(character_name, currency_hash):
            needs_validation['currency'] = True
            debug(f"[Smart Batch] {character_name} needs currency validation", category="character_validation")
        
        # Class features don't have caching yet, always validate if batched
        needs_validation['class_features'] = False  # Disable for now unless specifically needed
        
        return needs_validation
    
    def validate_and_correct_character_smart(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Smart validation that only calls validators that need updates

        Args:
            character_data: Character JSON data

        Returns:
            AI-corrected character data
        """
        character_name = character_data.get('name', 'Unknown')
        info(f"[Smart Validator] Checking {character_name} for needed validations...", category="character_validation")

        # Check what needs validation
        needs = self.check_validation_needs(character_data)

        # Count how many validations are needed
        needed_count = sum(1 for v in needs.values() if v)

        if needed_count == 0:
            print(f"DEBUG: [Smart Validator] {character_name} - All validations cached, skipping API calls")
            info(f"[Smart Validator] {character_name} - All validations cached, skipping API calls", category="character_validation")
            # When validation is cached, return character data unchanged
            # This preserves all current values including HP, spell slots, etc.
            return character_data

        print(f"DEBUG: [Smart Validator] {character_name} needs {needed_count} validation(s)")
        info(f"[Smart Validator] {character_name} needs {needed_count} validation(s)", category="character_validation")
        
        # Apply only needed validations
        corrected_data = character_data
        
        if needs['ac']:
            corrected_data = self.ai_validate_armor_class(corrected_data)
        
        if needs['inventory']:
            corrected_data = self.ai_validate_inventory_categories(corrected_data)
        
        if needs['currency']:
            corrected_data = self.ai_consolidate_inventory(corrected_data)
        
        # Non-AI validations (always run, they're fast)
        corrected_data = self.validate_status_condition_consistency(corrected_data)
        corrected_data = self.ensure_currency_integrity(corrected_data)
        corrected_data = self.consolidate_ammunition(corrected_data)
        
        return corrected_data
    
    def validate_multiple_characters_smart(self, character_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate multiple characters with smart batching based on cache status
        Only creates batches for validators that need API calls
        
        Args:
            character_list: List of character data dictionaries
            
        Returns:
            List of validated character data
        """
        if not character_list:
            return []
        
        info(f"[Smart Batch] Processing {len(character_list)} characters", category="character_validation")
        
        # Group characters by validation needs
        validation_batches = {
            'ac': [],
            'inventory': [],
            'currency': []
        }
        
        # Track which characters need which validations
        character_needs = {}
        
        for character in character_list:
            char_name = character.get('name', 'Unknown')
            needs = self.check_validation_needs(character)
            character_needs[char_name] = needs
            
            # Add to appropriate batches
            if needs['ac']:
                validation_batches['ac'].append(character)
            if needs['inventory']:
                validation_batches['inventory'].append(character)
            if needs['currency']:
                validation_batches['currency'].append(character)
        
        # Report batch sizes
        info(f"[Smart Batch] AC batch: {len(validation_batches['ac'])} characters", category="character_validation")
        info(f"[Smart Batch] Inventory batch: {len(validation_batches['inventory'])} characters", category="character_validation")
        info(f"[Smart Batch] Currency batch: {len(validation_batches['currency'])} characters", category="character_validation")
        
        # Process batches (could be parallelized in future)
        results = {}
        
        # Batch AC validations
        if validation_batches['ac']:
            info(f"[Smart Batch] Processing AC validations for {len(validation_batches['ac'])} characters", category="character_validation")
            for character in validation_batches['ac']:
                char_name = character.get('name', 'Unknown')
                validated = self.ai_validate_armor_class(character)
                results[char_name] = validated
        
        # Batch inventory validations
        if validation_batches['inventory']:
            info(f"[Smart Batch] Processing inventory validations for {len(validation_batches['inventory'])} characters", category="character_validation")
            for character in validation_batches['inventory']:
                char_name = character.get('name', 'Unknown')
                # Use existing result if already validated, otherwise use original
                base_data = results.get(char_name, character)
                validated = self.ai_validate_inventory_categories(base_data)
                results[char_name] = validated
        
        # Batch currency validations
        if validation_batches['currency']:
            info(f"[Smart Batch] Processing currency validations for {len(validation_batches['currency'])} characters", category="character_validation")
            for character in validation_batches['currency']:
                char_name = character.get('name', 'Unknown')
                # Use existing result if already validated, otherwise use original
                base_data = results.get(char_name, character)
                validated = self.ai_consolidate_inventory(base_data)
                results[char_name] = validated
        
        # Apply non-AI validations to all characters
        final_results = []
        for character in character_list:
            char_name = character.get('name', 'Unknown')
            
            # Use validated version if exists, otherwise original
            char_data = results.get(char_name, character)
            
            # Always apply non-AI validations
            char_data = self.validate_status_condition_consistency(char_data)
            char_data = self.ensure_currency_integrity(char_data)
            char_data = self.consolidate_ammunition(char_data)
            
            final_results.append(char_data)
        
        # Report savings
        total_possible = len(character_list) * 3  # 3 validators per character
        total_called = len(validation_batches['ac']) + len(validation_batches['inventory']) + len(validation_batches['currency'])
        total_skipped = total_possible - total_called
        
        print(f"DEBUG: [Smart Batch] Complete: {total_called}/{total_possible} API calls made ({total_skipped} skipped due to caching)")
        info(f"[Smart Batch] Complete: {total_called}/{total_possible} API calls made ({total_skipped} skipped due to caching)", category="character_validation")
        
        return final_results
    
    def ai_validate_armor_class(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to validate and correct Armor Class calculation with caching
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with AI-corrected AC (from cache if unchanged)
        """
        
        # Extract only AC-relevant data to reduce tokens
        ac_relevant_data = self.extract_ac_relevant_data(character_data)
        
        # Compute hash of AC-relevant data
        character_name = character_data.get('name', 'Unknown')
        ac_hash = self._compute_ac_hash(ac_relevant_data)
        
        # Check if validation is cached and unchanged
        if self._is_ac_validation_cached(character_name, ac_hash):
            # Return original data - no changes needed since cached validation passed
            print(f"DEBUG: [Validation Cache] Skipping AC validation for {character_name} - data unchanged")
            info(f"[Validation Cache] Skipping AC validation for {character_name} - data unchanged", category="character_validation")
            
            # Log cache hit statistics
            if character_name in self.validation_cache:
                cache_entry = self.validation_cache[character_name]
                debug(f"[Validation Cache] Last validated: {cache_entry.get('last_ac_validation')}", category="character_validation")
                debug(f"[Validation Cache] Cached AC value: {cache_entry.get('ac_value')}", category="character_validation")
            
            return character_data
        
        # Data has changed or not cached - perform validation
        print(f"DEBUG: [Validation Cache] Running AC validation for {character_name} - new/changed data")
        info(f"[Validation Cache] Running AC validation for {character_name} - new/changed data", category="character_validation")
        validation_prompt = self.build_ac_validation_prompt(ac_relevant_data)
        
        try:
            response = capture_and_fanout("T051", self.client.chat.completions.create, messages=[
                    {"role": "system", "content": self.get_validator_system_prompt()},
                    {"role": "user", "content": validation_prompt}
                ], model=CHARACTER_VALIDATOR_MODEL, temperature=0.1)

            # Track usage if available
            if USAGE_TRACKING_AVAILABLE:
                try:
                    from utils.openai_usage_tracker import get_global_tracker
                    tracker = get_global_tracker()
                    tracker.track(response, context={'endpoint': 'character_validation', 'purpose': 'validate_character_data'})
                except:
                    pass

            ai_response = response.choices[0].message.content.strip()

            # Parse AI response to get corrected character data
            corrected_data = self.parse_ai_validation_response(ai_response, ac_relevant_data)

            # CRITICAL FIX: Merge the corrections into original data, don't replace!
            # The AI only returns the extracted subset with corrections
            # We need to merge those corrections back into the full character data
            from updates.update_character_info import deep_merge_dict
            merged_data = deep_merge_dict(character_data, corrected_data)

            # Update cache with new validation results
            self._update_ac_cache(character_name, ac_hash, merged_data)

            return merged_data
            
        except Exception as e:
            self.logger.error(f"AI validation failed: {str(e)}")
            return character_data
    
    def ai_validate_inventory_categories(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to validate and correct inventory item categorization with caching
        Following the main character updater pattern: return only changes, use deep merge
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with AI-corrected inventory categories (from cache if unchanged)
        """
        
        # Extract only inventory data that needs validation
        inventory_data = self.extract_inventory_data(character_data)
        
        # Compute hash of inventory data
        character_name = character_data.get('name', 'Unknown')
        inventory_hash = self._compute_inventory_hash(inventory_data)
        
        # Check if validation is cached and unchanged
        if self._is_inventory_validation_cached(character_name, inventory_hash):
            # Return original data - no changes needed since cached validation passed
            print(f"DEBUG: [Validation Cache] Skipping inventory validation for {character_name} - data unchanged")
            info(f"[Validation Cache] Skipping inventory validation for {character_name} - data unchanged", category="character_validation")
            
            # Log cache hit statistics
            if character_name in self.validation_cache:
                cache_entry = self.validation_cache[character_name]
                debug(f"[Validation Cache] Last validated: {cache_entry.get('last_inventory_validation')}", category="character_validation")
            
            return character_data
        
        # If no items need validation, skip API call
        if len(inventory_data['equipment']) == 0:
            print(f"DEBUG: [Inventory Validation] No suspicious items found for {character_name} - skipping validation")
            info(f"[Inventory Validation] No suspicious items found for {character_name} - skipping validation", category="character_validation")
            # Update cache to avoid checking again
            self._update_inventory_cache(character_name, inventory_hash)
            return character_data
        
        # Data has changed or not cached - perform validation
        print(f"DEBUG: [Validation Cache] Running inventory validation for {character_name} - {len(inventory_data['equipment'])} items to check")
        info(f"[Validation Cache] Running inventory validation for {character_name} - {len(inventory_data['equipment'])} items to check", category="character_validation")
        
        max_attempts = 3
        attempt = 1
        
        while attempt <= max_attempts:
            try:
                # Build prompt with filtered inventory data
                validation_prompt = self.build_inventory_validation_prompt(inventory_data)
                
                response = capture_and_fanout("T052", self.client.chat.completions.create, messages=[
                        {"role": "system", "content": self.get_inventory_validator_system_prompt()},
                        {"role": "user", "content": validation_prompt}
                    ], model=CHARACTER_VALIDATOR_MODEL, temperature=0.1)
                
                # Track usage if available
                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(response, context={'endpoint': 'character_validation', 'purpose': 'validate_character_effects'})
                    except:
                        pass
                
                ai_response = response.choices[0].message.content.strip()
                
                # Parse AI response to get inventory updates only
                inventory_updates = self.parse_inventory_validation_response(ai_response, character_data)
                
                # Update cache with validation results
                self._update_inventory_cache(character_name, inventory_hash)
                
                if inventory_updates:
                    # Apply updates using deep merge (same pattern as main character updater)
                    from updates.update_character_info import deep_merge_dict
                    corrected_data = deep_merge_dict(character_data, inventory_updates)
                    return corrected_data
                else:
                    # No changes needed
                    return character_data
                    
            except Exception as e:
                self.logger.error(f"AI inventory validation attempt {attempt} failed: {str(e)}")
                attempt += 1
                if attempt > max_attempts:
                    self.logger.error(f"All {max_attempts} inventory validation attempts failed")
                    return character_data
        
        return character_data
    
    def get_validator_system_prompt(self) -> str:
        """
        Comprehensive system prompt for AI character validation
        
        Returns:
            System prompt with 5th edition rules and examples
        """
        # Return cached prompt loaded from file
        if self.ac_prompt:
            return self.ac_prompt
        
        # Fallback to hardcoded prompt if file loading failed
        return """You are an expert character validator for the 5th edition of the world's most popular role playing game. Your job is to validate and correct character data to ensure it follows the rules accurately.

## PRIMARY TASK: ARMOR CLASS VALIDATION

You must validate that the character's Armor Class (AC) is calculated correctly based on their equipped items and apply corrections as needed.

## 5TH EDITION ARMOR CLASS RULES

### Base Armor AC Values:
**Light Armor** (AC = Base + Dex modifier, no limit):
- Padded: 11 AC
- Leather: 11 AC  
- Studded Leather: 12 AC

**Medium Armor** (AC = Base + Dex modifier, max +2):
- Hide: 12 AC
- Chain Shirt: 13 AC
- Scale Mail: 14 AC (stealth disadvantage)
- Breastplate: 14 AC
- Half Plate: 15 AC (stealth disadvantage)

**Heavy Armor** (AC = Base only, no Dex bonus):
- Ring Mail: 14 AC (stealth disadvantage)
- Chain Mail: 16 AC (stealth disadvantage)
- Splint: 17 AC (stealth disadvantage)  
- Plate: 18 AC (stealth disadvantage)

**Shields**: +2 AC when equipped

### AC Calculation Formula:
AC = Base Armor + Dex Modifier (limited by armor type) + Shield Bonus + Fighting Style Bonus + Other Bonuses

### Fighting Style Bonuses:
- **Defense**: +1 AC when wearing any armor
- All other fighting styles: No AC bonus

### Equipment Rules:
- Only ONE base armor piece can be equipped
- Only ONE shield can be equipped
- Multiple armor pieces of same type = conflict (keep highest AC)

## VALIDATION EXAMPLES

### Example 1: Fighter with Chain Mail and Shield
```json
Character Data:
{
  "armorClass": 15,
  "abilities": {"dexterity": 14},
  "classFeatures": [{"name": "Fighting Style: Defense"}],
  "equipment": [
    {"item_name": "Chain Mail", "item_type": "armor", "equipped": true},
    {"item_name": "Shield", "item_type": "armor", "equipped": true}
  ]
}

Calculation:
- Chain Mail: 16 AC (heavy armor, no Dex bonus)
- Shield: +2 AC  
- Defense Fighting Style: +1 AC (wearing armor)
- Correct AC: 16 + 0 + 2 + 1 = 19

Correction Needed: AC should be 19, not 15
```

### Example 2: Rogue with Studded Leather
```json
Character Data:
{
  "armorClass": 14,
  "abilities": {"dexterity": 16},
  "equipment": [
    {"item_name": "Studded Leather", "item_type": "armor", "equipped": true}
  ]
}

Calculation:
- Studded Leather: 12 AC (light armor)
- Dex Modifier: +3 (16 Dex, no limit for light armor)
- Correct AC: 12 + 3 = 15

Correction Needed: AC should be 15, not 14
```

### Example 3: Equipment Conflict Resolution
```json
Character Data:
{
  "equipment": [
    {"item_name": "Chain Mail", "item_type": "armor", "equipped": true},
    {"item_name": "Scale Mail", "item_type": "armor", "equipped": true}
  ]
}

Problem: Two base armor pieces equipped
Solution: Keep Chain Mail (16 AC), unequip Scale Mail (14 AC)
```

## RESPONSE FORMAT

You must respond with a JSON object containing:

```json
{
  "validated_character_data": {
    // Complete corrected character data with proper AC
  },
  "corrections_made": [
    "List of specific corrections made"
  ],
  "ac_calculation_breakdown": {
    "base_armor": "Name and AC value",
    "dex_modifier": "Value applied", 
    "shield_bonus": "Value applied",
    "fighting_style_bonus": "Value applied",
    "total_ac": "Final calculated AC"
  }
}
```

## INSTRUCTIONS

1. **Analyze the character data** to identify all equipped armor and relevant bonuses
2. **Auto-populate missing armor properties** using the reference table above
3. **Resolve equipment conflicts** per 5th edition rules
4. **Calculate correct AC** using the formula and rules
5. **Update character data** with corrections
6. **Provide detailed breakdown** of the calculation

Be thorough but concise. Focus on accuracy and rule compliance."""

    def build_ac_validation_prompt(self, character_data: Dict[str, Any]) -> str:
        """
        Build validation prompt with character data
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Formatted prompt for AI validation
        """
        return f"""Please validate and correct the Armor Class calculation for this character:

```json
{json.dumps(character_data, indent=2)}
```

Analyze their equipment, abilities, and class features to determine the correct AC according to 5th edition rules. 

Pay special attention to:
1. Equipped armor and shields
2. Dexterity modifier and armor type limitations
3. Fighting style bonuses (especially Defense)
4. Equipment conflicts (multiple armor pieces)

Provide the corrected character data with proper AC calculation."""

    def parse_ai_validation_response(self, ai_response: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse AI response and extract corrected character data
        
        Args:
            ai_response: AI validation response
            original_data: Original character data
            
        Returns:
            Corrected character data
        """
        try:
            # Try to extract JSON from AI response
            start_idx = ai_response.find('{')
            end_idx = ai_response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = ai_response[start_idx:end_idx]
                parsed_response = json.loads(json_str)

                schema_errors = validate_schema(parsed_response, CHARACTER_VALIDATOR_SCHEMA, path="response")
                if schema_errors:
                    self.logger.error("Character validator response schema violation: %s", schema_errors)
                    return original_data

                # Extract corrected character data
                if 'validated_character_data' in parsed_response:
                    corrected_data = parsed_response['validated_character_data']
                    
                    # Log corrections made
                    if 'corrections_made' in parsed_response:
                        self.corrections_made = parsed_response['corrections_made']
                        for correction in self.corrections_made:
                            debug(f"[AC Correction] {correction}", category="character_validation")
                            self.logger.info(f"AI Correction: {correction}")
                    
                    # Log AC breakdown
                    if 'ac_calculation_breakdown' in parsed_response:
                        breakdown = parsed_response['ac_calculation_breakdown']
                        self.logger.info(f"AC Breakdown: {breakdown}")
                    
                    return corrected_data
                
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse AI response: {str(e)}")
            self.logger.debug(f"AI Response was: {ai_response}")
        
        # Return original data if parsing fails
        return original_data
    
    def get_inventory_validator_system_prompt(self) -> str:
        """
        System prompt for AI inventory categorization validation
        
        Returns:
            System prompt with inventory categorization rules
        """
        # Return cached prompt loaded from file
        if self.inventory_prompt:
            return self.inventory_prompt
        
        # Fallback to hardcoded prompt if file loading failed
        return """You are an expert inventory categorization validator for the 5th edition of the world's most popular role playing game. Your job is to ensure all inventory items are correctly categorized according to standard item types.

## PRIMARY TASK: INVENTORY CATEGORIZATION VALIDATION

You must validate that each item in the character's inventory has the correct item_type based on its name and description.

### VALID ITEM TYPES (use these EXACTLY):
- "weapon" - swords, bows, daggers, melee and ranged weapons
- "armor" - armor pieces, shields, cloaks, boots, gloves, protective wear
- "ammunition" - arrows, bolts, sling bullets, thrown weapon ammo
- "consumable" - potions, scrolls, food, rations, anything consumed when used
- "equipment" - tools, torches, rope, containers, utility items
- "miscellaneous" - rings, amulets, wands, truly miscellaneous items only

### DETAILED CATEGORIZATION RULES:

#### EXCEPTION RULES - DO NOT RE-CATEGORIZE:
- If "Short Sword" is already type "weapon", leave it as is
- If "Shortsword" is already type "weapon", leave it as is  
- If "Longbow" is already type "weapon", leave it as is
- If "Long Bow" is already type "weapon", leave it as is
- If "Crossbow" is already type "weapon", leave it as is
- If "Light Crossbow" is already type "weapon", leave it as is
- If "Studded Leather Armor" is already type "armor", leave it as is
- If "Leather Armor" is already type "armor", leave it as is
- If "Scale Mail" is already type "armor", leave it as is
- If "Shield" is already type "armor", leave it as is
- If "Quiver" is already type "equipment", leave it as is
- If "Pouch" is already type "equipment" or "miscellaneous", leave it as is
- If "Explorer's Pack" is already type "equipment", leave it as is
- If "Torch" is already type "equipment", leave it as is
- If "Rope" is already type "equipment", leave it as is
- If "Waterskin" is already type "equipment", leave it as is
- Items already correctly categorized should not be changed

#### WEAPONS -> "weapon"
- All swords, axes, maces, hammers, daggers
- All bows, crossbows, slings
- Staffs and quarterstaffs used as weapons
- Any item with attack bonus or damage dice

#### ARMOR -> "armor"  
- All armor (leather, chain, plate, etc.)
- Shields of any type
- Helmets, gauntlets, boots IF they provide AC bonus
- Cloaks IF they provide AC or protection
- Robes IF they provide magical protection
- NOTE: Regular gloves are NOT armor unless they're gauntlets with AC bonus

#### AMMUNITION -> "ammunition"
- Arrows, Bolts, Bullets, Darts
- Sling stones, blowgun needles
- Any projectile meant to be fired/thrown multiple times

#### CONSUMABLES -> "consumable"
- ALL potions (healing, magic, alcohol)
- ALL scrolls
- ALL food items (rations, bread, meat, fruit)
- Trail rations, iron rations, dried foods
- Flasks of oil, holy water, acid, alchemist's fire
- Anything that is used up when activated

#### EQUIPMENT -> "equipment"
- Backpacks, sacks, chests, boxes (storage containers)
- Rope, chain, grappling hooks, pitons
- Torches, lanterns, candles (light sources)
- Thieves' tools, healer's kits, tool sets
- Bedrolls, tents, blankets
- Maps, spyglasses, magnifying glasses
- Musical instruments (lute, flute, drums)
- Holy symbols IF actively used for spellcasting
- Component pouches, spell focuses
- Books, tomes, journals (non-magical)
- Climbing gear, explorer's packs
- Regular boots without AC bonus (Sturdy Boots, Leather Boots, Work Boots)
- Regular cloaks without AC bonus (Woolen Cloak, Travel Cloak, Winter Cloak)
- Belts, sashes, bandoliers (weapon belts, tool belts, pouches worn on belt)
- Regular clothing items (tunics, shirts, vests, robes without magical properties)
- Regular hats and hoods (not helmets)

#### MISCELLANEOUS -> "miscellaneous"
- Coin pouches, money bags, pouches of coins (NOT active storage containers)
- Loose coins, gems, pearls, jewelry
- Dice, cards, gaming sets, chess pieces (including "Set of bone dice")
- Lucky charms, tokens, trinkets (non-magical)
- Holy symbols IF kept as keepsakes (not for spellcasting)
- Feathers, twine, small decorative items (including "Crow's Hand Feather")
- Art objects, statuettes, paintings
- Goblets, chalices, ceremonial vessels (unless actively used as tools)
- Letters, notes, deeds, contracts
- Signet rings (non-magical)
- Badges, medals, emblems (including "Insignia of rank")
- Amulets and talismans (non-magical) - ALWAYS miscellaneous unless they provide game mechanics
- Ward charms, protective tokens (non-magical)
- Carved or decorative talismans (keepsakes)
- Military keepsakes, trophies, dog tags (including "Trophy from a fallen enemy", "Dog tag")
- Trade goods, valuable cloth, fabric scraps (including "Torn but valuable cloth")
- Simple pouches and coin containers (including "Pouch")
- Protective gloves without AC bonus (including "Sturdy gloves")

### CRITICAL EDGE CASE RULES:
1. Coin containers (pouches, bags with coins) -> "miscellaneous" NOT "equipment"
2. Gaming items (dice, cards) -> "miscellaneous" NOT "equipment"  
3. Holy symbols -> "equipment" IF used for spellcasting, "miscellaneous" IF keepsake
4. Charms/tokens/wards -> "miscellaneous" for non-magical protective charms (even if they grant resistance)
5. Books -> "equipment" IF spellbooks or reference manuals, "miscellaneous" IF just lore
6. Containers -> "equipment" IF empty/general use, "miscellaneous" IF specifically for coins
7. Jewelry -> "miscellaneous" UNLESS it provides magical effects
8. Tools -> "equipment" IF professional tools, "miscellaneous" IF trinkets
9. Military memorabilia -> "miscellaneous" (insignia, trophies, dog tags are keepsakes)
10. Trade goods -> "miscellaneous" (cloth, fabric, raw materials for trade)
11. SPECIAL CASES THAT ARE ALWAYS MISCELLANEOUS:
    - Yew Ward Charm (protective charm)
    - Insignia of rank (badge/emblem)
    - Trophy from a fallen enemy (keepsake)
    - Set of bone dice (gaming set)
    - Dog tag (keepsake)
    - Pouch (coin container)
    - Crow's Hand Feather (token)
    - Torn but valuable cloth (trade good)
    - Carved bone talisman (charm/talisman)
    - Knight's Heart Amulet (keepsake amulet)
    - Any amulet or talisman (unless it grants mechanical benefits)
    - Enchanted goblet (art object/valuable)
    - Any goblet, chalice, or ceremonial vessel (unless actively used as equipment)
12. SPECIAL CASES FOR GLOVES:
    - Sturdy gloves -> "miscellaneous" (protective but no AC bonus)
    - Work gloves -> "equipment" (utility gloves for tasks)
    - Gauntlets -> "armor" (combat protection with AC bonus)
13. SPECIAL CASES FOR BOOTS AND CLOAKS:
    - Regular boots (Sturdy Boots, Leather Boots, etc.) -> "equipment" (worn but no AC bonus)
    - Regular cloaks (Woolen Cloak, Travel Cloak, etc.) -> "equipment" (worn but no AC bonus)
    - Armored boots or magical boots with AC -> "armor"
    - Cloaks of protection or with AC bonus -> "armor"
14. SPECIAL CASES FOR OTHER WEARABLES:
    - Regular belts, sashes -> "equipment" (utility items)
    - Regular clothing (tunics, shirts, vests) -> "equipment" (worn but no AC)
    - Regular hats, hoods -> "equipment" (worn but no AC)
    - Helmets or hats with AC bonus -> "armor"
    - Magical robes with protection -> "armor"
    - Bracers without AC bonus -> "equipment"
    - Bracers of defense or with AC bonus -> "armor"

### OUTPUT FORMAT:
Return a JSON object with ONLY the changes needed:
{
  "corrections_made": ["list of corrections"],
  "equipment": [
    {
      "item_name": "exact item name",
      "item_type": "corrected_type"
    }
  ]
}

CRITICAL: Only return items that need their item_type corrected. Do NOT return items that are already correctly categorized. Do NOT return the complete character data - only the equipment items that need item_type fixes.
"""
    
    def build_inventory_validation_prompt(self, character_data: Dict[str, Any]) -> str:
        """
        Build validation prompt for inventory categorization
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Formatted prompt for AI validation
        """
        equipment = character_data.get('equipment', [])
        
        prompt = f"""Please validate the inventory categorization for this character:

CHARACTER NAME: {character_data.get('name', 'Unknown')}

CURRENT INVENTORY:
"""
        
        for i, item in enumerate(equipment):
            item_name = item.get('item_name', 'Unknown Item')
            item_type = item.get('item_type', 'Unknown')
            description = item.get('description', 'No description')
            quantity = item.get('quantity', 1)
            
            prompt += f"""
Item #{i+1}:
- Name: {item_name}
- Current Type: {item_type}
- Description: {description}
- Quantity: {quantity}
"""
        
        prompt += """

Validate each item's categorization and correct any that are wrong. Focus especially on:
- Items currently marked as "miscellaneous" that should be other types
- Arrows/ammunition items
- Food/rations that should be "consumable"  
- Tools/torches that should be "equipment"

IMPORTANT: Return ONLY the items that need their item_type corrected. Do not include items that are already correctly categorized."""
        
        return prompt
    
    def parse_inventory_validation_response(self, ai_response: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse AI inventory validation response - returns only the updates/changes
        
        Args:
            ai_response: AI response string
            original_data: Original character data
            
        Returns:
            Dictionary with only the changes to apply (or empty dict if no changes)
        """
        try:
            # Try to extract JSON from AI response
            start_idx = ai_response.find('{')
            end_idx = ai_response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = ai_response[start_idx:end_idx]
                parsed_response = json.loads(json_str)
                
                # Check if there are any equipment updates
                if 'equipment' in parsed_response and parsed_response['equipment']:
                    # Log corrections made
                    if 'corrections_made' in parsed_response:
                        inventory_corrections = parsed_response['corrections_made']
                        for correction in inventory_corrections:
                            debug(f"[Inventory Correction] {correction}", category="character_validation")
                            self.logger.info(f"AI Inventory Correction: {correction}")
                            self.corrections_made.append(f"Inventory: {correction}")
                    
                    # Return only the equipment updates
                    return {"equipment": parsed_response['equipment']}
                else:
                    # No corrections needed
                    self.logger.debug("No inventory corrections needed")
                    return {}
                
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse AI inventory response: {str(e)}")
            self.logger.debug(f"AI Response was: {ai_response}")
        
        # Return empty dict if parsing fails (no changes)
        return {}
    
    def validate_character_file_safe(self, file_path: str) -> tuple[Dict[str, Any], bool]:
        """
        Validate character file using atomic file operations
        
        Args:
            file_path: Path to character JSON file
            
        Returns:
            Tuple of (character_data, success_flag)
        """
        try:
            # Load character data using safe file operations
            character_data = safe_read_json(file_path)
            if character_data is None:
                self.logger.error(f"Could not read character file {file_path}")
                return {}, False
            
            # AI validation and correction
            corrected_data = self.validate_and_correct_character(character_data)
            
            # Save if corrections were made using atomic file operations
            if self.corrections_made:
                # DEBUG: Check XP before saving corrections
                if 'experience_points' in character_data and 'experience_points' in corrected_data:
                    original_xp = character_data.get('experience_points', 0)
                    corrected_xp = corrected_data.get('experience_points', 0)
                    if original_xp != corrected_xp:
                        print(f"[DEBUG VALIDATOR XP] WARNING: Validator changing XP from {original_xp} to {corrected_xp}")
                    else:
                        print(f"[DEBUG VALIDATOR XP] Validator preserving XP: {corrected_xp}")
                
                success = safe_write_json(file_path, corrected_data)
                if success:
                    self.logger.info(f"Character file validated and corrected: {file_path}")
                    return corrected_data, True
                else:
                    self.logger.error(f"Failed to save corrected character data to {file_path}")
                    return character_data, False
            else:
                self.logger.debug(f"Character file validated - no corrections needed: {file_path}")
                return corrected_data, True
                
        except Exception as e:
            self.logger.error(f"Error validating character file {file_path}: {str(e)}")
            return {}, False
    
    def ai_validate_all_batched(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        OPTIMIZED: Batch all AI validations into a single request
        Combines AC validation, inventory categorization, currency consolidation, and class feature validation
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with all AI corrections applied
        """
        character_name = character_data.get('name', 'Unknown')
        
        # Build combined validation prompt
        validation_prompt = self.build_combined_validation_prompt(character_data)
        
        try:
            response = capture_and_fanout("T053", self.client.chat.completions.create, messages=[
                    {"role": "system", "content": self.get_combined_validator_system_prompt()},
                    {"role": "user", "content": validation_prompt}
                ], model=CHARACTER_VALIDATOR_MODEL, temperature=0.1)

            # Track usage if available
            if USAGE_TRACKING_AVAILABLE:
                try:
                    from utils.openai_usage_tracker import get_global_tracker
                    tracker = get_global_tracker()
                    tracker.track(response, context={'endpoint': 'character_validation', 'purpose': 'validate_character_data'})
                except:
                    pass

            ai_response = response.choices[0].message.content.strip()

            # Parse AI response to get all corrections
            corrected_data = self.parse_combined_validation_response(ai_response, character_data)
            
            return corrected_data
            
        except Exception as e:
            self.logger.error(f"Batched AI validation failed: {str(e)}")
            return character_data
    
    def get_combined_validator_system_prompt(self) -> str:
        """
        System prompt for combined validation tasks
        """
        return """You are an expert character validator for the 5th edition of the world's most popular role playing game. 
You must perform FOUR validation tasks in a single response:

1. ARMOR CLASS VALIDATION
2. INVENTORY CATEGORIZATION
3. CURRENCY CONSOLIDATION
4. CLASS FEATURE VALIDATION

## TASK 1: ARMOR CLASS VALIDATION

Validate the Armor Class calculation based on equipped armor, shields, and abilities.

AC Calculation Rules:
- Base AC = 10 + Dexterity modifier (if no armor)
- With armor: Use armor's base AC + allowed Dexterity modifier
- Shield: +2 AC (if equipped)
- Special abilities may add bonuses

Common armor types:
- Leather Armor: 11 + Dex modifier
- Studded Leather: 12 + Dex modifier  
- Chain Shirt: 13 + Dex modifier (max 2)
- Scale Mail: 14 + Dex modifier (max 2)
- Chain Mail: 16 (no Dex)
- Plate: 18 (no Dex)

## TASK 2: INVENTORY CATEGORIZATION

""" + self.get_inventory_validator_system_prompt() + """

## TASK 3: CURRENCY CONSOLIDATION

""" + self.get_inventory_consolidation_system_prompt() + """

## TASK 4: CLASS FEATURE VALIDATION

Check for duplicate or outdated class features that should have been replaced during level up.

Common issues to check:
1. Multiple versions of the same feature (e.g., "Channel Divinity (1/rest)" and "Channel Divinity (2/rest)")
2. Features with usage counts in the name that should be consolidated
3. Outdated feature descriptions that don't match current level

Rules:
- When a feature upgrades (like Channel Divinity uses increasing), the old version should be removed
- Features like "Sneak Attack (1d6)" should be replaced by "Sneak Attack (2d6)", not kept as duplicates
- Look for features with parenthetical usage counts or dice values that indicate versions

## COMBINED OUTPUT FORMAT:

Return a single JSON response with all corrections:
{
  "ac_validation": {
    "current_ac": 17,
    "calculated_ac": 16,
    "correction_needed": true,
    "breakdown": "Scale Mail (14) + Dex mod (+1) + Shield (+2) = 17",
    "corrections": ["AC should be 17, not 16"]
  },
  "inventory_corrections": {
    "corrections_made": ["List of inventory corrections"],
    "equipment": [
      {
        "item_name": "exact item name",
        "item_type": "corrected_type"
      }
    ]
  },
  "currency_consolidation": {
    "corrections_made": ["List of consolidation actions"],
    "currency": {
      "gold": 125,
      "silver": 50,
      "copper": 200
    },
    "items_to_remove": ["5 gold pieces", "bag of 50 gold"],
    "ammunition": [
      {"name": "Arrow", "quantity": 30}
    ],
    "ammo_items_to_remove": ["Arrows x 20"]
  },
  "class_feature_validation": {
    "duplicates_found": ["List of duplicate features to remove"],
    "corrections_made": ["Channel Divinity (1/rest) should be removed - superseded by Channel Divinity (2/rest)"],
    "features_to_remove": ["Channel Divinity (1/rest)"]
  }
}

IMPORTANT: Perform ALL FOUR validations and return results for each in the combined JSON response.
"""
    
    def build_combined_validation_prompt(self, character_data: Dict[str, Any]) -> str:
        """
        Build a combined prompt for all validations
        """
        character_name = character_data.get('name', 'Unknown')
        
        # Get individual prompts
        ac_prompt = self.build_ac_validation_prompt(character_data)
        inventory_prompt = self.build_inventory_validation_prompt(character_data)
        consolidation_prompt = self.build_inventory_consolidation_prompt(character_data)
        
        combined_prompt = f"""Please validate ALL aspects of this character in a single response:

CHARACTER NAME: {character_name}

=== TASK 1: ARMOR CLASS VALIDATION ===
{ac_prompt}

=== TASK 2: INVENTORY CATEGORIZATION ===
{inventory_prompt}

=== TASK 3: CURRENCY CONSOLIDATION ===
{consolidation_prompt}

=== TASK 4: CLASS FEATURE VALIDATION ===
Class Features:
{json.dumps(character_data.get('classFeatures', []), indent=2)}

Check for duplicate features that should have been replaced during level up (e.g., "Channel Divinity (1/rest)" vs "Channel Divinity (2/rest)").

Remember to return a single JSON response with all four validation results."""
        
        return combined_prompt
    
    def parse_combined_validation_response(self, ai_response: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the combined AI validation response
        """
        try:
            # Try to extract JSON from AI response
            start_idx = ai_response.find('{')
            end_idx = ai_response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = ai_response[start_idx:end_idx]
                parsed_response = json.loads(json_str)
                
                result_data = copy.deepcopy(original_data)
                
                # Process AC validation
                if 'ac_validation' in parsed_response:
                    ac_result = parsed_response['ac_validation']
                    if ac_result.get('correction_needed') and 'calculated_ac' in ac_result:
                        result_data['armorClass'] = ac_result['calculated_ac']
                        if 'corrections' in ac_result:
                            self.corrections_made.extend(ac_result['corrections'])
                    
                    # Add equipment effects if needed
                    if 'equipment_effects' in ac_result:
                        result_data['equipment_effects'] = ac_result['equipment_effects']
                
                # Process inventory corrections
                if 'inventory_corrections' in parsed_response:
                    inv_result = parsed_response['inventory_corrections']
                    if 'corrections_made' in inv_result:
                        self.corrections_made.extend(inv_result['corrections_made'])
                    
                    if 'equipment' in inv_result and inv_result['equipment']:
                        # Apply inventory updates using deep merge
                        from updates.update_character_info import deep_merge_dict
                        inventory_updates = {'equipment': inv_result['equipment']}
                        result_data = deep_merge_dict(result_data, inventory_updates)
                
                # Process currency consolidation
                if 'currency_consolidation' in parsed_response:
                    curr_result = parsed_response['currency_consolidation']
                    if 'corrections_made' in curr_result:
                        self.corrections_made.extend(curr_result['corrections_made'])
                    
                    # Update currency (only if not empty) - MERGE don't replace!
                    if 'currency' in curr_result and curr_result['currency']:
                        # Ensure we have a currency dict with all fields
                        if 'currency' not in result_data:
                            result_data['currency'] = {}
                        
                        # Preserve existing currency fields and update only what AI returns
                        # This prevents erasure of gold/silver when only copper is updated
                        current_currency = result_data.get('currency', {})
                        result_data['currency'] = {
                            'gold': current_currency.get('gold', 0),
                            'silver': current_currency.get('silver', 0),
                            'copper': current_currency.get('copper', 0)
                        }
                        # Now apply AI updates
                        result_data['currency'].update(curr_result['currency'])
                    
                    # Remove consolidated items
                    if 'items_to_remove' in curr_result and 'equipment' in result_data:
                        items_to_remove = set(curr_result['items_to_remove'])
                        result_data['equipment'] = [
                            item for item in result_data['equipment']
                            if item.get('item_name') not in items_to_remove
                        ]
                    
                    # Update ammunition (only if not empty)
                    if 'ammunition' in curr_result and curr_result['ammunition']:
                        result_data['ammunition'] = curr_result['ammunition']
                    
                    # Remove ammo items from equipment
                    if 'ammo_items_to_remove' in curr_result and 'equipment' in result_data:
                        ammo_to_remove = set(curr_result['ammo_items_to_remove'])
                        result_data['equipment'] = [
                            item for item in result_data['equipment']
                            if item.get('item_name') not in ammo_to_remove
                        ]
                
                # Process class feature validation
                if 'class_feature_validation' in parsed_response:
                    feat_result = parsed_response['class_feature_validation']
                    if 'corrections_made' in feat_result:
                        self.corrections_made.extend(feat_result['corrections_made'])
                    
                    # Remove duplicate features
                    if 'features_to_remove' in feat_result and feat_result['features_to_remove']:
                        features_to_remove = feat_result['features_to_remove']
                        if 'classFeatures' in result_data and isinstance(result_data['classFeatures'], list):
                            # Remove features by name
                            result_data['classFeatures'] = [
                                feature for feature in result_data['classFeatures']
                                if feature.get('name') not in features_to_remove
                            ]
                
                return result_data
                
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse combined AI response: {str(e)}")
            self.logger.debug(f"AI Response was: {ai_response}")
        
        # Return original data if parsing fails
        return original_data
    
    def validate_status_condition_consistency(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and correct status-condition consistency
        
        Ensures that status, condition, and hitPoints fields are logically consistent:
        - If status is "alive" and hitPoints > 0, condition cannot be "unconscious"
        - If healing an unconscious character, clear unconscious conditions
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with corrected status-condition consistency
        """
        
        status = character_data.get("status", "alive")
        condition = character_data.get("condition", "none")
        condition_affected = character_data.get("condition_affected", [])
        hit_points = character_data.get("hitPoints", 0)
        
        # Check for inconsistent state: alive with HP > 0 but unconscious condition
        if (status == "alive" and 
            hit_points > 0 and 
            (condition == "unconscious" or "unconscious" in condition_affected)):
            
            # Create a copy of character data to modify
            corrected_data = character_data.copy()
            
            # Clear unconscious conditions
            corrected_data["condition"] = "none"
            corrected_data["condition_affected"] = [c for c in condition_affected if c != "unconscious"]
            
            # Log the correction
            self.corrections_made.append({
                "type": "status_condition_consistency",
                "issue": f"Character had status='alive' with hitPoints={hit_points} but condition was unconscious",
                "correction": "Cleared unconscious condition and condition_affected"
            })
            
            self.logger.info(f"Corrected status-condition inconsistency: status={status}, HP={hit_points}, cleared unconscious condition")
            
            return corrected_data
        
        # Check for opposite case: unconscious status but no unconscious condition
        elif status == "unconscious" and condition != "unconscious":
            # Create a copy of character data to modify
            corrected_data = character_data.copy()
            
            # Set unconscious conditions
            corrected_data["condition"] = "unconscious"
            if "unconscious" not in corrected_data.get("condition_affected", []):
                corrected_data["condition_affected"] = corrected_data.get("condition_affected", []) + ["unconscious"]
            
            # Log the correction
            self.corrections_made.append({
                "type": "status_condition_consistency", 
                "issue": f"Character had status='unconscious' but condition was not unconscious",
                "correction": "Set condition to unconscious and added to condition_affected"
            })
            
            self.logger.info(f"Corrected status-condition inconsistency: status={status}, set unconscious condition")
            
            return corrected_data
        
        # No corrections needed
        return character_data
    
    def ai_consolidate_inventory(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to consolidate loose currency and ammunition into their proper sections with caching
        Following the main character updater pattern: return only changes, use deep merge
        
        Consolidates:
        - Loose coins (e.g., "5 gold pieces") into currency
        - Emptied coin bags (e.g., "bag of 50 gold") into currency
        - Ammunition items (e.g., "Crossbow bolts x 10") into ammunition section
        
        Preserves:
        - Gems and valuables (e.g., "ruby worth 150 gold")
        - Containers with contents (e.g., "chest containing 1000 gold")
        - Art objects and trade goods
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with consolidated currency and ammunition (from cache if unchanged)
        """
        
        # Extract only currency/ammo relevant data
        consolidation_data = self.extract_currency_consolidation_data(character_data)
        
        # Compute hash of consolidation data
        character_name = character_data.get('name', 'Unknown')
        currency_hash = self._compute_currency_hash(consolidation_data)
        
        # Check if validation is cached and unchanged
        if self._is_currency_validation_cached(character_name, currency_hash):
            # Return original data - no changes needed since cached validation passed
            print(f"DEBUG: [Validation Cache] Skipping currency consolidation for {character_name} - data unchanged")
            info(f"[Validation Cache] Skipping currency consolidation for {character_name} - data unchanged", category="character_validation")
            
            # Log cache hit statistics
            if character_name in self.validation_cache:
                cache_entry = self.validation_cache[character_name]
                debug(f"[Validation Cache] Last validated: {cache_entry.get('last_currency_validation')}", category="character_validation")
            
            return character_data
        
        # If no items need consolidation, skip API call
        if len(consolidation_data['equipment']) == 0:
            print(f"DEBUG: [Currency Consolidation] No currency/ammo items found for {character_name} - skipping consolidation")
            info(f"[Currency Consolidation] No currency/ammo items found for {character_name} - skipping consolidation", category="character_validation")
            # Update cache to avoid checking again
            self._update_currency_cache(character_name, currency_hash)
            return character_data
        
        # Data has changed or not cached - perform consolidation
        print(f"DEBUG: [AI Validator] Checking {character_name}'s inventory for consolidation opportunities...")
        info(f"[Validation Cache] Running currency consolidation for {character_name} - {len(consolidation_data['equipment'])} items to check", category="character_validation")
        
        max_attempts = 3
        attempt = 1
        
        while attempt <= max_attempts:
            try:
                # Build prompt with filtered data
                consolidation_prompt = self.build_inventory_consolidation_prompt(consolidation_data)
                
                response = capture_and_fanout("T054", self.client.chat.completions.create, messages=[
                        {"role": "system", "content": self.get_inventory_consolidation_system_prompt()},
                        {"role": "user", "content": consolidation_prompt}
                    ], model=CHARACTER_VALIDATOR_MODEL, temperature=0.1)
                
                # Track usage if available
                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(response, context={'endpoint': 'character_validation', 'purpose': 'validate_character_effects'})
                    except:
                        pass
                
                ai_response = response.choices[0].message.content.strip()
                
                # Parse AI response to get consolidation updates only
                consolidation_updates = self.parse_currency_consolidation_response(ai_response, character_data)
                
                # Update cache with validation results
                self._update_currency_cache(character_name, currency_hash)
                
                if consolidation_updates:
                    # Apply updates using deep merge (same pattern as main character updater)
                    from updates.update_character_info import deep_merge_dict
                    corrected_data = deep_merge_dict(character_data, consolidation_updates)
                    return corrected_data
                else:
                    # No consolidation needed
                    return character_data
                    
            except Exception as e:
                self.logger.error(f"AI currency consolidation attempt {attempt} failed: {str(e)}")
                attempt += 1
                if attempt > max_attempts:
                    self.logger.error(f"All {max_attempts} currency consolidation attempts failed")
                    return character_data
        
        return character_data
    
    def get_inventory_consolidation_system_prompt(self) -> str:
        """
        System prompt for AI inventory consolidation (currency and ammunition)
        
        Returns:
            System prompt with consolidation rules and examples
        """
        return """You are an expert inventory manager for the 5th edition of the world's most popular role playing game. Your job is to consolidate loose currency items and ammunition into their proper sections while preserving player agency over containers and valuables.

## PRIMARY TASKS: CURRENCY AND AMMUNITION CONSOLIDATION

You must:
1. Identify loose currency that should be added to the character's currency totals and remove those items from inventory
2. Identify ammunition items in equipment that should be moved to the ammunition section

### CONSOLIDATION RULES:

**DO CONSOLIDATE (add to currency and remove from inventory):**
- Loose coins: "5 gold pieces", "10 silver", "handful of copper"
- Emptied coin bags: "bag of 50 gold", "pouch with 100 silver"
- Clearly available currency: "20 gold from the table", "coins from defeated bandit"
- Currency with clear amounts: "15 gp", "stack of 30 silver coins"

**DO NOT CONSOLIDATE (preserve as inventory items):**
- Gems/jewelry: "ruby worth 150 gold", "diamond (500gp value)", "golden necklace"
- Containers with contents: "chest containing 1000 gold", "locked strongbox with coins"
- Trapped/locked items: "trapped chest", "locked coffer", "sealed vault"
- Art objects: "golden statue worth 250gp", "ornate painting valued at 100gp"
- Trade goods: "silk worth 100gp", "rare spices (50gp value)"
- Ambiguous containers: Items where it's unclear if the player has opened them

### AMMUNITION CONSOLIDATION RULES:

**DO CONSOLIDATE (move to ammunition section and remove from equipment):**
- Clear ammunition items: "Arrows x 20", "Crossbow bolts x 10", "20 arrows"
- Ammunition with quantities: "Quiver with 30 arrows", "Bundle of 15 bolts"
- Loose ammunition: "handful of arrows", "some crossbow bolts"

**DO NOT CONSOLIDATE (keep in equipment):**
- Magical ammunition: "+1 arrows", "flaming arrows", "arrows of slaying"
- Special ammunition: "silvered arrows", "adamantine bolts"
- Ammunition containers without clear count: "empty quiver", "bolt case"
- Non-standard ammunition: "ballista bolts", "special ammunition"

### AMMUNITION CONTAINER STANDARDIZATION:
**ALWAYS standardize container names:**
- "full quiver", "empty quiver", "quiver full of arrows" → "Quiver"
- "full bolt case", "empty bolt case", "case of bolts" → "Bolt case"

**If container is described as "full" or contains ammo:**
- Rename to standard name ("Quiver" or "Bolt case")
- Add appropriate ammunition to ammunition section:
  - "full quiver" → Add 20 arrows to ammunition
  - "quiver with 30 arrows" → Add 30 arrows to ammunition
  - "full bolt case" → Add 20 crossbow bolts to ammunition
  
**If container is "empty" or just a container:**
- Rename to standard name but don't add ammunition

### CURRENCY TYPES:
- platinum (pp) = 10 gold
- gold (gp) = 1 gold
- electrum (ep) = 0.5 gold
- silver (sp) = 0.1 gold  
- copper (cp) = 0.01 gold

### OUTPUT FORMAT:
Return a JSON object with ONLY the changes needed:
{
  "inventory": {
    "currency": {
      "platinum": 0,
      "gold": 125,      // New total after consolidation
      "electrum": 0,
      "silver": 50,     // New total after consolidation
      "copper": 200     // New total after consolidation
    }
  },
  "ammunition": [
    {
      "name": "Arrows",
      "quantity": 20,     // Added from "full quiver"
      "description": "Standard arrows for use with a longbow or shortbow"
    },
    {
      "name": "Crossbow bolt",
      "quantity": 50,     // New total after consolidation
      "description": "Ammunition for crossbows."
    }
  ],
  "equipment": [
    {"item_name": "full quiver", "item_name": "Quiver", "_update": true},  // Rename container
    {"item_name": "Crossbow bolts x 10", "_remove": true},  // Remove loose ammo from equipment
    {"item_name": "5 gold pieces", "_remove": true}  // Remove loose coins
  ],
  "consolidations_made": [
    "Consolidated X gold pieces into currency",
    "Emptied bag of Y gold into currency",
    "Total gold increased from A to B",
    "Renamed 'full quiver' to 'Quiver' and added 20 arrows",
    "Moved 'Crossbow bolts x 10' to ammunition section",
    "Ammunition 'Crossbow bolt' increased from 40 to 50"
  ]
}

CRITICAL: 
- Only return currency fields that changed
- Only return ammunition entries that changed
- Only list items that should be removed
- Calculate new totals by adding consolidated amounts to existing currency/ammunition
- For ammunition, maintain the same name format (e.g., "Crossbow bolt" not "crossbow bolts")
- Preserve player agency - when in doubt, don't consolidate"""
    
    def build_inventory_consolidation_prompt(self, character_data: Dict[str, Any]) -> str:
        """
        Build consolidation prompt with character inventory
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Formatted prompt for AI consolidation
        """
        equipment = character_data.get('equipment', [])
        current_currency = character_data.get('inventory', {}).get('currency', {})
        current_ammunition = character_data.get('ammunition', [])
        
        prompt = f"""Please consolidate loose currency and ammunition for this character:

CHARACTER NAME: {character_data.get('name', 'Unknown')}

CURRENT CURRENCY:
- Platinum: {current_currency.get('platinum', 0)}
- Gold: {current_currency.get('gold', 0)}
- Electrum: {current_currency.get('electrum', 0)}
- Silver: {current_currency.get('silver', 0)}
- Copper: {current_currency.get('copper', 0)}

CURRENT AMMUNITION:
"""
        for ammo in current_ammunition:
            prompt += f"- {ammo.get('name', 'Unknown')}: {ammo.get('quantity', 0)}\n"
        
        if not current_ammunition:
            prompt += "- None\n"
            
        prompt += """
CURRENT INVENTORY:
"""
        
        for i, item in enumerate(equipment):
            item_name = item.get('item_name', 'Unknown Item')
            item_type = item.get('item_type', 'Unknown')
            description = item.get('description', 'No description')
            quantity = item.get('quantity', 1)
            
            prompt += f"""
Item #{i+1}:
- Name: {item_name}
- Type: {item_type}
- Description: {description}
- Quantity: {quantity}
"""
        
        prompt += """

Identify loose currency items AND ammunition that should be consolidated. Remember:
- Consolidate loose coins and emptied bags into currency
- Move ammunition items (arrows, bolts) to the ammunition section
- Standardize container names (e.g., "full quiver" → "Quiver")
- If a container is "full", add ammo and rename container
- Preserve gems, containers, and valuables
- Calculate new totals after consolidation
- Return only the changes needed for both currency and ammunition"""
        
        return prompt
    
    def parse_currency_consolidation_response(self, ai_response: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse AI currency consolidation response - returns only the updates/changes
        
        Args:
            ai_response: AI response string
            original_data: Original character data
            
        Returns:
            Dictionary with only the changes to apply (or empty dict if no changes)
        """
        try:
            # Try to extract JSON from AI response
            start_idx = ai_response.find('{')
            end_idx = ai_response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = ai_response[start_idx:end_idx]
                parsed_response = json.loads(json_str)
                
                # Build update dictionary with only changes
                updates = {}
                
                # Check for currency updates
                if 'inventory' in parsed_response and 'currency' in parsed_response['inventory']:
                    updates['inventory'] = {'currency': parsed_response['inventory']['currency']}
                
                # Check for ammunition updates
                if 'ammunition' in parsed_response and parsed_response['ammunition']:
                    updates['ammunition'] = parsed_response['ammunition']
                
                # Check for equipment removals
                if 'equipment' in parsed_response and parsed_response['equipment']:
                    updates['equipment'] = parsed_response['equipment']
                
                # Log consolidations made
                if 'consolidations_made' in parsed_response:
                    consolidations = parsed_response['consolidations_made']
                    for consolidation in consolidations:
                        print(f"DEBUG: [Consolidation] {consolidation}")
                        info(f"[Consolidation] {consolidation}", category="character_validation")
                        self.logger.info(f"AI Currency Consolidation: {consolidation}")
                        self.corrections_made.append(consolidation)
                
                return updates if updates else {}
                
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse AI currency consolidation response: {str(e)}")
            self.logger.debug(f"AI Response was: {ai_response}")
        
        # Return empty dict if parsing fails (no changes)
        return {}
    
    def ensure_currency_integrity(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure currency object has all required fields (gold, silver, copper).
        This prevents KeyError crashes when fields are missing.
        
        Args:
            character_data: Character data to validate
            
        Returns:
            Character data with complete currency object
        """
        if 'currency' not in character_data:
            character_data['currency'] = {}
        
        currency = character_data['currency']
        
        # Ensure all currency fields exist with default value of 0
        required_fields = ['gold', 'silver', 'copper']
        missing_fields = []
        
        for field in required_fields:
            if field not in currency:
                currency[field] = 0
                missing_fields.append(field)
        
        if missing_fields:
            print(f"DEBUG: [Currency Integrity] Added missing currency fields: {missing_fields}")
            info(f"[Currency Integrity] Added missing currency fields: {missing_fields}", category="character_validation")
            self.corrections_made.append(f"Added missing currency fields: {', '.join(missing_fields)}")
        
        return character_data
    
    def consolidate_ammunition(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consolidate duplicate ammunition entries with exact name matches (case-insensitive).
        This handles cases like "Arrow" + "arrows" -> single "arrows" entry.
        
        IMPORTANT: Only consolidates exact matches (e.g., "arrows" + "Arrows").
        Does NOT consolidate special ammunition like "ice arrows" or "arrows +1".
        
        Args:
            character_data: Character data to validate
            
        Returns:
            Character data with consolidated ammunition
        """
        if 'ammunition' not in character_data or not isinstance(character_data['ammunition'], list):
            return character_data
        
        ammunition_list = character_data['ammunition']
        if len(ammunition_list) <= 1:
            return character_data
        
        # Group ammunition by normalized name (lowercase, handling singular/plural)
        consolidated = {}
        
        for ammo in ammunition_list:
            name = ammo.get('name', '').strip()
            if not name:
                continue
            
            # Normalize the name for comparison
            normalized_name = name.lower()
            
            # Handle singular/plural for exact base words only
            # "arrow" -> "arrows", "bolt" -> "bolts", "bullet" -> "bullets"
            singular_to_plural = {
                'arrow': 'arrows',
                'bolt': 'bolts', 
                'crossbow bolt': 'crossbow bolts',
                'bullet': 'bullets',
                'sling bullet': 'sling bullets',
                'dart': 'darts',
                'needle': 'needles',
                'blowgun needle': 'blowgun needles'
            }
            
            # Check if this is a singular form that should be pluralized
            if normalized_name in singular_to_plural:
                normalized_name = singular_to_plural[normalized_name]
            
            # Only consolidate if the name is EXACTLY one of our standard ammunition types
            # This prevents consolidation of "ice arrows", "flaming arrows", etc.
            standard_ammo_types = [
                'arrows', 'bolts', 'crossbow bolts', 'bullets', 
                'sling bullets', 'darts', 'needles', 'blowgun needles'
            ]
            
            if normalized_name not in standard_ammo_types:
                # Special ammunition - don't consolidate, keep as-is
                # Use the original name as the key to preserve it
                consolidated[name] = ammo
                continue
            
            # For standard ammunition, consolidate by normalized name
            if normalized_name in consolidated:
                # Add quantities together
                consolidated[normalized_name]['quantity'] = (
                    consolidated[normalized_name].get('quantity', 0) + 
                    ammo.get('quantity', 0)
                )
            else:
                # First occurrence - use the plural form as standard
                standardized_ammo = {
                    'name': normalized_name.title() if normalized_name != 'crossbow bolts' else 'Crossbow Bolts',
                    'quantity': ammo.get('quantity', 0),
                    'description': ammo.get('description', f"Standard {normalized_name}.")
                }
                consolidated[normalized_name] = standardized_ammo
        
        # Check if consolidation happened
        if len(consolidated) < len(ammunition_list):
            # Build list of what was consolidated
            original_entries = [f"{a.get('name')} ({a.get('quantity', 0)})" for a in ammunition_list]
            new_entries = [f"{a.get('name')} ({a.get('quantity', 0)})" for a in consolidated.values()]
            
            print(f"DEBUG: [Ammunition Consolidation] Consolidated {len(ammunition_list)} entries to {len(consolidated)}")
            print(f"DEBUG:   Original: {', '.join(original_entries)}")
            print(f"DEBUG:   Consolidated: {', '.join(new_entries)}")
            
            info(f"[Ammunition Consolidation] Consolidated duplicate ammunition entries", category="character_validation")
            self.corrections_made.append(f"Consolidated ammunition: {', '.join(original_entries)} -> {', '.join(new_entries)}")
            
            # Update the character data with consolidated ammunition
            character_data['ammunition'] = list(consolidated.values())
        
        return character_data


def validate_character_file(file_path: str) -> bool:
    """
    Convenience function to validate a character file using AI with atomic file operations
    
    CRITICAL: This function ensures currency fields are never erased by:
    1. Using safe_write_json which creates automatic .bak backups
    2. Merging currency updates instead of replacing
    3. Validating currency object has all required fields
    
    Args:
        file_path: Path to character JSON file
        
    Returns:
        True if validation successful, False otherwise
    """
    try:
        # Load character data using safe file operations
        character_data = safe_read_json(file_path)
        if character_data is None:
            error(f"FAILURE: Could not read character file {file_path}", category="file_operations")
            return False
        
        # AI validation and correction
        validator = AICharacterValidator()
        corrected_data = validator.validate_and_correct_character(character_data)
        
        # Save if corrections were made using atomic file operations
        if validator.corrections_made:
            success = safe_write_json(file_path, corrected_data)
            if success:
                info(f"SUCCESS: AI Corrections made: {validator.corrections_made}", category="character_validation")
                return True
            else:
                error(f"FAILURE: Failed to save corrected character data to {file_path}", category="file_operations")
                return False
        else:
            debug("VALIDATION: No corrections needed - character data is valid", category="character_validation")
            return True
        
    except Exception as e:
        error(f"FAILURE: Error validating character file {file_path}", exception=e, category="character_validation")
        return False


if __name__ == "__main__":
    # Test with character file
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        validate_character_file(file_path)
    else:
        # Test with default character
        validate_character_file("modules/Keep_of_Doom/characters/norn.json")
