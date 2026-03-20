"""Synthetic integration test for api_client.create_completion().

Phase 0 gate: this test MUST pass before any callsite migration.
Tests the wrapper's routing, param translation, and JSON mode
WITHOUT making real API calls -- uses monkeypatching to intercept calls
and verify the parameters the wrapper would send to each provider.
"""
import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import model_config
from core.ai.api_client import create_completion


class TestCreateCompletionLegacy(unittest.TestCase):
    """Test wrapper behavior with legacy provider (GPT-4.1)."""

    def setUp(self):
        self.original_provider = model_config.MODEL_PROVIDER

    def tearDown(self):
        model_config.MODEL_PROVIDER = self.original_provider

    @patch("core.ai.api_client.get_openai_client")
    def test_legacy_passes_temperature(self, mock_get_client):
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            temperature=0.8,
        )

        call_kwargs = mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs.get("temperature") or call_kwargs[1].get("temperature"), 0.8)

    @patch("core.ai.api_client.get_openai_client")
    def test_legacy_injects_json_mode(self, mock_get_client):
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
        )

        call_args = mock_client.chat.completions.create.call_args
        # response_format should be injected
        rf = call_args.kwargs.get("response_format") or call_args[1].get("response_format")
        self.assertEqual(rf, {"type": "json_object"})

    @patch("core.ai.api_client.get_openai_client")
    def test_legacy_strips_top_p(self, mock_get_client):
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            top_p=1,
        )

        call_args = mock_client.chat.completions.create.call_args
        self.assertNotIn("top_p", call_args.kwargs)
        if len(call_args) > 1:
            self.assertNotIn("top_p", call_args[1])

    @patch("core.ai.api_client.get_openai_client")
    def test_legacy_forwards_response_format_from_callsite(self, mock_get_client):
        """Callsite-passed response_format is forwarded to the API call."""
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            response_format={"type": "json_object"},
        )

        call_args = mock_client.chat.completions.create.call_args
        # Callsite-passed response_format should be forwarded to the API call
        rf = call_args.kwargs.get("response_format") or call_args[1].get("response_format")
        self.assertEqual(rf, {"type": "json_object"})

    @patch("core.ai.api_client.get_openai_client")
    def test_legacy_no_escalation_applied(self, mock_get_client):
        """Legacy provider: retry_attempt has no effect (no escalation ladder)."""
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            temperature=0.8,
            retry_attempt=3,
        )

        call_args = mock_client.chat.completions.create.call_args
        # Should NOT have reasoning_effort or thinking_level
        self.assertNotIn("reasoning_effort", call_args.kwargs)
        self.assertNotIn("thinking_level", call_args.kwargs)
        # retry_attempt should NOT be forwarded
        self.assertNotIn("retry_attempt", call_args.kwargs)


