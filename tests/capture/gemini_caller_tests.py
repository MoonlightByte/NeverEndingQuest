"""Tests for Gemini message format conversion."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.capture.gemini_caller import convert_messages_to_gemini, build_gemini_config


def test_system_message_extracted():
    """System message becomes system_instruction, not part of contents."""
    messages = [
        {"role": "system", "content": "You are a dungeon master."},
        {"role": "user", "content": "What do I see?"}
    ]
    system_instruction, contents = convert_messages_to_gemini(messages)

    assert system_instruction == "You are a dungeon master."
    assert len(contents) == 1
    assert contents[0]["role"] == "user"
    assert "What do I see?" in str(contents[0]["parts"])


def test_no_system_message():
    """Messages without a system role: system_instruction is None."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello back"}
    ]
    system_instruction, contents = convert_messages_to_gemini(messages)

    assert system_instruction is None
    assert len(contents) == 2


def test_assistant_role_mapped_to_model():
    """OpenAI 'assistant' role maps to Gemini 'model' role."""
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"}
    ]
    _, contents = convert_messages_to_gemini(messages)

    roles = [c["role"] for c in contents]
    assert "model" in roles
    assert "assistant" not in roles


def test_build_config_low_thinking_with_temp():
    """Low thinking with temperature included."""
    variant = {
        "model": "gemini-3-pro-preview",
        "thinking_level": "low",
        "use_caller_temp": True,
        "label": "gemini-3-pro|thinking=low"
    }
    config = build_gemini_config(variant, caller_temperature=0.7, use_json=False)

    assert config["thinking_level"] == "low"
    assert config.get("temperature") == 0.7


def test_build_config_high_thinking_no_temp():
    """High thinking: temperature omitted (use_caller_temp=False)."""
    variant = {
        "model": "gemini-3-pro-preview",
        "thinking_level": "high",
        "use_caller_temp": False,
        "label": "gemini-3-pro|thinking=high"
    }
    config = build_gemini_config(variant, caller_temperature=0.7, use_json=False)

    assert config["thinking_level"] == "high"
    assert "temperature" not in config


def test_build_config_json_output():
    """JSON response_mime_type set when use_json=True."""
    variant = {
        "model": "gemini-3-flash-preview",
        "thinking_level": "low",
        "use_caller_temp": False,
        "label": "gemini-3-flash|thinking=low"
    }
    config = build_gemini_config(variant, caller_temperature=None, use_json=True)

    assert config.get("response_mime_type") == "application/json"
