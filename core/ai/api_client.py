"""Provider-aware API client for multi-model support.

Routes API calls to the correct provider (OpenAI, Gemini, LM Studio)
based on the active MODEL_PROVIDER setting. Normalizes all responses
to the OpenAI response shape so callsites don't need provider-specific code.

Escalation: Callsites pass retry_attempt=N and the wrapper applies
provider-native "try harder" logic (reasoning_effort for GPT-5.x,
thinking_level for Gemini, passthrough for legacy/LM Studio).
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
# Per-provider escalation ladders
# ---------------------------------------------------------------------------

# Each ladder maps retry_attempt -> provider-native parameter dict.
# Attempt 0 = default. Clamped to max index.

_ESCALATION_LADDERS = {
    "openai_5x": [
        # attempt 0: reasoning=none, temperature passes through
        {"reasoning_effort": "none"},
        # attempt 1: low reasoning, temperature stripped
        {"reasoning_effort": "low"},
        # attempt 2
        {"reasoning_effort": "medium"},
        # attempt 3
        {"reasoning_effort": "high"},
        # attempt 4+
        {"reasoning_effort": "high"},
    ],
    "openai_54": [
        {"reasoning_effort": "none"},
        {"reasoning_effort": "low"},
        {"reasoning_effort": "medium"},
        {"reasoning_effort": "high"},
        {"reasoning_effort": "xhigh"},
    ],
    "openai_5mini": [
        # GPT-5-mini: no "none", no temperature ever
        {"reasoning_effort": "low"},
        {"reasoning_effort": "medium"},
        {"reasoning_effort": "high"},
        {"reasoning_effort": "high"},
        {"reasoning_effort": "high"},
    ],
    "gemini_pro": [
        {"thinking_level": "low"},
        {"thinking_level": "medium"},
        {"thinking_level": "high"},
        {"thinking_level": "high"},
        {"thinking_level": "high"},
    ],
    "gemini_flash": [
        {"thinking_level": "minimal"},
        {"thinking_level": "low"},
        {"thinking_level": "medium"},
        {"thinking_level": "high"},
        {"thinking_level": "high"},
    ],
}


def _get_ladder_key(provider, model):
    """Determine which escalation ladder to use based on provider and model."""
    if provider in ("legacy", "lmstudio"):
        return None  # No escalation -- callsite handles temp reduction
    if provider == "openai":
        model_lower = model.lower() if model else ""
        if "mini" in model_lower:
            return "openai_5mini"
        if "5.4" in model_lower or "gpt-5.4" in model_lower:
            return "openai_54"
        return "openai_5x"
    if provider == "gemini":
        model_lower = model.lower() if model else ""
        if "pro" in model_lower:
            return "gemini_pro"
        return "gemini_flash"
    return None


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
    """Provider-aware completion wrapper with escalation support.

    Routes to OpenAI, Gemini, or LM Studio based on MODEL_PROVIDER.
    Returns an OpenAI-shaped response regardless of provider.

    This wrapper is a THIN routing layer. It does exactly three things:
    1. Route to the correct provider API
    2. Translate parameters natively for that provider
    3. Return the response

    It does NOT retry, validate, parse, track, or fall back.

    Args:
        messages: list of {"role": ..., "content": ...} dicts (OpenAI format)
        model: model identifier string (e.g. config.DM_MAIN_MODEL)
        temperature: optional float temperature (used by legacy/lmstudio,
                     GPT-5.x at reasoning=none only)
        retry_attempt: escalation level (0=default, 1+=try harder).
                       Consumed by wrapper, never forwarded to provider.
        **kwargs: additional kwargs. task_id is consumed for override lookup.
                  top_p is stripped. response_format uses _UNSET sentinel
                  (default=JSON mode, None=plain text, other=forwarded).
                  All other kwargs forwarded to provider.

    Returns:
        An object with .choices[0].message.content and .usage attributes.
    """
    from model_config import MODEL_PROVIDER, CALLSITE_OVERRIDES

    # --- Pop wrapper-only params (never forwarded to provider) ---
    task_id = kwargs.pop("task_id", None)
    kwargs.pop("top_p", None)
    _response_format = kwargs.pop("response_format", _UNSET)

    # --- Clamp retry_attempt ---
    retry_attempt = min(retry_attempt, 4)

    # --- Build merged params: escalation + overrides ---
    # Priority: explicit kwargs > CALLSITE_OVERRIDES[task_id][provider] > escalation > defaults
    merged = {}

    # 1. Escalation ladder (lowest priority among merged sources)
    ladder_key = _get_ladder_key(MODEL_PROVIDER, model)
    if ladder_key and retry_attempt >= 0:
        ladder = _ESCALATION_LADDERS[ladder_key]
        step = min(retry_attempt, len(ladder) - 1)
        merged.update(ladder[step])

    # 2. CALLSITE_OVERRIDES (mid priority)
    if task_id and task_id in CALLSITE_OVERRIDES:
        provider_overrides = CALLSITE_OVERRIDES[task_id].get(MODEL_PROVIDER, {})
        merged.update(provider_overrides)

    # 3. Explicit kwargs from callsite (highest priority)
    # These are already in kwargs and will be applied per-provider below.
    # We merge escalation/override params that aren't explicitly overridden:
    for key, val in merged.items():
        if key not in kwargs:
            kwargs[key] = val

    # --- Post-merge enforcement (hard API constraints) ---
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
            # Will be handled in _openai_completion by not passing temp
            kwargs["_strip_temperature"] = True

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

    # Thinking level (from escalation ladder or explicit kwarg)
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