class TestCreateCompletionOpenAI(unittest.TestCase):
    """Test wrapper behavior with OpenAI GPT-5.x provider."""

    def setUp(self):
        self.original_provider = model_config.MODEL_PROVIDER

    def tearDown(self):
        model_config.MODEL_PROVIDER = self.original_provider

    @patch("core.ai.api_client.get_openai_client")
    def test_openai_reasoning_none_passes_temp(self, mock_get_client):
        """Callsite passes reasoning_effort=none explicitly, temperature should pass through."""
        model_config.MODEL_PROVIDER = "openai"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-5.2",
            temperature=0.8,
            reasoning_effort="none",
        )

        call_args = mock_client.chat.completions.create.call_args
        # Callsite-passed reasoning_effort=none should forward and allow temperature
        self.assertEqual(call_args.kwargs.get("reasoning_effort"), "none")
        self.assertEqual(call_args.kwargs.get("temperature"), 0.8)

    @patch("core.ai.api_client.get_openai_client")
    def test_openai_reasoning_low_strips_temp(self, mock_get_client):
        """Callsite passes reasoning_effort=low, temperature must be stripped."""
        model_config.MODEL_PROVIDER = "openai"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-5.2",
            temperature=0.8,
            reasoning_effort="low",
        )

        call_args = mock_client.chat.completions.create.call_args
        # reasoning > none: temperature MUST be stripped
        self.assertEqual(call_args.kwargs.get("reasoning_effort"), "low")
        self.assertNotIn("temperature", call_args.kwargs)

    @patch("core.ai.api_client.get_openai_client")
    def test_openai_5mini_never_has_temp(self, mock_get_client):
        """GPT-5-mini: temperature always stripped regardless of reasoning_effort."""
        model_config.MODEL_PROVIDER = "openai"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-5-mini",
            temperature=0.8,
            reasoning_effort="low",
        )

        call_args = mock_client.chat.completions.create.call_args
        # GPT-5-mini: temperature NEVER passes through
        self.assertNotIn("temperature", call_args.kwargs)
        # Callsite-passed reasoning_effort should be forwarded
        self.assertEqual(call_args.kwargs.get("reasoning_effort"), "low")

    @patch("core.ai.api_client.get_openai_client")
    def test_task_id_not_forwarded(self, mock_get_client):
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            task_id="T999",
        )

        call_args = mock_client.chat.completions.create.call_args
        self.assertNotIn("task_id", call_args.kwargs)

    @patch("core.ai.api_client.get_openai_client")
    def test_retry_attempt_not_forwarded(self, mock_get_client):
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            retry_attempt=2,
        )

        call_args = mock_client.chat.completions.create.call_args
        self.assertNotIn("retry_attempt", call_args.kwargs)

    @patch("core.ai.api_client.get_openai_client")
    def test_max_tokens_passes_through_openai(self, mock_get_client):
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            max_tokens=20,
        )

        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs.get("max_tokens"), 20)


class TestResponseFormat(unittest.TestCase):
    """Verify response_format default and opt-out behavior."""

    def setUp(self):
        self.original_provider = model_config.MODEL_PROVIDER

    def tearDown(self):
        model_config.MODEL_PROVIDER = self.original_provider

    @patch("core.ai.api_client.get_openai_client")
    def test_json_mode_default_when_not_passed(self, mock_get_client):
        """No response_format arg -> JSON mode injected (85+ callsites depend on this)."""
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            temperature=0.7,
        )

        call_args = mock_client.chat.completions.create.call_args
        rf = call_args.kwargs.get("response_format")
        self.assertEqual(rf, {"type": "json_object"})

    @patch("core.ai.api_client.get_openai_client")
    def test_json_mode_suppressed_when_none(self, mock_get_client):
        """response_format=None -> NO JSON mode (plain-text callsites use this)."""
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'plain text narrative'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            temperature=0.7,
            response_format=None,
        )

        call_args = mock_client.chat.completions.create.call_args
        self.assertNotIn("response_format", call_args.kwargs)

    @patch("core.ai.api_client.get_openai_client")
    def test_explicit_response_format_passed_through(self, mock_get_client):
        """Explicit response_format value -> forwarded as-is."""
        model_config.MODEL_PROVIDER = "legacy"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4.1-2025-04-14",
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        call_args = mock_client.chat.completions.create.call_args
        rf = call_args.kwargs.get("response_format")
        self.assertEqual(rf, {"type": "json_object"})

    @patch("core.ai.api_client._gemini_completion")
    def test_gemini_json_mode_default(self, mock_gemini):
        """Gemini path: no response_format -> JSON mode (default)."""
        model_config.MODEL_PROVIDER = "gemini"
        mock_gemini.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"test": true}'))],
            usage=MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gemini-3.1-pro-preview",
            temperature=0.7,
        )

        # _gemini_completion should be called with response_format=_UNSET
        call_args = mock_gemini.call_args
        from core.ai.api_client import _UNSET
        self.assertIs(call_args.kwargs.get("response_format"), _UNSET)

    @patch("core.ai.api_client._gemini_completion")
    def test_gemini_json_mode_suppressed_when_none(self, mock_gemini):
        """Gemini path: response_format=None -> no JSON mode."""
        model_config.MODEL_PROVIDER = "gemini"
        mock_gemini.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='plain text'))],
            usage=MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gemini-3.1-pro-preview",
            temperature=0.7,
            response_format=None,
        )

        call_args = mock_gemini.call_args
        self.assertIsNone(call_args.kwargs.get("response_format"))


if __name__ == "__main__":
    unittest.main()
