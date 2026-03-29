#!/usr/bin/env python3
"""
NPC Name Canonicalization Utility
Extracts canonical first names from complex D&D character names using AI normalization with persistent caching.

Examples:
- "James the Magnificent" → "James"
- "Sir Aldric Stoneheart" → "Aldric"
- "Scout Kira" → "Kira"
- "Brother Marcus of the Light" → "Marcus"
- "Lady Elara Moonwhisper" → "Elara"
- "Elder Dorun Ironforge" → "Dorun"
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

try:
    import openai
except ImportError:
    openai = None

from model_config import DM_MINI_MODEL
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.enhanced_logger import debug, info, warning, error

# Cache file location
CACHE_FILE = Path("data/companion_memories/name_normalization_cache.json")


def load_name_cache() -> Dict[str, str]:
    """Load the name normalization cache from disk"""
    if not CACHE_FILE.exists():
        return {}

    cache = safe_json_load(CACHE_FILE)
    if cache is None:
        return {}

    return cache


def save_name_cache(cache: Dict[str, str]) -> bool:
    """Save the name normalization cache to disk"""
    # Ensure directory exists
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    return safe_json_dump(cache, CACHE_FILE)


def simple_name_extraction(full_name: str) -> str:
    """Fallback heuristic for name extraction when AI is unavailable

    This is a last resort and not comprehensive - AI normalization is preferred.
    """
    if not full_name:
        return full_name

    # Split on spaces
    parts = full_name.split()

    if len(parts) == 1:
        return parts[0]

    # Common D&D titles to skip (expanded list)
    titles = {
        'Sir', 'Lord', 'Lady', 'Dame', 'Baron', 'Baroness', 'Count', 'Countess',
        'Duke', 'Duchess', 'King', 'Queen', 'Prince', 'Princess',
        'Captain', 'Commander', 'Lieutenant', 'Sergeant', 'General',
        'Scout', 'Ranger', 'Hunter', 'Tracker',
        'Cleric', 'Priest', 'Priestess', 'Brother', 'Sister', 'Father', 'Mother',
        'Elder', 'Ancient', 'Wise',
        'Knight', 'Paladin', 'Champion', 'Defender',
        'Wizard', 'Mage', 'Sorcerer', 'Warlock',
        'Bard', 'Minstrel', 'Troubadour',
        'Rogue', 'Thief', 'Assassin',
        'Fighter', 'Warrior', 'Gladiator',
        'Monk', 'Master',
        'Druid', 'Shaman',
        'Artificer', 'Inventor'
    }

    # If first word is a title, use second word
    if parts[0] in titles and len(parts) > 1:
        return parts[1]

    # Otherwise use first word
    return parts[0]


def call_mini_model_for_name(full_name: str) -> str:
    """Call the mini model to extract canonical name

    Args:
        full_name: The full character name to normalize

    Returns:
        The canonical first name

    Raises:
        Exception: If API call fails
    """
    if openai is None:
        raise RuntimeError("openai package unavailable")

    from config import OPENAI_API_KEY

    # Initialize OpenAI client
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""Extract the person's actual first name from this D&D character name: '{full_name}'

Examples:
- "Sir Aldric Stoneheart" → "Aldric"
- "James the Magnificent" → "James"
- "Scout Kira" → "Kira"
- "Brother Marcus of the Light" → "Marcus"
- "Lady Elara Moonwhisper" → "Elara"
- "Elder Dorun Ironforge" → "Dorun"

Return ONLY the first name, nothing else. No quotes, no explanation."""

    try:
        response = client.chat.completions.create(
            model=DM_MINI_MODEL,
            messages=[
                {"role": "system", "content": "You are a name extraction assistant. Extract only the person's actual first name from character names."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=20
        )

        canonical = response.choices[0].message.content.strip()

        # Remove any quotes that might have been added
        canonical = canonical.strip('"\'')

        debug(f"AI normalized '{full_name}' → '{canonical}'", category="name_normalization")

        return canonical

    except Exception as e:
        error(f"Failed to normalize name '{full_name}' via AI: {e}", category="name_normalization")
        raise


def get_canonical_name(full_name: str, skip_cache: bool = False) -> str:
    """Get canonical first name using cached AI normalization

    This function uses a persistent cache to avoid redundant API calls.
    On first encounter with a name, it calls the mini model to normalize it.
    Subsequent calls use the cached result.

    Args:
        full_name: The full character name (e.g., "Sir Aldric Stoneheart")
        skip_cache: If True, bypass cache and force AI normalization (for testing)

    Returns:
        The canonical first name (e.g., "Aldric")

    Examples:
        >>> get_canonical_name("James the Magnificent")
        "James"
        >>> get_canonical_name("Scout Kira")
        "Kira"
    """
    if not full_name:
        return full_name

    # Normalize input (trim whitespace)
    full_name = full_name.strip()

    # Load cache
    cache = load_name_cache()

    # Check cache first (unless explicitly skipping)
    if not skip_cache and full_name in cache:
        debug(f"Name cache hit: '{full_name}' → '{cache[full_name]}'", category="name_normalization")
        return cache[full_name]

    # Not in cache - need to normalize
    info(f"Name not in cache, normalizing: '{full_name}'", category="name_normalization")

    try:
        # Call AI for normalization
        canonical = call_mini_model_for_name(full_name)

        # Validate result (must be non-empty and reasonable)
        if not canonical or len(canonical) > 50:
            warning(f"AI returned suspicious name '{canonical}' for '{full_name}', using fallback",
                   category="name_normalization")
            canonical = simple_name_extraction(full_name)

        # Cache the result
        cache[full_name] = canonical
        save_name_cache(cache)

        info(f"Cached name normalization: '{full_name}' → '{canonical}'", category="name_normalization")

        return canonical

    except Exception as e:
        # API failed - use fallback heuristic
        warning(f"Name normalization API failed for '{full_name}': {e}", category="name_normalization")
        warning("Using fallback heuristic (less reliable)", category="name_normalization")

        canonical = simple_name_extraction(full_name)

        # Cache the fallback result to avoid repeated failures
        cache[full_name] = canonical
        save_name_cache(cache)

        return canonical


def get_canonical_names_batch(full_names: list) -> Dict[str, str]:
    """Get canonical names for multiple NPCs at once

    Args:
        full_names: List of full character names

    Returns:
        Dictionary mapping full names to canonical names

    Example:
        >>> get_canonical_names_batch(["Scout Kira", "Sir Aldric", "James the Magnificent"])
        {"Scout Kira": "Kira", "Sir Aldric": "Aldric", "James the Magnificent": "James"}
    """
    result = {}

    for full_name in full_names:
        result[full_name] = get_canonical_name(full_name)

    return result


def clear_name_cache():
    """Clear the entire name normalization cache (for testing/reset)"""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        info("Name normalization cache cleared", category="name_normalization")
    else:
        info("Name normalization cache already empty", category="name_normalization")


# Test function
if __name__ == "__main__":
    print("Testing NPC Name Canonicalizer\n")
    print("=" * 80)

    # Test cases
    test_names = [
        "Scout Kira",
        "Sir Aldric Stoneheart",
        "James the Magnificent",
        "Brother Marcus of the Light",
        "Lady Elara Moonwhisper",
        "Elder Dorun Ironforge",
        "Edda Ravenscroft",
        "Oswin Peverell",
        "Captain Sarah Brightshield"
    ]

    print("\nNormalizing test names:\n")
    for name in test_names:
        canonical = get_canonical_name(name)
        print(f"  '{name}' → '{canonical}'")

    print("\n" + "=" * 80)
    print("\nCache contents:")
    cache = load_name_cache()
    for full, canonical in cache.items():
        print(f"  '{full}' → '{canonical}'")

    print(f"\nTotal cached entries: {len(cache)}")
