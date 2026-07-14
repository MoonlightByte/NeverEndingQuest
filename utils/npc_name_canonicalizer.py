#!/usr/bin/env python3
"""
NPC Name Canonicalization Utility
Extracts canonical first names from complex D&D character names using AI normalization with persistent caching.

Examples:
- "James the Magnificent" -> "James"
- "Sir Aldric Stoneheart" -> "Aldric"
- "Scout Kira" -> "Kira"
- "Brother Marcus of the Light" -> "Marcus"
- "Lady Elara Moonwhisper" -> "Elara"
- "Elder Dorun Ironforge" -> "Dorun"
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T087", "utils/npc_name_canonicalizer.py", 162)
import config
from utils.atomic_json_cache import (
    merge_json_mapping,
    read_json_mapping,
    replace_json_mapping,
)
from utils.enhanced_logger import debug, info, warning, error

# Cache file location
CACHE_FILE = Path("data/companion_memories/name_normalization_cache.json")
_CACHE_CONTRACT_VERSION = "npc-name-v2"
_PROMPT_CONTRACT_VERSION = "first-name-only-v1"


def _mini_config_for_provider(provider):
    if provider == "openai":
        return config.MINI_UTIL_GPT54MINI_NONE
    if provider == "gemini":
        return config.MINI_UTIL_GEMINI_FLASH_LOW
    if provider == "lmstudio":
        return config.MINI_UTIL_LMSTUDIO
    return config.MINI_UTIL_LEGACY


def _name_cache_key(full_name, provider, model):
    payload = json.dumps(
        {
            "version": _CACHE_CONTRACT_VERSION,
            "prompt": _PROMPT_CONTRACT_VERSION,
            "provider": provider,
            "model": model,
            "name": full_name,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_valid_canonical_name(value):
    return (
        isinstance(value, str)
        and 0 < len(value) <= 50
        and not any(character.isspace() for character in value)
        and any(character.isalpha() for character in value)
        and all(character.isalpha() or character in "-'’" for character in value)
    )


def load_name_cache() -> Dict[str, str]:
    """Load the name normalization cache from disk"""
    return read_json_mapping(CACHE_FILE)


def save_name_cache(cache: Dict[str, str]) -> bool:
    """Save the name normalization cache to disk"""
    replace_json_mapping(CACHE_FILE, cache)
    return True


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


def call_mini_model_for_name(full_name: str, request_provider=None) -> str:
    """Call the mini model to extract canonical name

    Args:
        full_name: The full character name to normalize

    Returns:
        The canonical first name

    Raises:
        Exception: If API call fails
    """
    prompt = f"""Extract the person's actual first name from this D&D character name: '{full_name}'

Examples:
- "Sir Aldric Stoneheart" -> "Aldric"
- "James the Magnificent" -> "James"
- "Scout Kira" -> "Kira"
- "Brother Marcus of the Light" -> "Marcus"
- "Lady Elara Moonwhisper" -> "Elara"
- "Elder Dorun Ironforge" -> "Dorun"

Return ONLY the first name, nothing else. No quotes, no explanation."""

    try:
        import model_config

        provider = request_provider or model_config.get_provider()
        # Keep provider-to-config assignments explicit here: the semantic
        # callsite inventory audits the exact four configs feeding T087.
        if provider == "openai":
            mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
        elif provider == "gemini":
            mini_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
        elif provider == "lmstudio":
            mini_cfg = config.MINI_UTIL_LMSTUDIO
        else:
            mini_cfg = config.MINI_UTIL_LEGACY

        response = capture_and_fanout("T087", api_client.create_completion,
            _request_provider=provider,
            messages=[
                {"role": "system", "content": "You are a name extraction assistant. Extract only the person's actual first name from character names."},
                {"role": "user", "content": prompt}
            ],
            model=mini_cfg["model"],
            temperature=0.0,
            response_format=None,
            **{k: v for k, v in mini_cfg.items() if k != "model"})

        canonical = response.choices[0].message.content.strip()

        # Remove any quotes that might have been added
        canonical = canonical.strip('"\'')

        if not _is_valid_canonical_name(canonical):
            raise ValueError(f"T087 returned an invalid first-name token: {canonical!r}")

        debug(f"AI normalized '{full_name}' -> '{canonical}'", category="name_normalization")

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

    import model_config

    provider = model_config.get_provider()
    mini_cfg = _mini_config_for_provider(provider)
    cache_key = _name_cache_key(full_name, provider, mini_cfg["model"])

    # Load cache
    cache = load_name_cache()

    # Check cache first (unless explicitly skipping)
    if not skip_cache and cache_key in cache:
        cached_name = cache[cache_key]
        if _is_valid_canonical_name(cached_name):
            debug(f"Name cache hit: '{full_name}' -> '{cached_name}'", category="name_normalization")
            return cached_name

    # Not in cache - need to normalize
    info(f"Name not in cache, normalizing: '{full_name}'", category="name_normalization")

    try:
        # Call AI for normalization
        canonical = call_mini_model_for_name(
            full_name, request_provider=provider
        )

        # Cache only a response that satisfied the AI contract. The atomic
        # merge reloads the latest file under lock so parallel names cannot
        # erase one another.
        try:
            merge_json_mapping(CACHE_FILE, {cache_key: canonical})
        except Exception as cache_error:
            warning(
                f"Could not persist name normalization cache: {cache_error}",
                category="name_normalization",
            )

        info(f"Cached name normalization: '{full_name}' -> '{canonical}'", category="name_normalization")

        return canonical

    except Exception as e:
        # API failed - use fallback heuristic
        warning(f"Name normalization API failed for '{full_name}': {e}", category="name_normalization")
        warning("Using fallback heuristic (less reliable)", category="name_normalization")

        canonical = simple_name_extraction(full_name)

        # A heuristic is a recoverable fallback, not a successful model
        # result. Do not cache it; a later healthy provider call can heal it.
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
        replace_json_mapping(CACHE_FILE, {})
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
        print(f"  '{name}' -> '{canonical}'")

    print("\n" + "=" * 80)
    print("\nCache contents:")
    cache = load_name_cache()
    for full, canonical in cache.items():
        print(f"  '{full}' -> '{canonical}'")

    print(f"\nTotal cached entries: {len(cache)}")
