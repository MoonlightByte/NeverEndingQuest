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
# Provider-neutral errors and OpenAI-shaped response wrappers
# ---------------------------------------------------------------------------

class ProviderCallError(RuntimeError):
    """Transport/provider failure with stable request correlation metadata."""

    def __init__(self, provider, model, task_id=None, original_error=None, message=None):
        self.provider = provider
        self.model = model
        self.task_id = task_id
        self.original_error = original_error
        task_label = task_id or "unregistered"
        detail = message or (
            f"{type(original_error).__name__}: {original_error}"
            if original_error is not None
            else "unknown provider error"
        )
        super().__init__(
            f"{provider} call failed for {task_label} using {model}: {detail}"
        )


class ProviderEmptyResponse(ProviderCallError):
    """Provider returned no usable text for a callsite that requires content."""

    def __init__(
        self,
        provider,
        model,
        task_id=None,
        finish_reason=None,
        original_error=None,
    ):
        self.finish_reason = finish_reason
        reason = finish_reason or "unknown"
        super().__init__(
            provider=provider,
            model=model,
            task_id=task_id,
            original_error=original_error,
            message=f"empty/non-text response (finish_reason={reason})",
        )

class _Usage:
    """Minimal wrapper matching openai.types.CompletionUsage."""
    __slots__ = ("prompt_tokens", "completion_tokens", "total_tokens")

    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens

    def model_dump(self):
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


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
    __slots__ = (
        "choices",
        "usage",
        "model",
        "id",
        "provider",
        "task_id",
        "raw_response",
    )

    def __init__(
        self,
        content,
        usage_dict,
        model="",
        response_id="",
        finish_reason="stop",
        provider="",
        task_id=None,
        raw_response=None,
    ):
        self.choices = [
            _Choice(_Message(content), finish_reason=finish_reason or "unknown")
        ]
        self.usage = _Usage(
            prompt_tokens=usage_dict.get("prompt_tokens", 0),
            completion_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("total_tokens", 0),
        )
        self.model = model
        self.id = response_id
        self.provider = provider
        self.task_id = task_id
        self.raw_response = raw_response

    def model_dump(self):
        return {
            "id": self.id,
            "model": self.model,
            "provider": self.provider,
            "task_id": self.task_id,
            "choices": [
                {
                    "index": self.choices[0].index,
                    "finish_reason": self.choices[0].finish_reason,
                    "message": {
                        "role": self.choices[0].message.role,
                        "content": self.choices[0].message.content,
                    },
                }
            ],
            "usage": self.usage.model_dump(),
        }


def _integer_token_count(value):
    return int(value) if isinstance(value, (int, float)) else 0


def _finish_reason_value(value):
    if isinstance(value, str):
        return value
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    raw_value = getattr(value, "value", None)
    if isinstance(raw_value, str):
        return raw_value
    return "unknown"


