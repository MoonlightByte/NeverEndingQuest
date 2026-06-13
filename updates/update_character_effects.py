# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
AI-driven temporary effects tracking system that runs parallel to character updates.
Tracks temporary modifiers and automatically reverses them when expired.
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import uuid
from utils.enhanced_logger import debug, info, warning, error
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_path_manager import ModulePathManager
from updates.update_character_info import normalize_character_name
import config
from core.ai import api_client

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass

# Set up logging
from utils.enhanced_logger import set_script_name
set_script_name(os.path.basename(__file__))

from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T078", "updates/update_character_effects.py", 210)

EFFECTS_TRACKER_FILE = "modules/effects_tracker.json"

def get_current_game_time() -> datetime:
    """Get current game time from party tracker as datetime."""
    party_data = safe_read_json("party_tracker.json")
    if not party_data or "worldConditions" not in party_data:
        warning("Failed to get game time from party tracker", category="effects_tracking")
        # Return a default time
        return datetime(2000, 1, 1)
    
    world = party_data["worldConditions"]
    day = world.get("day", 0)
    time_str = world.get("time", "00:00:00")
    
    # Parse time
    time_parts = time_str.split(":")
    hour = int(time_parts[0])
    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
    second = int(time_parts[2]) if len(time_parts) > 2 else 0
    
    # Calculate total days accounting for month transitions
    # If we see day drop from 31+ to 1, we've crossed a month
    total_days = day
    last_day = getattr(get_current_game_time, 'last_day', 0)
    if hasattr(get_current_game_time, 'month_count'):
        if day < last_day and last_day >= 30:
            # Month transition detected
            get_current_game_time.month_count += 1
            debug(f"EFFECTS: Month transition detected. Day {last_day} -> {day}", category="effects_tracking")
        total_days = (get_current_game_time.month_count * 30) + day
    else:
        # Initialize tracking
        get_current_game_time.month_count = 0
    
    get_current_game_time.last_day = day
    
    # Use base date and add total game days
    base_date = datetime(2000, 1, 1)
    game_datetime = base_date + timedelta(days=total_days, hours=hour, minutes=minute, seconds=second)
    
    return game_datetime

def get_effects_file_path() -> str:
    """Get the path to the global effects tracker file."""
    # Effects are tracked globally across all modules in the modules directory
    return EFFECTS_TRACKER_FILE

def load_effects_tracker() -> Dict[str, Any]:
    """Load the effects tracker file, creating it if it doesn't exist."""
    file_path = get_effects_file_path()
    
    if not os.path.exists(file_path):
        # Create initial structure
        initial_data = {
            "version": "1.0",
            "lastUpdated": datetime.now().isoformat(),
            "characters": {},
            "metadata": {
                "description": "Tracks temporary effects and modifiers for characters"
            }
        }
        safe_write_json(file_path, initial_data)
        debug(f"EFFECTS: Created new effects tracker at {file_path}", category="effects_tracking")
        return initial_data
    
    data = safe_read_json(file_path)
    if data is None:
        error(f"Failed to load effects tracker from {file_path}")
        return {"characters": {}}
    
    return data

def save_effects_tracker(data: Dict[str, Any]) -> bool:
    """Save the effects tracker file."""
    file_path = get_effects_file_path()
    data["lastUpdated"] = datetime.now().isoformat()
    
    success = safe_write_json(file_path, data)
    if success:
        debug(f"EFFECTS: Saved effects tracker to {file_path}", category="effects_tracking")
    else:
        error(f"EFFECTS: Failed to save effects tracker to {file_path}", category="effects_tracking")
    
    return success

