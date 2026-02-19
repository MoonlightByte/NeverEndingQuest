"""Tests for capture_and_fanout wrapper."""
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def _make_mock_response(content="mock response"):
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = content
    return mock


def test_returns_primary_response_when_capture_disabled():
    """With capture disabled, returns primary call result transparently."""
    mock_create = MagicMock(return_value=_make_mock_response("primary"))

    with patch("model_config.MULTI_MODEL_CAPTURE", False):
        # Re-import to pick up the patched value
        import importlib
        import utils.capture.multi_model_capture as m
        importlib.reload(m)
        result = m.capture_and_fanout(
            "T013", mock_create,
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4.1-2025-04-14",
        )

    assert result.choices[0].message.content == "primary"
    mock_create.assert_called_once()


def test_passes_original_kwargs_to_primary():
    """All original kwargs reach the primary call unchanged."""
    mock_create = MagicMock(return_value=_make_mock_response())

    with patch("model_config.MULTI_MODEL_CAPTURE", False):
        import importlib
        import utils.capture.multi_model_capture as m
        importlib.reload(m)
        m.capture_and_fanout(
            "T013", mock_create,
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4.1-2025-04-14",
            temperature=0.7,
            reasoning_effort="none",
        )

    _, kwargs = mock_create.call_args
    assert kwargs["temperature"] == 0.7
    assert kwargs["reasoning_effort"] == "none"
    assert kwargs["model"] == "gpt-4.1-2025-04-14"


def test_determines_tier_full():
    """Full model config variables map to 'full' tier."""
    import utils.capture.multi_model_capture as m
    import model_config as mc
    assert m._determine_tier(mc.DM_MAIN_MODEL) == "full"


def test_determines_tier_mini():
    """Mini model config variables map to 'mini' tier."""
    import utils.capture.multi_model_capture as m
    import model_config as mc
    assert m._determine_tier(mc.DM_MINI_MODEL) == "mini"
