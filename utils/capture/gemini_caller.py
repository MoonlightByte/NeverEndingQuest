"""Gemini variant caller for multi-model capture system.

Handles OpenAI->Gemini message format conversion and executes Gemini variant calls.

Key fix (2026-02-22): Always set response_mime_type="application/json" for calls
that expect JSON output. This prevents Gemini from returning plain prose or
markdown-wrapped JSON, which was causing validation failures.
"""
import os
import re
import threading
import time

_gemini_client = None
_client_lock = threading.Lock()

# Patterns that indicate the call expects JSON output
JSON_INDICATOR_PATTERNS = [
    r'@FMT\s*=',           # Compressed prompt format marker
    r'"narration"',         # DM response schema
    r'"actions"\s*:',       # Action array in schema
    r'respond.*JSON',       # "respond with JSON"
    r'output.*JSON',        # "output JSON"
    r'return.*JSON',        # "return JSON"
    r'JSON\s+object',       # "JSON object"
    r'valid\s+JSON',        # "valid JSON"
    r'\{["\'].*["\']:',     # JSON object literal in prompt
]

# Models that support thinking_config
THINKING_SUPPORTED_MODELS = [
    "gemini-2.0-flash-thinking",
    "gemini-3-flash",
    "gemini-3-pro",
]


def _get_client():
    global _gemini_client
    if _gemini_client is None:
        with _client_lock:
            if _gemini_client is None:
                from google import genai
                # Look for API key file in project root (where run_web.py runs)
                import sys
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                api_key_file = os.path.join(project_root, "google_api.pi")
                if os.path.exists(api_key_file):
                    with open(api_key_file, 'r') as f:
                        content = f.read().strip()
                        if 'api_key=' in content:
                            api_key = content.split('api_key=')[1].strip()
                        else:
                            api_key = content
                else:
                    raise FileNotFoundError(
                        f"google_api.pi not found at {api_key_file} - Gemini API key required for capture"
                    )
                os.environ['GEMINI_API_KEY'] = api_key
                _gemini_client = genai.Client()
    return _gemini_client


def convert_messages_to_gemini(messages):
    """Convert OpenAI messages format to Gemini contents format.

    Args:
        messages: list of {"role": "system"|"user"|"assistant", "content": "..."}

    Returns:
        tuple of (system_instruction_str_or_None, contents_list)
        where contents_list items are {"role": "user"|"model", "parts": [{"text": "..."}]}
    """
    system_parts = []
    contents = []

    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")

        if role == "system":
            # Concatenate all system messages (don't overwrite)
            system_parts.append(content)
            continue

        # Map OpenAI roles to Gemini roles
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({
            "role": gemini_role,
            "parts": [{"text": content}]
        })

    # Join all system messages with double newlines
    system_instruction = "\n\n".join(system_parts) if system_parts else None

    # Gemini requires at least one content item. If only system messages were provided,
    # inject a minimal user message to trigger execution.
    if not contents and system_instruction:
        contents.append({
            "role": "user",
            "parts": [{"text": "Execute the above instructions."}]
        })

    return system_instruction, contents


def expects_json_output(system_instruction, caller_kwargs=None):
    """Detect if this call expects JSON output based on prompt content.

    Args:
        system_instruction: The concatenated system prompt
        caller_kwargs: Original call kwargs (may contain response_format)

    Returns:
        True if JSON output is expected
    """
    # Explicit response_format from original call
    if (caller_kwargs is not None
            and caller_kwargs.get("response_format", {}).get("type") == "json_object"):
        return True

    # Check system prompt for JSON indicators
    if system_instruction:
        for pattern in JSON_INDICATOR_PATTERNS:
            if re.search(pattern, system_instruction, re.IGNORECASE):
                return True

    return False


def model_supports_thinking(model_name):
    """Check if the model supports thinking_config.

    Args:
        model_name: The Gemini model identifier

    Returns:
        True if thinking_config is supported
    """
    model_lower = model_name.lower()
    for supported in THINKING_SUPPORTED_MODELS:
        if supported in model_lower:
            return True
    return False


def build_gemini_config(variant, caller_temperature=None, use_json=False):
    """Build the config dict for generate_content call.

    Args:
        variant: variant config dict with thinking_level and use_caller_temp
        caller_temperature: temperature from original callsite, or None
        use_json: True if JSON output is expected (detected or explicit)

    Returns:
        dict of config values (not yet a types.GenerateContentConfig object)
    """
    config = {}

    # Only include thinking_level for models that support it
    # (will be checked again in call_gemini_variant with actual model name)
    if "thinking_level" in variant:
        config["thinking_level"] = variant["thinking_level"]

    if variant.get("use_caller_temp") and caller_temperature is not None:
        config["temperature"] = caller_temperature

    # CRITICAL FIX: Always set response_mime_type when JSON is expected
    # This prevents Gemini from returning plain prose or markdown-wrapped JSON
    if use_json:
        config["response_mime_type"] = "application/json"

    return config


def call_gemini_variant(variant, messages, caller_temperature=None, caller_kwargs=None):
    """Execute one Gemini variant call and return (content, latency_s).

    Args:
        variant: variant config dict
        messages: original OpenAI-format messages list
        caller_temperature: temperature from original callsite, or None
        caller_kwargs: other kwargs from original call (response_format etc)

    Returns:
        tuple of (content_str, latency_seconds)

    Raises:
        Exception: any API error - caller should catch
    """
    from google.genai import types

    # Convert messages and extract system instruction
    system_instruction, contents = convert_messages_to_gemini(messages)

    # Detect if JSON output is expected (IMPROVED: checks prompt content too)
    use_json = expects_json_output(system_instruction, caller_kwargs)

    # Build config
    cfg = build_gemini_config(variant, caller_temperature, use_json)

    # Build GenerateContentConfig
    config_kwargs = {}

    # Only add thinking_config for models that support it
    model_name = variant.get("model", "")
    if model_supports_thinking(model_name) and "thinking_level" in cfg:
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=cfg["thinking_level"]
        )

    if "temperature" in cfg:
        config_kwargs["temperature"] = cfg["temperature"]

    # CRITICAL: Set response_mime_type for JSON-expecting calls
    if "response_mime_type" in cfg:
        config_kwargs["response_mime_type"] = cfg["response_mime_type"]

    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    gen_config = types.GenerateContentConfig(**config_kwargs)

    # Convert contents to types.Content objects
    gemini_contents = [
        types.Content(
            role=c["role"],
            parts=[types.Part(text=p["text"]) for p in c["parts"]]
        )
        for c in contents
    ]

    client = _get_client()
    start = time.time()
    response = client.models.generate_content(
        model=model_name,
        contents=gemini_contents,
        config=gen_config,
    )
    latency_s = round(time.time() - start, 3)

    # Extract token usage from response.usage_metadata
    usage = getattr(response, 'usage_metadata', None)
    token_usage = {
        "prompt_tokens": getattr(usage, 'prompt_token_count', 0) if usage else 0,
        "completion_tokens": getattr(usage, 'candidates_token_count', 0) if usage else 0,
        "total_tokens": getattr(usage, 'total_token_count', 0) if usage else 0,
    }

    return response.text, latency_s, token_usage
