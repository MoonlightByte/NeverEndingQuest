"""Provider-aware API client for multi-model support.

Routes API calls to the correct provider (OpenAI, Gemini, LM Studio)
based on the active MODEL_PROVIDER setting. Normalizes all responses
to the OpenAI response shape so callsites don't need provider-specific code.

create_completion() is a thin routing layer. Callsites own their
model and params via named config dicts in model_config.py.
"""
from utils.openai_client import get_openai_client

_UNSET = object()  # sentinel: distinguishes "not provided" from "explicitly None"


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
# Public API
# ---------------------------------------------------------------------------

def get_client():
    """Get the appropriate API client for the current provider.

    For OpenAI / legacy / lmstudio this returns an openai.OpenAI instance.
    For Gemini the raw client is not directly useful at callsites -- use
    create_completion() instead.
    """
    return get_openai_client()


def create_completion(messages, model, temperature=None, retry_attempt=0, **kwargs):
    """Provider-aware completion wrapper -- thin routing layer.

    Routes to OpenAI, Gemini, or LM Studio based on MODEL_PROVIDER.
    Returns an OpenAI-shaped response regardless of provider.

    This wrapper does exactly two things:
    1. Route to the correct provider API
    2. Translate parameters natively for that provider

    It does NOT inject reasoning_effort, thinking_level, or other params.
    The callsite owns its parameters via named config dicts in model_config.py.

    Args:
        messages: list of {"role": ..., "content": ...} dicts (OpenAI format)
        model: model identifier string (e.g. "gpt-5.2", "gemini-3.1-pro-preview")
        temperature: optional float temperature (used by legacy/lmstudio,
                     GPT-5.x at reasoning=none only)
        retry_attempt: unused (kept for backwards compatibility)
        **kwargs: provider-specific params from callsite config dicts
                  (reasoning_effort, thinking_level, etc.).
                  top_p is stripped. response_format uses _UNSET sentinel
                  (default=JSON mode, None=plain text, other=forwarded).

    Returns:
        An object with .choices[0].message.content and .usage attributes.
    """
    from model_config import MODEL_PROVIDER

    # --- Pop wrapper-only params (never forwarded to provider) ---
    task_id = kwargs.pop("task_id", None)
    kwargs.pop("top_p", None)
    _response_format = kwargs.pop("response_format", _UNSET)

    # create_completion() is a thin routing layer. It does NOT inject
    # reasoning_effort, thinking_level, or other params. The callsite
    # owns its parameters via named config dicts in model_config.py.

    # --- Enforce hard API constraints ---
    _enforce_provider_constraints(MODEL_PROVIDER, model, temperature, kwargs)

    # --- Route to provider ---
    if MODEL_PROVIDER in ("legacy", "openai", "lmstudio"):
        return _openai_completion(messages, model, temperature, MODEL_PROVIDER,
                                  response_format=_response_format, **kwargs)
    elif MODEL_PROVIDER == "gemini":
        return _gemini_completion(messages, model, temperature,
                                 response_format=_response_format, **kwargs)
    else:
        raise ValueError(f"Unknown MODEL_PROVIDER: {MODEL_PROVIDER}")


def _enforce_provider_constraints(provider, model, temperature, kwargs):
    """Apply hard API constraints after merge. Mutates kwargs in place."""
    if provider == "openai":
        model_lower = model.lower() if model else ""
        reasoning = kwargs.get("reasoning_effort")

        # GPT-5-mini: NEVER supports temperature
        if "mini" in model_lower and "5" in model_lower:
            kwargs["_strip_temperature"] = True
            # gpt-5-mini does not support reasoning_effort="none"
            if reasoning and str(reasoning).lower() == "none":
                kwargs["reasoning_effort"] = "low"

        # GPT-5.x with reasoning > none: temperature must be stripped
        elif reasoning and str(reasoning).lower() != "none":
            kwargs["_strip_temperature"] = True

    elif provider == "gemini":
        # Gemini ignores temperature -- handled in _gemini_completion
        pass


# ---------------------------------------------------------------------------
# OpenAI / LM Studio path
# ---------------------------------------------------------------------------

def _openai_completion(messages, model, temperature, provider, response_format=_UNSET, **kwargs):
    """Execute a completion via the OpenAI-compatible API."""
    client = get_openai_client()

    # Pop internal flags
    strip_temp = kwargs.pop("_strip_temperature", False)

    call_kwargs = {"model": model, "messages": messages}

    # Temperature: pass through unless stripped by constraint enforcement
    if temperature is not None and not strip_temp:
        call_kwargs["temperature"] = temperature

    # JSON mode: default ON, opt-out with response_format=None
    if response_format is _UNSET:
        call_kwargs["response_format"] = {"type": "json_object"}
    elif response_format is not None:
        call_kwargs["response_format"] = response_format
    # else: response_format=None means plain text (no JSON mode)

    # Forward remaining kwargs (reasoning_effort, max_tokens, etc.)
    call_kwargs.update(kwargs)

    return client.chat.completions.create(**call_kwargs)


# ---------------------------------------------------------------------------
# Gemini path -- reuses helpers from utils/capture/gemini_caller.py
# ---------------------------------------------------------------------------

def _gemini_completion(messages, model, temperature, response_format=_UNSET, **kwargs):
    """Execute a completion via the Gemini API and return a normalized response.

    Reuses conversion and detection helpers from utils.capture.gemini_caller
    to avoid code duplication.
    """
    from google.genai import types
    from utils.capture.gemini_caller import (
        _get_client as gemini_get_client,
        convert_messages_to_gemini,
        model_supports_thinking,
    )

    # --- Pop Gemini-specific params from kwargs ---
    thinking_level = kwargs.pop("thinking_level", None)
    # Pop OpenAI-only params that Gemini doesn't understand
    kwargs.pop("reasoning_effort", None)
    kwargs.pop("_strip_temperature", None)

    # Translate max_tokens -> max_output_tokens for Gemini
    max_tokens = kwargs.pop("max_tokens", None)

    # --- Convert messages ---
    system_instruction, contents = convert_messages_to_gemini(messages)

    # --- Build GenerateContentConfig kwargs ---
    config_kwargs = {}

    # System instruction
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    # Thinking level (from callsite kwarg)
    if thinking_level is not None and model_supports_thinking(model):
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=thinking_level
        )

    # Temperature -- per CLAUDE.md, do NOT set temperature for Gemini.
    # Gemini defaults to 1.0 and is optimized for that.

    # JSON mode: default ON (_UNSET), respect explicit JSON format, skip for None (plain text)
    if response_format is _UNSET:
        config_kwargs["response_mime_type"] = "application/json"
    elif isinstance(response_format, dict) and response_format.get("type") in ("json_object", "json_schema"):
        config_kwargs["response_mime_type"] = "application/json"
    # else: response_format=None or unrecognized format means plain text (no JSON mode)

    # max_output_tokens (translated from max_tokens)
    if max_tokens is not None:
        config_kwargs["max_output_tokens"] = max_tokens

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