def analyze_effect_with_ai(character_name: str, change_description: str) -> Optional[Dict[str, Any]]:
    """Use AI to analyze if a change is a trackable temporary effect."""
    
    # Try to load character stats for ability score calculations
    character_stats = {}
    try:
        from utils.file_operations import safe_read_json
        char_file = f"characters/{character_name.lower().replace(' ', '_')}.json"
        char_data = safe_read_json(char_file)
        if char_data and 'abilities' in char_data:
            character_stats = char_data['abilities']
    except:
        pass  # Continue without stats if unable to load
    
    stats_info = ""
    if character_stats:
        stats_info = f"\nCharacter's current ability scores: STR {character_stats.get('strength', 10)}, DEX {character_stats.get('dexterity', 10)}, CON {character_stats.get('constitution', 10)}, INT {character_stats.get('intelligence', 10)}, WIS {character_stats.get('wisdom', 10)}, CHA {character_stats.get('charisma', 10)}"
    
    prompt = f"""You are an effects tracking AI for a 5th edition fantasy RPG. Analyze this character update to determine if it's a temporary effect that should be tracked.

Character: {character_name}{stats_info}
Update: {change_description}

Determine if this is a TEMPORARY effect that will expire. Track temporary effects with durations of 1 minute or longer.
Do NOT track instant effects, permanent changes, or effects lasting less than 1 minute (including round-based effects).
IMPORTANT: Convert any round-based durations to minutes (10 rounds = 1 minute) if the effect should persist.

Common trackable effects include:
- Shield of Faith (+2 AC for 10 minutes)
- Bless (+1d4 to attacks/saves for 1 minute or up to concentration)
- Aid spell (+5 HP for 8 hours) - affects BOTH current HP and max HP
- Mage Armor (AC bonus for 8 hours)
- Enhance Ability (advantage for 1 hour)
- Ability drain (STR/DEX reduction until rest)
- Buffs/debuffs lasting minutes, hours, or days
- Poison/disease effects with durations
- Heroes' Feast (+2d10 max HP for 24 hours) - affects both current and max HP

Duration handling:
- Track effects lasting 1 minute or longer
- For concentration spells, use the spell's maximum duration
- Round-based effects (less than 1 minute) should NOT be tracked

IMPORTANT: Some effects modify both the current value AND the maximum value:
- Aid spell: Increases both current HP and max HP
- Temporary HP effects: Only affect current HP, not max HP
- Ability score changes: May affect derived stats (CON affects max HP)

CRITICAL: For effects that SET an ability score to a specific value (like Potion of Giant Strength setting STR to 21):
- Track these as the MODIFIER from the character's base score
- Example: If base strength is 11 and potion sets it to 21, track value as +10
- The effects system will calculate and apply the correct final value
- This allows proper reversal when the effect expires

Return JSON with this exact structure:
{{
  "should_track": true/false,
  "effect": {{
    "stat": "hitPoints|maxHitPoints|strength|dexterity|constitution|intelligence|wisdom|charisma|armorClass|other",
    "value": numeric_modifier (positive or negative),
    "source": "brief description of source",
    "duration_type": "hours|days|until_rest|special",
    "duration_value": number or "long_rest"/"short_rest",
    "description": "full effect description",
    "affects_max": true/false (true if this also affects the maximum value, like Aid affecting max HP)
  }}
}}

If should_track is false, still populate the effect fields with empty/default values.
For ability drains, use negative values (e.g., -2 for strength drain).
For HP gains from Aid, use positive values (e.g., +5).
Set affects_max to true for effects like Aid that modify both current and maximum values.
"""

    # Select model config per provider
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        effects_config = config.CHAR_EFFECTS_GPT52_NONE
    elif MODEL_PROVIDER == "gemini":
        effects_config = config.CHAR_EFFECTS_GEMINI_FLASH_HIGH
    elif MODEL_PROVIDER == "lmstudio":
        effects_config = config.CHAR_EFFECTS_LMSTUDIO
    else:  # legacy
        effects_config = config.CHAR_EFFECTS_LEGACY

    try:
        response = capture_and_fanout("T078", api_client.create_completion,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analyze this update: {change_description}"}
            ],
            model=effects_config["model"],
            temperature=0.3,
            **{k: v for k, v in effects_config.items() if k != "model"})
        
        # Track usage if available
        if USAGE_TRACKING_AVAILABLE:
            try:
                track_response(response)
            except:
                pass
        
        # Clean response and parse JSON
        # MED-3: strip markdown code fences robustly. The old prefix check only
        # matched a "```json" opening; Gemini-flash often emits a BARE "```"
        # fence, which slipped through -> json.loads failed -> effects (Sneak
        # Attack, Bless duration) were silently dropped. Handle both forms.
        response_text = response.choices[0].message.content.strip()
        response_text = re.sub(r'^```(?:json)?\s*|\s*```$', '', response_text.strip())

        result = json.loads(response_text.strip())
        debug(f"EFFECTS: AI effect analysis: {result}", category="effects_tracking")
        return result
        
    except Exception as e:
        error(f"Failed to analyze effect with AI: {str(e)}")
        return None

def calculate_expiration(duration_type: str, duration_value: Any) -> Optional[str]:
    """Calculate when an effect expires based on duration."""
    # Use game time instead of real time
    now = get_current_game_time()
    
    if duration_type == "hours":
        try:
            hours = float(duration_value)
            expiration = now + timedelta(hours=hours)
            return expiration.isoformat()
        except:
            return None
    
    elif duration_type == "days":
        try:
            days = int(duration_value)
            expiration = now + timedelta(days=days)
            return expiration.isoformat()
        except:
            return None
    
    elif duration_type == "until_rest":
        # Rest-based effects don't have a timestamp
        return duration_value  # "long_rest" or "short_rest"
    
    elif duration_type == "special":
        # Special conditions handled case-by-case
        return "special"
    
    return None

