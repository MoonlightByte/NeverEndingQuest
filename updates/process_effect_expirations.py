# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Process expired effects and automatically reverse them through character updates.
This should be called periodically (e.g., in the main game loop).
"""

import os
from typing import List, Dict, Any
from updates.update_character_effects import (
    apply_claimed_effect_reversal,
    check_and_apply_expirations,
)
from updates.update_character_info import update_character_info
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set up logging
set_script_name(os.path.basename(__file__))

def process_all_effect_expirations():
    """
    Check for expired effects and apply reversals for all characters.
    This is the main entry point for the game loop.
    """
    debug("EFFECTS: Checking for expired effects...", category="effects_tracking")
    
    # Get all expired effects
    reversals = check_and_apply_expirations()
    
    if not reversals:
        debug("EFFECTS: No expired effects found", category="effects_tracking")
        return {"claimed": 0, "completed": 0, "failed": 0, "blocked": 0}
    
    info(f"EFFECTS: Processing {len(reversals)} expired effects", category="effects_tracking")
    
    result = {
        "claimed": len(reversals),
        "completed": 0,
        "failed": 0,
        "blocked": 0,
    }

    # Apply each reversal through the character update system.
    for reversal in reversals:
        character_name = reversal['character']
        description = reversal['description']
        modifier = reversal['modifier']
        
        info(f"EFFECTS: Reversing effect for {character_name}: {description}", category="effects_tracking")
        
        if apply_claimed_effect_reversal(reversal, update_character_info):
            result["completed"] += 1
            info(f"EFFECTS: Successfully reversed effect: {modifier['source']}", category="effects_tracking")
        else:
            result["failed"] += 1
            error(
                f"EFFECTS: Failed to reverse effect for {character_name}; "
                "the durable reversal record was retained",
                category="effects_tracking",
            )
    return result

def process_rest_effects(character_name: str, rest_type: str):
    """
    Clear effects that expire on rest and apply reversals.
    
    Args:
        character_name: Name of the character taking a rest
        rest_type: Type of rest ('short_rest' or 'long_rest')
    """
    from updates.update_character_effects import clear_rest_effects
    
    debug(f"EFFECTS: Processing {rest_type} effects for {character_name}", category="effects_tracking")
    
    # Get effects that need to be cleared
    reversals = clear_rest_effects(character_name, rest_type)
    
    if not reversals:
        debug(f"EFFECTS: No {rest_type} effects to clear for {character_name}", category="effects_tracking")
        return {"claimed": 0, "completed": 0, "failed": 0, "blocked": 0}
    
    info(f"EFFECTS: Clearing {len(reversals)} effects due to {rest_type}", category="effects_tracking")
    
    result = {
        "claimed": len(reversals),
        "completed": 0,
        "failed": 0,
        "blocked": 0,
    }

    # Apply each reversal.
    for reversal in reversals:
        description = reversal['description']
        modifier = reversal['modifier']
        
        info(f"EFFECTS: Clearing effect: {modifier['source']}", category="effects_tracking")
        
        if apply_claimed_effect_reversal(reversal, update_character_info):
            result["completed"] += 1
            info(f"EFFECTS: Successfully cleared rest effect: {modifier['source']}", category="effects_tracking")
        else:
            result["failed"] += 1
            error(
                f"EFFECTS: Failed to clear rest effect: {modifier['source']}; "
                "the durable reversal record was retained",
                category="effects_tracking",
            )
    return result

# Test function
if __name__ == "__main__":
    print("Testing effect expiration processing...")
    
    # Test time-based expiration
    print("\nChecking for time-based expirations:")
    process_all_effect_expirations()
    
    # Test rest-based clearing
    print("\nTesting long rest for Thane:")
    process_rest_effects("Thane", "long_rest")
    
    print("\nTesting short rest for Elara:")
    process_rest_effects("Elara", "short_rest")