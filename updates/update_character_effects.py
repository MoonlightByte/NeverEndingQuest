# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
AI-driven temporary effects tracking system that runs parallel to character updates.
Tracks temporary modifiers and automatically reverses them when expired.
"""

import copy
import json
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import uuid
from utils.enhanced_logger import debug, info, warning, error
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.file_operations import atomic_writer, safe_read_json, safe_write_json
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
register_callsite("T078", "updates/update_character_effects.py", 335)

EFFECTS_TRACKER_FILE = "modules/effects_tracker.json"
_EFFECTS_TRANSACTION_LOCK = threading.RLock()
_COMPLETED_REVERSAL_LIMIT = 200


_TRACKED_EFFECT_FIELDS = {
    "stat",
    "value",
    "source",
    "duration_type",
    "duration_value",
    "description",
    "affects_max",
}
_TRACKED_STATS = {
    "hitPoints",
    "maxHitPoints",
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
    "armorClass",
    "other",
}


def _validate_effect_analysis(result: Any) -> Dict[str, Any]:
    """Validate T078 before its output can mutate the effects tracker."""
    if not isinstance(result, dict) or set(result) != {"should_track", "effect"}:
        raise ValueError("T078 requires exactly should_track and effect")
    if type(result["should_track"]) is not bool or not isinstance(result["effect"], dict):
        raise ValueError("T078 returned invalid should_track/effect types")
    if result["should_track"] is False:
        return result

    effect = result["effect"]
    if set(effect) != _TRACKED_EFFECT_FIELDS:
        raise ValueError("T078 tracked effect has missing or extra fields")
    if effect["stat"] not in _TRACKED_STATS:
        raise ValueError("T078 tracked effect has an unsupported stat")
    if type(effect["value"]) is not int:
        raise ValueError("T078 tracked effect value must be an integer")
    if not isinstance(effect["source"], str) or not effect["source"].strip():
        raise ValueError("T078 tracked effect source must be useful text")
    if not isinstance(effect["description"], str) or not effect["description"].strip():
        raise ValueError("T078 tracked effect description must be useful text")
    if type(effect["affects_max"]) is not bool:
        raise ValueError("T078 affects_max must be a boolean")

    duration_type = effect["duration_type"]
    duration_value = effect["duration_value"]
    if duration_type in {"hours", "days"}:
        if type(duration_value) not in {int, float} or duration_value <= 0:
            raise ValueError("T078 timed duration must be a positive number")
    elif duration_type == "until_rest":
        if duration_value not in {"long_rest", "short_rest"}:
            raise ValueError("T078 rest duration must name a valid rest")
    elif duration_type == "special":
        if not isinstance(duration_value, str) or not duration_value.strip():
            raise ValueError("T078 special duration must be useful text")
    else:
        raise ValueError("T078 returned an unsupported duration_type")
    return result

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


def _initial_effects_tracker() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "lastUpdated": datetime.now().isoformat(),
        "characters": {},
        "metadata": {
            "description": "Tracks temporary effects and modifiers for characters"
        },
    }


def _load_effects_tracker_locked(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return _initial_effects_tracker()
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot safely read effects tracker {file_path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("characters"), dict):
        raise RuntimeError("Effects tracker must contain a characters object")
    return data


@contextmanager
def _effects_tracker_transaction():
    """Hold the complete cross-thread/process read-modify-write boundary."""
    file_path = os.path.abspath(os.path.normpath(get_effects_file_path()))
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with _EFFECTS_TRANSACTION_LOCK:
        lock_acquired = False
        try:
            atomic_writer.acquire_lock(file_path)
            lock_acquired = True
            tracker = _load_effects_tracker_locked(file_path)
            yield tracker
            tracker["lastUpdated"] = datetime.now().isoformat()
            if not safe_write_json(
                file_path,
                tracker,
                create_backup=True,
                acquire_lock=False,
            ):
                raise RuntimeError(f"Failed to commit effects tracker {file_path}")
        finally:
            if lock_acquired:
                atomic_writer.release_lock(file_path)

def load_effects_tracker() -> Dict[str, Any]:
    """Load the effects tracker file, creating it if it doesn't exist."""
    file_path = os.path.abspath(os.path.normpath(get_effects_file_path()))
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with _EFFECTS_TRANSACTION_LOCK:
        lock_acquired = False
        try:
            atomic_writer.acquire_lock(file_path)
            lock_acquired = True
            data = _load_effects_tracker_locked(file_path)
            if not os.path.exists(file_path):
                if not safe_write_json(
                    file_path,
                    data,
                    create_backup=False,
                    acquire_lock=False,
                ):
                    raise RuntimeError(f"Failed to create effects tracker {file_path}")
                debug(
                    f"EFFECTS: Created new effects tracker at {file_path}",
                    category="effects_tracking",
                )
            return data
        finally:
            if lock_acquired:
                atomic_writer.release_lock(file_path)

