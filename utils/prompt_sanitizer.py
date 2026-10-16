#!/usr/bin/env python3
"""
Prompt rewrite after a DALL-E content-policy refusal (T089).
Only used after a refusal - no pre-processing. The model returns a typed
{"prompt": "..."} object; code uses that field or makes no rewrite (#855).
"""

import json
from typing import Optional

from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T089", "utils/prompt_sanitizer.py", 61)


def rewritten_prompt(original: str, raw) -> Optional[str]:
    """The typed ``prompt`` field of a T089 reply when it is a non-empty string
    that differs from the original prompt; otherwise None (no rewrite)."""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    candidate = value.get("prompt") if isinstance(value, dict) else None
    if not isinstance(candidate, str) or not candidate.strip():
        return None
    candidate = candidate.strip()
    return None if candidate == str(original or "").strip() else candidate


def sanitize_prompt(prompt: str) -> Optional[str]:
    """
    Rewrite a prompt that DALL-E refused, keeping the narrative.
    Returns the rewritten prompt, or None when T089 gives no usable rewrite.
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

Return a JSON object with one field: {"prompt": "<the rewritten prompt>"}."""

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
                {"role": "system", "content": "You are a prompt sanitizer. Return a JSON object with one field, prompt."},
                {"role": "user", "content": sanitization_request}
            ],
            model=mini_cfg["model"],
            temperature=0.3,
            response_format={"type": "json_object"},
            **{k: v for k, v in mini_cfg.items() if k != "model"})
        return rewritten_prompt(prompt, response.choices[0].message.content)
    except Exception:
        return None
