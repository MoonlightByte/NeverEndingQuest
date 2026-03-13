"""Provider-aware API client for multi-model support.

Routes API calls to the correct provider (OpenAI, Gemini, LM Studio)
based on the active MODEL_PROVIDER setting. Normalizes all responses
to the OpenAI response shape so callsites don't need provider-specific code.
"""
from utils.openai_client import get_openai_client


# ---------------------------------------------------------------------------
# OpenAI-shaped response wrappers for non-OpenAI providers
# ---------------------------------------------------------------------------

class _Usage:
    """Minimal wrapper matching openai.types.CompletionUsage."""
    __slots__ = ("prompt_tokens", "completion_tokens", "total_tokens")

    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _Message:
    """Minimal wrapper matching openai.types.chat.ChatCompletionMessage."""
    __slots__ = ("content", "role")

    def __init__(self, content, role="assistant"):
        self.content = content
        self.role = role


class _Choice:
    """Minimal wrapper matching openai.types.chat.ChatCompletionChoice."""
    __slots__ = ("message", "index", "finish_reason")

    def __init__(self, message, index=0, finish_reason="stop"):
        self.message = message
        self.index = index
        self.finish_reason = finish_reason


class _NormalizedResponse:
    """Wraps any provider response into the OpenAI ChatCompletion shape.

    Guarantees:
        response.choices[0].message.content  -> str
        response.usage.prompt_tokens         -> int
        response.usage.completion_tokens     -> int
        response.usage.total_tokens          -> int
    """
    __slots__ = ("choices", "usage", "model", "id")

    def __init__(self, content, usage_dict, model="", response_id=""):
        self.choices = [_Choice(_Message(content))]
        self.usage = _Usage(
            prompt_tokens=usage_dict.get("prompt_tokens", 0),
            completion_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("total_tokens", 0),
        )
        self.model = model
        self.id = response_id


# ---------------------------------------------------------------------------
# Reasoning effort -> Gemini thinking level mapping
# ---------------------------------------------------------------------------

_REASONING_TO_THINKING = {
    "none": "low",
    "low": "low",
    "medium": "high",
    "high": "high",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_client():
    """Get the appropriate API client for the current provider.

    For OpenAI / legacy / lmstudio this returns an openai.OpenAI instance.
    For Gemini the raw client is not directly useful at callsites -- use
    create_completion() instead.
    """
    return get_openai_client()


def create_completion(messages, model, temperature=None, **kwargs):
    """Provider-aware completion wrapper.

    Routes to OpenAI, Gemini, or LM Studio based on MODEL_PROVIDER.
    Returns an OpenAI-shaped response regardless of provider.

    Args:
        messages: list of {"role": ..., "content": ...} dicts (OpenAI format)
        model: model identifier string (e.g. config.DM_MAIN_MODEL)
        temperature: optional float temperature
        **kwargs: additional provider-specific kwargs (response_format,
                  reasoning_effort, etc.)

    Returns:
        An object with .choices[0].message.content and .usage attributes.
    """
    from model_config import MODEL_PROVIDER

    if MODEL_PROVIDER in ("legacy", "openai", "lmstudio"):
        return _openai_completion(messages, model, temperature, **kwargs)
    elif MODEL_PROVIDER == "gemini":
        return _gemini_completion(messages, model, temperature, **kwargs)
    else:
        raise ValueError(f"Unknown MODEL_PROVIDER: {MODEL_PROVIDER}")


# ---------------------------------------------------------------------------
# OpenAI / LM Studio path
# ---------------------------------------------------------------------------

def _openai_completion(messages, model, temperature, **kwargs):
    """Execute a completion via the OpenAI-compatible API."""
    client = get_openai_client()
    call_kwargs = {"model": model, "messages": messages}
    if temperature is not None:
        call_kwargs["temperature"] = temperature
    call_kwargs.update(kwargs)
    return client.chat.completions.create(**call_kwargs)


# ---------------------------------------------------------------------------
# Gemini path -- reuses helpers from utils/capture/gemini_caller.py
# ---------------------------------------------------------------------------

def _gemini_completion(messages, model, temperature, **kwargs):
    """Execute a completion via the Gemini API and return a normalized response.

    Reuses conversion and detection helpers from utils.capture.gemini_caller
    to avoid code duplication.
    """
    from google.genai import types
    from utils.capture.gemini_caller import (
        _get_client as gemini_get_client,
        convert_messages_to_gemini,
        expects_json_output,
        model_supports_thinking,
    )

    # --- Convert messages ---
    system_instruction, contents = convert_messages_to_gemini(messages)

    # --- Detect JSON mode ---
    use_json = expects_json_output(system_instruction, kwargs)

    # --- Build GenerateContentConfig kwargs ---
    config_kwargs = {}

    # System instruction
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    # Thinking level (mapped from reasoning_effort if provided)
    reasoning_effort = kwargs.pop("reasoning_effort", None)
    if reasoning_effort is not None and model_supports_thinking(model):
        thinking_level = _REASONING_TO_THINKING.get(
            str(reasoning_effort).lower(), "low"
        )
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=thinking_level
        )

    # Temperature -- per CLAUDE.md, do NOT set temperature for Gemini by default.
    # Gemini defaults to 1.0 and is optimized for that.
    # We intentionally ignore the caller's temperature here.

    # JSON response mode
    if use_json:
        config_kwargs["response_mime_type"] = "application/json"

    # Strip OpenAI-only kwargs that Gemini does not understand
    kwargs.pop("response_format", None)

    gen_config = types.GenerateContentConfig(**config_kwargs)

    # --- Convert contents to typed objects ---
    gemini_contents = [
        types.Content(
            role=c["role"],
            parts=[types.Part(text=p["text"]) for p in c["parts"]]
        )
        for c in contents
    ]

    # --- Execute ---
    client = gemini_get_client()
    response = client.models.generate_content(
        model=model,
        contents=gemini_contents,
        config=gen_config,
    )

    # --- Extract token usage ---
    usage_meta = getattr(response, "usage_metadata", None)
    usage_dict = {
        "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0) if usage_meta else 0,
        "completion_tokens": getattr(usage_meta, "candidates_token_count", 0) if usage_meta else 0,
        "total_tokens": getattr(usage_meta, "total_token_count", 0) if usage_meta else 0,
    }

    # --- Normalize to OpenAI shape ---
    return _NormalizedResponse(
        content=response.text,
        usage_dict=usage_dict,
        model=model,
    )
