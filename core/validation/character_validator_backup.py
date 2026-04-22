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
from typing import Dict, List, Any, Optional
from openai import OpenAI

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
        """Initialize AI-powered validator"""
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
    
    def ai_validate_armor_class(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to validate and correct Armor Class calculation
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with AI-corrected AC
        """
        
        validation_prompt = self.build_ac_validation_prompt(character_data)
        
        try:
            response = self.client.chat.completions.create(
                model=CHARACTER_VALIDATOR_MODEL,
                temperature=0.1,  # Low temperature for consistent validation
                messages=[
                    {"role": "system", "content": self.get_validator_system_prompt()},
                    {"role": "user", "content": validation_prompt}
                ]
            )
            
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
            corrected_data = self.parse_ai_validation_response(ai_response, character_data)
            
            return corrected_data
            
        except Exception as e:
            self.logger.error(f"AI validation failed: {str(e)}")
            return character_data
    
    def ai_validate_inventory_categories(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to validate and correct inventory item categorization
        Following the main character updater pattern: return only changes, use deep merge
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with AI-corrected inventory categories
        """
        
        max_attempts = 3
        attempt = 1
        
        while attempt <= max_attempts:
            try:
                validation_prompt = self.build_inventory_validation_prompt(character_data)
                
                response = self.client.chat.completions.create(
                    model=CHARACTER_VALIDATOR_MODEL,
                    temperature=0.1,  # Low temperature for consistent validation
                    messages=[
                        {"role": "system", "content": self.get_inventory_validator_system_prompt()},
                        {"role": "user", "content": validation_prompt}
                    ]
                    # No max_tokens - let AI return full response
                )
                
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
            response = self.client.chat.completions.create(
                model=CHARACTER_VALIDATOR_MODEL,
                temperature=0.1,  # Low temperature for consistent validation
                messages=[
                    {"role": "system", "content": self.get_combined_validator_system_prompt()},
                    {"role": "user", "content": validation_prompt}
                ]
            )
            
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
        Use AI to consolidate loose currency and ammunition into their proper sections
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
            Character data with consolidated currency and ammunition
        """
        
        print(f"DEBUG: [AI Validator] Checking {character_data.get('name', 'Unknown')}'s inventory for consolidation opportunities...")
        info(f"[AI Validator] Checking {character_data.get('name', 'Unknown')}'s inventory for consolidation opportunities...", category="character_validation")
        
        max_attempts = 3
        attempt = 1
        
        while attempt <= max_attempts:
            try:
                consolidation_prompt = self.build_inventory_consolidation_prompt(character_data)
                
                response = self.client.chat.completions.create(
                    model=CHARACTER_VALIDATOR_MODEL,
                    temperature=0.1,  # Low temperature for consistent validation
                    messages=[
                        {"role": "system", "content": self.get_inventory_consolidation_system_prompt()},
                        {"role": "user", "content": consolidation_prompt}
                    ]
                )
                
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
- "full quiver", "empty quiver", "quiver full of arrows" -> "Quiver"
- "full bolt case", "empty bolt case", "case of bolts" -> "Bolt case"

**If container is described as "full" or contains ammo:**
- Rename to standard name ("Quiver" or "Bolt case")
- Add appropriate ammunition to ammunition section:
  - "full quiver" -> Add 20 arrows to ammunition
  - "quiver with 30 arrows" -> Add 30 arrows to ammunition
  - "full bolt case" -> Add 20 crossbow bolts to ammunition
  
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
- Standardize container names (e.g., "full quiver" -> "Quiver")
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