def save_effects_tracker(data: Dict[str, Any]) -> bool:
    """Save the effects tracker file."""
    try:
        with _effects_tracker_transaction() as tracker:
            tracker.clear()
            tracker.update(data)
        debug(
            f"EFFECTS: Saved effects tracker to {get_effects_file_path()}",
            category="effects_tracking",
        )
        return True
    except Exception as exc:
        error(
            f"EFFECTS: Failed to save effects tracker to {get_effects_file_path()}: {exc}",
            category="effects_tracking",
        )
        return False

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
            _request_provider=MODEL_PROVIDER,
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

        result = _validate_effect_analysis(json.loads(response_text.strip()))
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
    try:
        with _effects_tracker_transaction() as tracker:
            normalized_name = normalize_character_name(character_name)
            debug(
                f"EFFECTS: Normalized '{character_name}' to '{normalized_name}'",
                category="effects_tracking",
            )
            tracker["characters"].setdefault(normalized_name, {"modifiers": []})

            effect_entry = {
                "id": str(uuid.uuid4())[:8],
                "stat": effect_info["stat"],
                "value": effect_info["value"],
                "source": effect_info["source"],
                "description": effect_info["description"],
                "applied_at": get_current_game_time().isoformat(),
                "duration_type": effect_info["duration_type"],
                "duration_value": effect_info["duration_value"],
            }
            if "affects_max" in effect_info:
                effect_entry["affects_max"] = effect_info["affects_max"]
            expiration = calculate_expiration(
                effect_info["duration_type"], effect_info["duration_value"]
            )
            if expiration:
                effect_entry["expires_at"] = expiration
            tracker["characters"][normalized_name]["modifiers"].append(effect_entry)

        info(
            f"EFFECTS: Added effect for {normalized_name}: {effect_info['source']} "
            f"({effect_info['stat']} {effect_info['value']:+d})",
            category="effects_tracking",
        )
        return True
    except Exception as exc:
        error(f"EFFECTS: Failed to add effect transactionally: {exc}")
        return False


def _claim_effect_reversal(modifier: Dict[str, Any], reason: str) -> Optional[str]:
    """Claim one durable reversal; an interrupted claim is never applied twice."""
    if modifier.get("reversal_state") == "in_progress":
        warning(
            "EFFECTS: Reversal remains in progress and requires reconciliation: "
            f"{modifier.get('id', 'unknown')} ({modifier.get('source', 'unknown')})",
            category="effects_tracking",
        )
        return None

    claim_id = uuid.uuid4().hex
    modifier["reversal_state"] = "in_progress"
    modifier["reversal_reason"] = reason
    modifier["reversal_claim_id"] = claim_id
    modifier["reversal_claimed_at"] = datetime.now().isoformat()
    return claim_id


def _reversal_record(
    character_name: str,
    modifier: Dict[str, Any],
    claim_id: str,
    description: str,
) -> Dict[str, Any]:
    return {
        "character": character_name,
        "description": description,
        "modifier": copy.deepcopy(modifier),
        "claim_id": claim_id,
    }


def complete_effect_reversal(
    character_name: str,
    modifier_id: str,
    claim_id: str,
    *,
    success: bool,
) -> bool:
    """Acknowledge a claimed reversal without losing failed work.

    Known failures return the modifier to ``pending`` so the next scan heals it.
    A process crash leaves ``in_progress`` durably visible and will not be
    applied a second time automatically. Successful acknowledgements are kept
    in a bounded ledger, making duplicate completion calls idempotent.
    """
    normalized_name = normalize_character_name(character_name)
    completion_key = f"{normalized_name}:{modifier_id}"
    try:
        with _effects_tracker_transaction() as tracker:
            metadata = tracker.setdefault("metadata", {})
            completed = metadata.setdefault("completed_reversals", [])
            if not isinstance(completed, list):
                raise RuntimeError("effects completion ledger must be a list")

            modifiers = (
                tracker.get("characters", {})
                .get(normalized_name, {})
                .get("modifiers", [])
            )
            target = next(
                (
                    modifier
                    for modifier in modifiers
                    if modifier.get("id") == modifier_id
                ),
                None,
            )
            if target is None:
                return bool(success and completion_key in completed)
            if (
                target.get("reversal_state") != "in_progress"
                or target.get("reversal_claim_id") != claim_id
            ):
                warning(
                    f"EFFECTS: Reversal claim mismatch for {completion_key}",
                    category="effects_tracking",
                )
                return False

            if success:
                modifiers.remove(target)
                if completion_key not in completed:
                    completed.append(completion_key)
                    del completed[:-_COMPLETED_REVERSAL_LIMIT]
            else:
                target["reversal_state"] = "pending"
                target.pop("reversal_claim_id", None)
                target.pop("reversal_claimed_at", None)
        return True
    except Exception as exc:
        error(f"EFFECTS: Failed to acknowledge reversal {completion_key}: {exc}")
        return False