def add_effect(character_name: str, effect_info: Dict[str, Any]) -> bool:
    """Add a new effect to the tracker."""
    tracker = load_effects_tracker()
    
    # Normalize character name to match file naming convention
    normalized_name = normalize_character_name(character_name)
    debug(f"EFFECTS: Normalized '{character_name}' to '{normalized_name}'", category="effects_tracking")
    
    # Ensure character exists
    if normalized_name not in tracker["characters"]:
        tracker["characters"][normalized_name] = {
            "modifiers": []
        }
    
    # Create effect entry
    effect_id = str(uuid.uuid4())[:8]  # Short ID for readability
    
    # Use game time instead of real time
    game_time = get_current_game_time()
    
    effect_entry = {
        "id": effect_id,
        "stat": effect_info["stat"],
        "value": effect_info["value"],
        "source": effect_info["source"],
        "description": effect_info["description"],
        "applied_at": game_time.isoformat(),
        "duration_type": effect_info["duration_type"],
        "duration_value": effect_info["duration_value"]
    }
    
    # Include affects_max flag if present
    if "affects_max" in effect_info:
        effect_entry["affects_max"] = effect_info["affects_max"]
    
    # Calculate expiration
    expiration = calculate_expiration(effect_info["duration_type"], effect_info["duration_value"])
    if expiration:
        effect_entry["expires_at"] = expiration
    
    # Add to character's modifiers
    tracker["characters"][normalized_name]["modifiers"].append(effect_entry)
    
    info(f"EFFECTS: Added effect for {normalized_name}: {effect_info['source']} "
         f"({effect_info['stat']} {effect_info['value']:+d})", category="effects_tracking")
    
    return save_effects_tracker(tracker)

def check_and_apply_expirations() -> List[Dict[str, Any]]:
    """Check for expired effects and generate reversal actions."""
    tracker = load_effects_tracker()
    # Use game time instead of real time
    now = get_current_game_time()
    reversals = []
    
    for character_name, char_data in tracker["characters"].items():
        if "modifiers" not in char_data:
            continue
        
        active_modifiers = []
        
        for modifier in char_data["modifiers"]:
            expired = False
            
            # Check time-based expiration
            if "expires_at" in modifier and modifier["expires_at"] not in ["long_rest", "short_rest", "special"]:
                try:
                    expiration_time = datetime.fromisoformat(modifier["expires_at"])
                    if now >= expiration_time:
                        expired = True
                        info(f"EFFECTS: Effect expired for {character_name}: {modifier['source']}", category="effects_tracking")
                except:
                    warning(f"Invalid expiration time for effect {modifier['id']}")
            
            if expired:
                # Generate reversal
                reversal_value = -modifier["value"]  # Reverse the effect
                
                # Generate proper description based on whether we're adding or removing
                if modifier["value"] > 0:
                    # Positive effect expiring - character loses the bonus
                    action_word = "loses"
                else:
                    # Negative effect expiring - character regains what was lost
                    action_word = "regains"
                
                # Check if this effect affects both current and max values
                if modifier.get("affects_max", False) and modifier["stat"] == "hitPoints":
                    reversal_desc = f"{action_word} {abs(modifier['value'])} maximum hit points and {abs(modifier['value'])} current hit points as {modifier['source']} expires. Remove '{modifier['source']}' from temporaryEffects."
                else:
                    reversal_desc = f"{action_word} {abs(modifier['value'])} {modifier['stat']} as {modifier['source']} expires. Remove effect from temporaryEffects."
                
                reversals.append({
                    "character": character_name,
                    "description": reversal_desc,
                    "modifier": modifier
                })
            else:
                active_modifiers.append(modifier)
        
        char_data["modifiers"] = active_modifiers
    
    # Save updated tracker
    if reversals:
        save_effects_tracker(tracker)
    
    return reversals

def clear_rest_effects(character_name: str, rest_type: str) -> List[Dict[str, Any]]:
    """Clear effects that expire on rest."""
    tracker = load_effects_tracker()
    reversals = []
    
    # Normalize character name
    normalized_name = normalize_character_name(character_name)
    
    if normalized_name not in tracker["characters"]:
        return reversals
    
    char_data = tracker["characters"][normalized_name]
    if "modifiers" not in char_data:
        return reversals
    
    active_modifiers = []
    
    for modifier in char_data["modifiers"]:
        should_clear = False
        
        # Check if this effect expires on this type of rest
        if "expires_at" in modifier:
            if rest_type == "long_rest" and modifier["expires_at"] in ["long_rest", "short_rest"]:
                should_clear = True
            elif rest_type == "short_rest" and modifier["expires_at"] == "short_rest":
                should_clear = True
        
        if should_clear:
            # Generate reversal with specific value information
            reversal_value = -modifier["value"]
            
            # Generate proper description based on whether we're adding or removing
            if modifier["value"] > 0:
                # Positive effect expiring - character loses the bonus
                action_word = "loses"
            else:
                # Negative effect expiring - character regains what was lost
                action_word = "regains"
            
            # Include the specific stat and value in the description
            reversal_desc = f"{action_word} {abs(modifier['value'])} {modifier['stat']} as {modifier['source']} expires after {rest_type.replace('_', ' ')}"
            
            reversals.append({
                "character": character_name,
                "description": reversal_desc,
                "modifier": modifier
            })
            
            info(f"EFFECTS: Cleared rest effect for {character_name}: {modifier['source']}", category="effects_tracking")
        else:
            active_modifiers.append(modifier)
    
    char_data["modifiers"] = active_modifiers
    save_effects_tracker(tracker)
    
    return reversals