def _normalize_provider_response(response, provider, requested_model, task_id=None):
    """Return one response shape or raise a correlated empty-response error."""
    content = None
    finish_reason = "unknown"
    content_error = None

    choices = getattr(response, "choices", None) if response is not None else None
    if isinstance(choices, (list, tuple)) and choices:
        choice = choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None) if message is not None else None
        finish_reason = _finish_reason_value(getattr(choice, "finish_reason", None))
    elif response is not None:
        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, (list, tuple)) and candidates:
            finish_reason = _finish_reason_value(
                getattr(candidates[0], "finish_reason", None)
            )
        try:
            content = response.text
        except Exception as exc:
            content_error = exc

    if not isinstance(content, str) or not content.strip():
        raise ProviderEmptyResponse(
            provider=provider,
            model=requested_model,
            task_id=task_id,
            finish_reason=finish_reason,
            original_error=content_error,
        )

    usage = getattr(response, "usage", None)
    if usage is not None:
        usage_dict = {
            "prompt_tokens": _integer_token_count(
                getattr(usage, "prompt_tokens", 0)
            ),
            "completion_tokens": _integer_token_count(
                getattr(usage, "completion_tokens", 0)
            ),
            "total_tokens": _integer_token_count(getattr(usage, "total_tokens", 0)),
        }
    else:
        usage_meta = getattr(response, "usage_metadata", None)
        usage_dict = {
            "prompt_tokens": _integer_token_count(
                getattr(usage_meta, "prompt_token_count", 0)
            ),
            "completion_tokens": _integer_token_count(
                getattr(usage_meta, "candidates_token_count", 0)
            ),
            "total_tokens": _integer_token_count(
                getattr(usage_meta, "total_token_count", 0)
            ),
        }

    reported_model = getattr(response, "model", None)
    if not isinstance(reported_model, str) or not reported_model:
        reported_model = requested_model
    response_id = getattr(response, "id", None)
    if not isinstance(response_id, str):
        response_id = ""

    return _NormalizedResponse(
        content=content,
        usage_dict=usage_dict,
        model=reported_model,
        response_id=response_id,
        finish_reason=finish_reason,
        provider=provider,
        task_id=task_id,
        raw_response=response,
    )


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
    import model_config

    # --- Pop wrapper-only params (never forwarded to provider) ---
    task_id = kwargs.pop("task_id", None)
    request_provider = kwargs.pop("_request_provider", None)
    if request_provider is None:
        # Backward-compatible fallback for infrastructure probes and any caller
        # not yet routed through capture_and_fanout. Runtime callsites pass the
        # provider snapshot used to select their config.
        request_provider = model_config.get_provider()
    if request_provider not in model_config.PROVIDER_MODELS:
        raise ValueError(f"Unknown request provider: {request_provider}")
    kwargs.pop("top_p", None)
    _response_format = kwargs.pop("response_format", _UNSET)

    # create_completion() is a thin routing layer. It does NOT inject
    # reasoning_effort, thinking_level, or other params. The callsite
    # owns its parameters via named config dicts in model_config.py.

    # --- Enforce hard API constraints ---
    _enforce_provider_constraints(request_provider, model, temperature, kwargs)

    # --- Route to provider, then expose one response/error contract ---
    try:
        if request_provider in ("legacy", "openai", "lmstudio"):
            raw_response = _openai_completion(
                messages,
                model,
                temperature,
                request_provider,
                response_format=_response_format,
                **kwargs,
            )
        else:  # gemini
            raw_response = _gemini_completion(
                messages,
                model,
                temperature,
                response_format=_response_format,
                **kwargs,
            )
    except ProviderCallError:
        raise
    except Exception as exc:
        raise ProviderCallError(
            provider=request_provider,
            model=model,
            task_id=task_id,
            original_error=exc,
        ) from exc

    return _normalize_provider_response(
        raw_response,
        provider=request_provider,
        requested_model=model,
        task_id=task_id,
    )


def _enforce_provider_constraints(provider, model, temperature, kwargs):
    """Apply hard API constraints after merge. Mutates kwargs in place."""
    if provider == "openai":
        model_lower = model.lower() if model else ""
        reasoning = kwargs.get("reasoning_effort")

        # Mini model constraints -- substring matching:
        #   "5-mini" matches "gpt-5-mini" but NOT "gpt-5.4-mini" (dot breaks the match)
        #   "5.4-mini" matches "gpt-5.4-mini" only
        # NOTE: Future mini variants (gpt-5.5-mini etc.) will fall through to the
        # general GPT-5.x branch. Add explicit branches for new mini models as needed.
        if "5-mini" in model_lower:
            # gpt-5-mini: NEVER supports temperature, no reasoning_effort="none"
            kwargs["_strip_temperature"] = True
            if reasoning and str(reasoning).lower() == "none":
                kwargs["reasoning_effort"] = "low"
        elif "5.4-mini" in model_lower:
            # gpt-5.4-mini: supports temperature ONLY with reasoning=none
            if reasoning and str(reasoning).lower() != "none":
                kwargs["_strip_temperature"] = True
        # GPT-5.x (non-mini) with reasoning > none: temperature must be stripped
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
    client = get_openai_client(provider=provider)

    # Issue #120: honor a user-set custom model for the Local/Custom provider
    # WITHOUT touching any of the 67 per-callsite model dicts. Empty => keep the
    # callsite's own model string. Scoped to lmstudio only; no other provider or
    # param is affected (create_completion remains a thin router).
    if provider == "lmstudio":
        import model_config
        _local_model = model_config.get_local_endpoint().get("model")
        if _local_model:
            model = _local_model

        # LM Studio/OpenAI-compatible servers do not agree on support for the
        # OpenAI ``json_object`` response mode. Older LM Studio versions reject
        # it before inference (HTTP 400, accepting only ``json_schema`` or
        # ``text``). Local callsites already carry explicit JSON instructions
        # and production parsers/retries, so omit only this unsupported mode at
        # the provider adapter. Preserve an explicit json_schema for endpoints
        # that support it, and leave OpenAI/legacy behavior unchanged.
        if response_format is _UNSET or (
            isinstance(response_format, dict)
            and response_format.get("type") == "json_object"
        ):
            response_format = None

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
    response_schema = kwargs.pop("response_schema", None)
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

    # Gemini response_schema: constrains JSON output to a specific structure.
    # Auto-converted at runtime from the callsite's existing JSON schema file.
    if response_schema is not None:
        config_kwargs["response_schema"] = response_schema

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

    # Normalization is centralized in create_completion() so OpenAI, Gemini,
    # legacy, and Local/Custom all expose identical response/error semantics.
    return response