def apply_claimed_effect_reversal(reversal, update_function) -> bool:
    """Apply one claimed reversal and durably acknowledge its outcome."""
    character_name = reversal["character"]
    modifier = reversal["modifier"]
    claim_id = reversal["claim_id"]
    try:
        applied = update_function(character_name, reversal["description"])
    except Exception as exc:
        error(
            f"EFFECTS: Character reversal failed for {character_name}: {exc}",
            category="effects_tracking",
        )
        applied = False

    if applied is not True:
        released = complete_effect_reversal(
            character_name,
            modifier["id"],
            claim_id,
            success=False,
        )
        if not released:
            error(
                "EFFECTS: Failed reversal could not be released for retry; "
                f"claim remains explicit: {modifier['id']}",
                category="effects_tracking",
            )
        return False

    completed = complete_effect_reversal(
        character_name,
        modifier["id"],
        claim_id,
        success=True,
    )
    if not completed:
        error(
            "EFFECTS: Character was reversed but its durable claim could not "
            f"be completed: {modifier['id']}",
            category="effects_tracking",
        )
        return False
    return True

def check_and_apply_expirations() -> List[Dict[str, Any]]:
    """Claim expired effects and generate durable reversal actions."""
    reversals = []
    with _effects_tracker_transaction() as tracker:
        now = get_current_game_time()
        for character_name, char_data in tracker["characters"].items():
            if "modifiers" not in char_data:
                continue

            active_modifiers = []

            for modifier in char_data["modifiers"]:
                expired = False

                # Check time-based expiration.
                if (
                    "expires_at" in modifier
                    and modifier["expires_at"]
                    not in ["long_rest", "short_rest", "special"]
                ):
                    try:
                        expiration_time = datetime.fromisoformat(modifier["expires_at"])
                        if now >= expiration_time:
                            expired = True
                            info(
                                f"EFFECTS: Effect expired for {character_name}: "
                                f"{modifier['source']}",
                                category="effects_tracking",
                            )
                    except (TypeError, ValueError):
                        warning(f"Invalid expiration time for effect {modifier['id']}")

                if expired:
                    action_word = "loses" if modifier["value"] > 0 else "regains"
                    if (
                        modifier.get("affects_max", False)
                        and modifier["stat"] == "hitPoints"
                    ):
                        reversal_desc = (
                            f"{action_word} {abs(modifier['value'])} maximum hit "
                            f"points and {abs(modifier['value'])} current hit points "
                            f"as {modifier['source']} expires. Remove "
                            f"'{modifier['source']}' from temporaryEffects."
                        )
                    else:
                        reversal_desc = (
                            f"{action_word} {abs(modifier['value'])} "
                            f"{modifier['stat']} as {modifier['source']} expires. "
                            "Remove effect from temporaryEffects."
                        )

                    claim_id = _claim_effect_reversal(modifier, "expired")
                    if claim_id:
                        reversals.append(
                            _reversal_record(
                                character_name,
                                modifier,
                                claim_id,
                                reversal_desc,
                            )
                        )
                active_modifiers.append(modifier)

            char_data["modifiers"] = active_modifiers
    
    return reversals

def clear_rest_effects(character_name: str, rest_type: str) -> List[Dict[str, Any]]:
    """Claim effects that expire on rest without deleting them prematurely."""
    reversals = []
    with _effects_tracker_transaction() as tracker:
        normalized_name = normalize_character_name(character_name)

        if normalized_name not in tracker["characters"]:
            return reversals

        char_data = tracker["characters"][normalized_name]
        if "modifiers" not in char_data:
            return reversals

        active_modifiers = []

        for modifier in char_data["modifiers"]:
            should_clear = False

            # Check if this effect expires on this type of rest.
            if "expires_at" in modifier:
                if rest_type == "long_rest" and modifier["expires_at"] in [
                    "long_rest",
                    "short_rest",
                ]:
                    should_clear = True
                elif (
                    rest_type == "short_rest"
                    and modifier["expires_at"] == "short_rest"
                ):
                    should_clear = True

            if should_clear:
                action_word = "loses" if modifier["value"] > 0 else "regains"
                reversal_desc = (
                    f"{action_word} {abs(modifier['value'])} {modifier['stat']} "
                    f"as {modifier['source']} expires after "
                    f"{rest_type.replace('_', ' ')}"
                )

                claim_id = _claim_effect_reversal(
                    modifier, f"rest:{rest_type}"
                )
                if claim_id:
                    reversals.append(
                        _reversal_record(
                            character_name,
                            modifier,
                            claim_id,
                            reversal_desc,
                        )
                    )
                    info(
                        f"EFFECTS: Claimed rest effect for {character_name}: "
                        f"{modifier['source']}",
                        category="effects_tracking",
                    )
            active_modifiers.append(modifier)

        char_data["modifiers"] = active_modifiers
    
    return reversals

def update_character_effects(character_name: str, change_description: str) -> bool:
    """
    Main entry point for effects tracking.
    Analyzes character updates and tracks temporary effects.
    Also detects when rests occur to clear rest-based effects.
    """
    debug(f"EFFECTS: Analyzing potential effect for {character_name}: {change_description}", category="effects_tracking")
    
    rest_reversals_succeeded = True

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
                if not apply_claimed_effect_reversal(
                    reversal, update_character_info
                ):
                    rest_reversals_succeeded = False
        
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
        
        return success and rest_reversals_succeeded
    else:
        debug(f"EFFECTS: Effect not trackable: {change_description}", category="effects_tracking")
        return rest_reversals_succeeded

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