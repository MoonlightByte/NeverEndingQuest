#!/usr/bin/env python3
"""
Prompt sanitization for DALL-E content policy violations.
Only used after a failure - no pre-processing.
"""

import re

from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T089", "utils/prompt_sanitizer.py", 87)


_SAFE_REPLACEMENTS = (
    (r"\bslit (?:their|his|her|my|your) throat\b", "seriously harm them"),
    (r"\bgut (?:me|him|her|them|you)\b", "harm them"),
    (r"\bdisembowel(?:ed|ing)?\b", "gravely injure"),
    (r"\bgore\b", "signs of violence"),
    (r"\bcult(?:ist|ists|s)?\b", "shadowy group"),
    (r"\b(?:hallucinogen|narcotic|opium)\w*\b", "strange brew"),
)


def deterministic_sanitize_prompt(prompt: str) -> str:
    """Provide a local recovery prompt when the T089 provider is unavailable."""
    cleaned = " ".join(str(prompt or "").split())
    for pattern, replacement in _SAFE_REPLACEMENTS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:blood-soaked|bloodied|bloody|mutilated)\b",
        "weathered",
        cleaned,
        flags=re.IGNORECASE,
    )
    if cleaned == " ".join(str(prompt or "").split()):
        cleaned = (
            "Atmospheric dark-fantasy scene with implied danger, no graphic "
            f"violence: {cleaned}"
        )
    return cleaned.strip()


def _usable_sanitized_prompt(original: str, candidate: str) -> bool:
    if not isinstance(candidate, str):
        return False
    normalized = candidate.strip()
    if not normalized or normalized == str(original or "").strip():
        return False
    if "```" in normalized or normalized.startswith(("{", "[")):
        return False
    lower = normalized.lower()
    if lower.startswith(("here is", "sanitized prompt:", "explanation:")):
        return False
    return True

def sanitize_prompt(prompt: str) -> str:
    """
    Sanitize a prompt that was rejected by DALL-E.
    Uses AI to clean problematic content while preserving narrative.
    """
    sanitization_request = """You are a prompt sanitizer for DALL-E 3. The following prompt was rejected for content policy violations.

Your task is to rewrite it to be safe while preserving the dark fantasy atmosphere. Make these replacements:
- Replace graphic violence ("gut me", "slit throat", etc.) with implied threats ("harm me", "threaten me")
- Replace "cult" with "secret group" or "shadowy organization"
- Replace mind-altering substances with "strange brew" or "mysterious concoction"
- Reduce explicit fear/horror descriptions to atmospheric tension
- Remove gore or body horror elements
- Keep the narrative coherent and atmospheric

Original prompt: """ + prompt + """

Return ONLY the sanitized prompt, no explanations."""

    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
    elif MODEL_PROVIDER == "gemini":
        mini_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
    elif MODEL_PROVIDER == "lmstudio":
        mini_cfg = config.MINI_UTIL_LMSTUDIO
    else:  # legacy
        mini_cfg = config.MINI_UTIL_LEGACY

    try:
        response = capture_and_fanout("T089", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=[
                {"role": "system", "content": "You are a prompt sanitizer. Return only the cleaned prompt text."},
                {"role": "user", "content": sanitization_request}
            ],
            model=mini_cfg["model"],
            temperature=0.3,
            response_format=None,
            **{k: v for k, v in mini_cfg.items() if k != "model"})
        candidate = response.choices[0].message.content.strip()
        if _usable_sanitized_prompt(prompt, candidate):
            return candidate
    except Exception:
        pass

    return deterministic_sanitize_prompt(prompt)