def update_character_effects(character_name: str, change_description: str) -> bool:
    """
    Main entry point for effects tracking.
    Analyzes character updates and tracks temporary effects.
    Also detects when rests occur to clear rest-based effects.
    """
    debug(f"EFFECTS: Analyzing potential effect for {character_name}: {change_description}", category="effects_tracking")
    
    # First check if this is a rest action that should clear effects
    change_lower = change_description.lower()
    if any(phrase in change_lower for phrase in ["short rest", "long rest", "takes a rest", "take a rest"]):
        debug(f"EFFECTS: Detected rest action in description", category="effects_tracking")
        
        # Determine rest type
        if "long rest" in change_lower:
            rest_type = "long_rest"
        else:
            rest_type = "short_rest"  # Default to short rest
        
        info(f"EFFECTS: Processing {rest_type} effects for {character_name}", category="effects_tracking")
        
        # Clear rest-based effects and get reversals
        rest_reversals = clear_rest_effects(character_name, rest_type)
        
        # Apply reversals to character
        if rest_reversals:
            from updates.update_character_info import update_character_info
            for reversal in rest_reversals:
                debug(f"EFFECTS: Applying rest reversal: {reversal['description']}")
                update_character_info(reversal["character"], reversal["description"])
        
        # Continue to check if there are also new effects to track
    
    # Use AI to analyze if this is a trackable effect
    analysis = analyze_effect_with_ai(character_name, change_description)
    
    if not analysis:
        warning("Failed to analyze effect")
        return False
    
    # Track the effect if needed
    if analysis["should_track"]:
        effect_info = analysis["effect"]
        success = add_effect(character_name, effect_info)
        
        if success:
            info(f"EFFECTS: Successfully tracked effect: {effect_info['source']}", category="effects_tracking")
        else:
            error(f"EFFECTS: Failed to track effect: {effect_info['source']}", category="effects_tracking")
        
        return success
    else:
        debug(f"EFFECTS: Effect not trackable: {change_description}", category="effects_tracking")
        return True

def get_character_modifiers(character_name: str) -> Dict[str, int]:
    """Get current active modifiers for a character."""
    tracker = load_effects_tracker()
    
    # Normalize character name
    normalized_name = normalize_character_name(character_name)
    
    if normalized_name not in tracker["characters"]:
        return {}
    
    modifiers = {}
    char_data = tracker["characters"][normalized_name]
    
    if "modifiers" in char_data:
        for modifier in char_data["modifiers"]:
            stat = modifier["stat"]
            value = modifier["value"]
            
            # Sum modifiers for same stat
            if stat in modifiers:
                modifiers[stat] += value
            else:
                modifiers[stat] = value
    
    return modifiers

# Test function for development
if __name__ == "__main__":
    print("Testing update_character_effects.py")
    
    # Test various effects
    test_cases = [
        ("TestFighter", "gains 5 hit points from Aid spell cast by cleric"),
        ("TestWizard", "takes 10 damage from orc's sword"),
        ("TestFighter", "strength reduced by 2 from shadow's touch"),
        ("TestCleric", "gains +2 AC from Shield of Faith spell"),
        ("TestWizard", "gains advantage on strength checks from Enhance Ability"),
        ("TestFighter", "poisoned by spider venom for 1 hour"),
        ("TestCleric", "gains resistance to fire damage from potion"),
        ("TestWizard", "intelligence drained by 3 from mind flayer"),
        ("TestFighter", "gains 10 temporary hit points from False Life"),
        ("TestCleric", "affected by Slow spell reducing speed and AC")
    ]
    
    print("\nTesting effect detection:")
    for character, effect in test_cases:
        print(f"\n--- Testing: {character} - {effect} ---")
        update_character_effects(character, effect)
    
    print("\n\nCurrent effects tracker:")
    tracker = load_effects_tracker()
    print(json.dumps(tracker, indent=2))
    
    print("\n\nTesting expiration check:")
    reversals = check_and_apply_expirations()
    for reversal in reversals:
        print(f"Reversal needed: {reversal['character']} - {reversal['description']}")