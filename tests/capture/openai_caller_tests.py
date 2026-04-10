"""Tests for OpenAI variant caller parameter building."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.capture.openai_caller import build_openai_params


def test_baseline_with_temperature():
    """gpt-4.1 baseline: passes temperature, no reasoning_effort."""
    variant = {
        "provider": "openai",
        "model": "gpt-4.1-2025-04-14",
        "reasoning_effort": None,
        "use_caller_temp": True,
        "label": "gpt-4.1|baseline"
    }
    messages = [{"role": "user", "content": "hello"}]
    params = build_openai_params(variant, messages, caller_temperature=0.7)

    assert params["model"] == "gpt-4.1-2025-04-14"
    assert params["messages"] == messages
    assert params["temperature"] == 0.7
    assert "reasoning_effort" not in params
    assert "max_tokens" not in params
    assert "max_completion_tokens" not in params


def test_gpt52_effort_none_with_temperature():
    """gpt-5.2 effort=none: passes temperature alongside reasoning_effort."""
    variant = {
        "provider": "openai",
        "model": "gpt-5.2",
        "reasoning_effort": "none",
        "use_caller_temp": True,
        "label": "gpt-5.2|effort=none"
    }
    params = build_openai_params(variant, [], caller_temperature=0.8)

    assert params["model"] == "gpt-5.2"
    assert params["reasoning_effort"] == "none"
    assert params["temperature"] == 0.8
    assert "max_tokens" not in params


def test_gpt52_effort_low_no_temperature():
    """gpt-5.2 effort=low: omits temperature (incompatible with reasoning > none)."""
    variant = {
        "provider": "openai",
        "model": "gpt-5.2",
        "reasoning_effort": "low",
        "use_caller_temp": False,
        "label": "gpt-5.2|effort=low"
    }
    params = build_openai_params(variant, [], caller_temperature=0.7)

    assert params["reasoning_effort"] == "low"
    assert "temperature" not in params
    assert "max_tokens" not in params


def test_no_token_limits_ever():
    """Confirm max_tokens and max_completion_tokens are never present."""
    variant = {
        "provider": "openai",
        "model": "gpt-5-mini",
        "reasoning_effort": None,
        "use_caller_temp": False,
        "label": "gpt-5-mini"
    }
    params = build_openai_params(variant, [], caller_temperature=None)

    assert "max_tokens" not in params
    assert "max_completion_tokens" not in params


def test_caller_temp_none_skips_temperature():
    """If caller did not pass temperature, it is not included even with use_caller_temp."""
    variant = {
        "provider": "openai",
        "model": "gpt-4.1-2025-04-14",
        "reasoning_effort": None,
        "use_caller_temp": True,
        "label": "gpt-4.1|baseline"
    }
    params = build_openai_params(variant, [], caller_temperature=None)

    assert "temperature" not in params
