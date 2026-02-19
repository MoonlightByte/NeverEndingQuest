#!/usr/bin/env python3
"""
Prompt sanitization for DALL-E content policy violations.
Only used after a failure - no pre-processing.
"""

from openai import OpenAI
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T089", "utils/prompt_sanitizer.py", 33)
import re
from model_config import DM_MINI_MODEL

def sanitize_prompt(prompt: str) -> str:
    """
    Sanitize a prompt that was rejected by DALL-E.
    Uses GPT-4-mini to clean problematic content while preserving narrative.
    """
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    
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

    response = capture_and_fanout("T089", client.chat.completions.create, messages=[
            {"role": "system", "content": "You are a prompt sanitizer. Return only the cleaned prompt text."},
            {"role": "user", "content": sanitization_request}
        ], model=DM_MINI_MODEL,
        temperature=0.3
    )
    
    return response.choices[0].message.content.strip()