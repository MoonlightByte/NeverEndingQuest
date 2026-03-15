"""Synthetic integration test for api_client.create_completion().

Phase 0 gate: this test MUST pass before any callsite migration.
Tests the wrapper's routing, escalation, param translation, and JSON mode
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
from core.ai.api_client import create_completion, _get_ladder_key, _ESCALATION_LADDERS


class TestEscalationLadders(unittest.TestCase):
    """Test ladder key selection and ladder contents."""

    def test_legacy_has_no_ladder(self):
        self.assertIsNone(_get_ladder_key("legacy", "gpt-4.1-2025-04-14"))

    def test_lmstudio_has_no_ladder(self):
        self.assertIsNone(_get_ladder_key("lmstudio", "local-model"))

    def test_openai_full_uses_5x_ladder(self):
        self.assertEqual(_get_ladder_key("openai", "gpt-5.2"), "openai_5x")

    def test_openai_mini_uses_5mini_ladder(self):
        self.assertEqual(_get_ladder_key("openai", "gpt-5-mini"), "openai_5mini")

    def test_openai_54_uses_54_ladder(self):
        self.assertEqual(_get_ladder_key("openai", "gpt-5.4"), "openai_54")

    def test_gemini_pro_uses_pro_ladder(self):
        self.assertEqual(_get_ladder_key("gemini", "gemini-3.1-pro-preview"), "gemini_pro")

    def test_gemini_flash_uses_flash_ladder(self):
        self.assertEqual(_get_ladder_key("gemini", "gemini-3.1-flash-lite-preview"), "gemini_flash")

    def test_all_ladders_have_5_steps(self):
        for key, ladder in _ESCALATION_LADDERS.items():
            self.assertEqual(len(ladder), 5, f"Ladder {key} should have 5 steps")

    def test_openai_5x_starts_with_none(self):
        self.assertEqual(_ESCALATION_LADDERS["openai_5x"][0]["reasoning_effort"], "none")

    def test_openai_5mini_starts_with_low(self):
        self.assertEqual(_ESCALATION_LADDERS["openai_5mini"][0]["reasoning_effort"], "low")

    def test_openai_54_ends_with_xhigh(self):
        self.assertEqual(_ESCALATION_LADDERS["openai_54"][4]["reasoning_effort"], "xhigh")

    def test_gemini_pro_starts_with_low(self):
        self.assertEqual(_ESCALATION_LADDERS["gemini_pro"][0]["thinking_level"], "low")

    def test_gemini_flash_starts_with_minimal(self):
        self.assertEqual(_ESCALATION_LADDERS["gemini_flash"][0]["thinking_level"], "minimal")


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
    def test_openai_attempt0_reasoning_none_with_temp(self, mock_get_client):
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
            retry_attempt=0,
        )

        call_args = mock_client.chat.completions.create.call_args
        # At attempt 0, reasoning=none, temperature should pass through
        self.assertEqual(call_args.kwargs.get("reasoning_effort"), "none")
        self.assertEqual(call_args.kwargs.get("temperature"), 0.8)

    @patch("core.ai.api_client.get_openai_client")
    def test_openai_attempt1_strips_temp(self, mock_get_client):
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
            retry_attempt=1,
        )

        call_args = mock_client.chat.completions.create.call_args
        # At attempt 1, reasoning=low, temperature MUST be stripped
        self.assertEqual(call_args.kwargs.get("reasoning_effort"), "low")
        self.assertNotIn("temperature", call_args.kwargs)

    @patch("core.ai.api_client.get_openai_client")
    def test_openai_5mini_never_has_temp(self, mock_get_client):
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
            retry_attempt=0,
        )

        call_args = mock_client.chat.completions.create.call_args
        # GPT-5-mini: temperature NEVER passes through
        self.assertNotIn("temperature", call_args.kwargs)
        # reasoning_effort should be "low" (5-mini starts at low)
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


class TestCallsiteOverrides(unittest.TestCase):
    """Test CALLSITE_OVERRIDES merge priority."""

    def setUp(self):
        self.original_provider = model_config.MODEL_PROVIDER
        self.original_overrides = model_config.CALLSITE_OVERRIDES.copy()

    def tearDown(self):
        model_config.MODEL_PROVIDER = self.original_provider
        model_config.CALLSITE_OVERRIDES.clear()
        model_config.CALLSITE_OVERRIDES.update(self.original_overrides)

    @patch("core.ai.api_client.get_openai_client")
    def test_override_applies(self, mock_get_client):
        model_config.MODEL_PROVIDER = "openai"
        model_config.CALLSITE_OVERRIDES["T999"] = {
            "openai": {"reasoning_effort": "medium"},
        }
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-5.2",
            task_id="T999",
            retry_attempt=0,
        )

        call_args = mock_client.chat.completions.create.call_args
        # Override should win over escalation ladder's "none" at attempt 0
        self.assertEqual(call_args.kwargs.get("reasoning_effort"), "medium")

    @patch("core.ai.api_client.get_openai_client")
    def test_explicit_kwarg_beats_override(self, mock_get_client):
        model_config.MODEL_PROVIDER = "openai"
        model_config.CALLSITE_OVERRIDES["T999"] = {
            "openai": {"reasoning_effort": "medium"},
        }
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        create_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-5.2",
            task_id="T999",
            reasoning_effort="high",  # explicit kwarg
        )

        call_args = mock_client.chat.completions.create.call_args
        # Explicit kwarg should beat override
        self.assertEqual(call_args.kwargs.get("reasoning_effort"), "high")


class TestRetryAttemptClamping(unittest.TestCase):
    """Test that retry_attempt values > 4 are clamped."""

    def setUp(self):
        self.original_provider = model_config.MODEL_PROVIDER

    def tearDown(self):
        model_config.MODEL_PROVIDER = self.original_provider

    @patch("core.ai.api_client.get_openai_client")
    def test_retry_clamped_to_4(self, mock_get_client):
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
            retry_attempt=10,  # should clamp to 4
        )

        call_args = mock_client.chat.completions.create.call_args
        # At max level (clamped to 4), should be "high" for 5.2
        self.assertEqual(call_args.kwargs.get("reasoning_effort"), "high")


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


if __name__ == "__main__":
    unittest.main()
