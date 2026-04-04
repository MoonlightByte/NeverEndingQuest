#!/usr/bin/env python3
"""
Prompt sanitization for DALL-E content policy violations.
Only used after a failure - no pre-processing.
"""

from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T089", "utils/prompt_sanitizer.py", 41)

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
        mini_cfg = config.MINI_UTIL_GEMINI_FLASH_MINIMAL
    elif MODEL_PROVIDER == "lmstudio":
        mini_cfg = config.MINI_UTIL_LMSTUDIO
    else:  # legacy
        mini_cfg = config.MINI_UTIL_LEGACY

    response = capture_and_fanout("T089", api_client.create_completion,
        messages=[
            {"role": "system", "content": "You are a prompt sanitizer. Return only the cleaned prompt text."},
            {"role": "user", "content": sanitization_request}
        ],
        model=mini_cfg["model"],
        temperature=0.3,
        response_format=None,
        **{k: v for k, v in mini_cfg.items() if k != "model"})

    return response.choices[0].message.content.strip()
