"""OpenAI variant caller for production-shaped model comparisons.

The variant changes only model identity, reasoning effort, and the model's
temperature compatibility. Callsite-owned schemas, formats, token ceilings,
and other supported request options are copied from the real request.
"""

import time

from openai import OpenAI


_client = None


def _get_client():
    global _client
    if _client is None:
        import config

        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def build_openai_params(
    variant, messages, caller_temperature=None, caller_kwargs=None
):
    """Build detached SDK kwargs without changing the callsite contract."""
    params = {"model": variant["model"], "messages": messages}

    if variant.get("reasoning_effort") is not None:
        params["reasoning_effort"] = variant["reasoning_effort"]
    if variant.get("use_caller_temp") and caller_temperature is not None:
        params["temperature"] = caller_temperature

    allowed_callsite_options = (
        "response_format",
        "max_tokens",
        "max_completion_tokens",
        "seed",
        "stop",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "frequency_penalty",
        "presence_penalty",
        "logit_bias",
        "user",
    )
    for name in allowed_callsite_options:
        if caller_kwargs and name in caller_kwargs and caller_kwargs[name] is not None:
            params[name] = caller_kwargs[name]
    return params


def call_openai_variant(
    variant, messages, caller_temperature=None, caller_kwargs=None
):
    """Execute one comparison and return content, latency, and detailed usage."""
    params = build_openai_params(
        variant, messages, caller_temperature, caller_kwargs
    )
    start = time.time()
    response = _get_client().chat.completions.create(**params)
    latency_s = round(time.time() - start, 3)
    usage = response.usage
    token_usage = {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "cached_tokens": getattr(
            getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0
        ) or 0,
        "reasoning_tokens": getattr(
            getattr(usage, "completion_tokens_details", None),
            "reasoning_tokens",
            0,
        ) or 0,
    }
    return response.choices[0].message.content, latency_s, token_usage
