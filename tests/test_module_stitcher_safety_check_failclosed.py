"""
Tests for INT-M4: _ai_validate_content_safety must fail CLOSED on parse
errors or AI API exceptions.

`core/generators/module_stitcher.py` `_ai_validate_content_safety` currently
defaults to returning True (safe) when:
  1. The AI response cannot be parsed as JSON.
  2. The AI API call itself raises any exception.

This means a community-module submitter who triggers either failure mode
(by submitting content that confuses the AI, or by tripping a transient
API error) gets a free pass through content safety validation.

The fix: both failure paths must return False (UNSAFE) so malformed or
unparseable validations are rejected, not silently approved.

NOTE on contract: the existing function returns a single `bool`
(not a `(safe, reason)` tuple as one variant of the plan suggested).
These tests match the actual `-> bool` contract; the failure-mode
change is what matters.
"""

import logging
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import module_stitcher as module_stitcher_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _StubStitcher:
    """Minimal stand-in for ModuleStitcher.

    `_ai_validate_content_safety` only needs `self` for method dispatch --
    it does not read any instance attributes. We bind the real method to a
    bare object so we don't have to construct a full ModuleStitcher
    (which builds an OpenAI client, loads the world registry, etc.).
    """

    _ai_validate_content_safety = (
        module_stitcher_module.ModuleStitcher._ai_validate_content_safety
    )


def _make_ai_response(content: str):
    """Build a fake OpenAI-style response object whose
    .choices[0].message.content == `content`."""
    msg = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=msg)
    return types.SimpleNamespace(choices=[choice])


_SAMPLE_MODULE = {
    "plotObjective": "Recover the lost amulet",
    "themes": ["fantasy", "adventure"],
    "areas": {
        "AA001": {
            "areaDescription": "A quiet glade dotted with wildflowers."
        }
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_safety_check_returns_false_on_invalid_json():
    """Test 1: AI returns malformed JSON.

    The function MUST return False (fail closed). Pre-fix it returns True
    (defaults to safe), which is the bug being fixed.
    """
    stitcher = _StubStitcher()

    fake_response = _make_ai_response("this is not valid json {")

    with patch.object(
        module_stitcher_module,
        "capture_and_fanout",
        return_value=fake_response,
    ):
        result = stitcher._ai_validate_content_safety(_SAMPLE_MODULE)

    assert result is False, (
        "Safety check MUST fail closed when AI response is not valid JSON; "
        f"got {result!r}"
    )


def test_safety_check_returns_false_on_api_exception():
    """Test 2: AI API call itself raises.

    The function MUST return False (fail closed). Pre-fix it returns True
    (defaults to safe), which is the bug being fixed.
    """
    stitcher = _StubStitcher()

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated API failure")

    with patch.object(
        module_stitcher_module,
        "capture_and_fanout",
        side_effect=_boom,
    ):
        result = stitcher._ai_validate_content_safety(_SAMPLE_MODULE)

    assert result is False, (
        "Safety check MUST fail closed when the AI API call raises; "
        f"got {result!r}"
    )


def test_safety_check_returns_true_on_valid_safe_response():
    """Test 3 (regression): valid JSON saying safe=true.

    Happy path must still return True so this fix doesn't break legitimate
    module imports.
    """
    stitcher = _StubStitcher()

    fake_response = _make_ai_response(
        '{"safe": true, "reason": "Content is appropriate"}'
    )

    with patch.object(
        module_stitcher_module,
        "capture_and_fanout",
        return_value=fake_response,
    ):
        result = stitcher._ai_validate_content_safety(_SAMPLE_MODULE)

    assert result is True, (
        "Safety check MUST return True for a well-formed safe response; "
        f"got {result!r}"
    )


def test_safety_check_returns_false_on_valid_unsafe_response():
    """Regression: valid JSON saying safe=false must still return False.

    Guards against accidentally inverting the success path while fixing
    the failure path.
    """
    stitcher = _StubStitcher()

    fake_response = _make_ai_response(
        '{"safe": false, "reason": "Contains disallowed material"}'
    )

    with patch.object(
        module_stitcher_module,
        "capture_and_fanout",
        return_value=fake_response,
    ):
        result = stitcher._ai_validate_content_safety(_SAMPLE_MODULE)

    assert result is False
