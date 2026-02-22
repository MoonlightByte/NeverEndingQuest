"""OpenAI variant caller for multi-model capture system.

Builds call parameters and executes a single OpenAI variant call.
Never sets max_tokens or max_completion_tokens.
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


def build_openai_params(variant, messages, caller_temperature=None):
    """Build the kwargs dict for client.chat.completions.create.

    Args:
        variant: dict from capture_config full_tier_variants or mini_tier_variants
        messages: the original messages list from the callsite
        caller_temperature: the temperature value the callsite passed, or None

    Returns:
        dict of kwargs - never includes max_tokens or max_completion_tokens
    """
    params = {
        "model": variant["model"],
        "messages": messages,
    }

    if variant.get("reasoning_effort") is not None:
        params["reasoning_effort"] = variant["reasoning_effort"]

    if variant.get("use_caller_temp") and caller_temperature is not None:
        params["temperature"] = caller_temperature

    # Never add max_tokens or max_completion_tokens - ever
    return params


def call_openai_variant(variant, messages, caller_temperature=None, caller_kwargs=None):
    """Execute one OpenAI variant call and return (content, latency_s, token_usage).

    Args:
        variant: variant config dict
        messages: original messages list
        caller_temperature: temperature the original callsite used, or None
        caller_kwargs: other kwargs from original call (response_format etc)

    Returns:
        tuple of (content_str, latency_seconds, token_usage_dict)
        token_usage_dict has keys: prompt_tokens, completion_tokens, total_tokens

    Raises:
        Exception: any API error - caller should catch
    """
    params = build_openai_params(variant, messages, caller_temperature)

    # Pass through response_format if original call used it
    if caller_kwargs and "response_format" in caller_kwargs:
        params["response_format"] = caller_kwargs["response_format"]

    client = _get_client()
    start = time.time()
    response = client.chat.completions.create(**params)
    latency_s = round(time.time() - start, 3)

    content = response.choices[0].message.content

    # Extract token usage from response
    usage = response.usage
    token_usage = {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }

    return content, latency_s, token_usage
