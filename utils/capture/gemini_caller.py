"""Gemini variant caller for multi-model capture system.

Handles OpenAI->Gemini message format conversion and executes Gemini variant calls.
"""
import os
import threading
import time

_gemini_client = None
_client_lock = threading.Lock()


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
    system_instruction = None
    contents = []

    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")

        if role == "system":
            system_instruction = content
            continue

        # Map OpenAI roles to Gemini roles
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({
            "role": gemini_role,
            "parts": [{"text": content}]
        })

    return system_instruction, contents


def build_gemini_config(variant, caller_temperature=None, use_json=False):
    """Build the config dict for generate_content call.

    Args:
        variant: variant config dict with thinking_level and use_caller_temp
        caller_temperature: temperature from original callsite, or None
        use_json: True if original call used response_format json_object

    Returns:
        dict of config values (not yet a types.GenerateContentConfig object)
    """
    config = {
        "thinking_level": variant.get("thinking_level", "low")
    }

    if variant.get("use_caller_temp") and caller_temperature is not None:
        config["temperature"] = caller_temperature

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

    use_json = (
        caller_kwargs is not None
        and caller_kwargs.get("response_format", {}).get("type") == "json_object"
    )

    system_instruction, contents = convert_messages_to_gemini(messages)
    cfg = build_gemini_config(variant, caller_temperature, use_json)

    # Build GenerateContentConfig
    config_kwargs = {
        "thinking_config": types.ThinkingConfig(thinking_level=cfg["thinking_level"])
    }
    if "temperature" in cfg:
        config_kwargs["temperature"] = cfg["temperature"]
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
        model=variant["model"],
        contents=gemini_contents,
        config=gen_config,
    )
    latency_s = round(time.time() - start, 3)

    return response.text, latency_s
