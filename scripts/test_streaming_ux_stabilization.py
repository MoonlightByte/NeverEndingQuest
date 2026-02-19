#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Streaming UX stabilization regression checks.

Validates:
- narration-safe extraction from partial JSON drafts
- single canonical suppression behavior after stream commit
- superseded attempts cannot register canonical suppression
"""

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import model_config
from web.extensions import streaming_events


class StreamingUXStabilizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_streaming = getattr(model_config, "ENABLE_CHAT_STREAMING", False)
        model_config.ENABLE_CHAT_STREAMING = True
        streaming_events.configure_stream_transport(lambda _event, _payload: None)

        with streaming_events._state_lock:
            streaming_events._streams.clear()
            streaming_events._pending_canonical_suppressions.clear()

    def tearDown(self) -> None:
        model_config.ENABLE_CHAT_STREAMING = self._prev_streaming
        with streaming_events._state_lock:
            streaming_events._streams.clear()
            streaming_events._pending_canonical_suppressions.clear()

    def test_extract_narration_filters_json_wrappers(self) -> None:
        partial = '{"narration":"A goblin lunges at you'  # no closing quote yet
        extracted = streaming_events.extract_narration_for_stream(partial)
        self.assertEqual(extracted, "A goblin lunges at you")
        self.assertNotIn("{", extracted)
        self.assertNotIn('"narration"', extracted)

    def test_extract_narration_decodes_escapes(self) -> None:
        raw = '{"narration":"Line 1\\nLine 2\\\"quoted\\\"."}'
        extracted = streaming_events.extract_narration_for_stream(raw)
        self.assertEqual(extracted, 'Line 1\nLine 2"quoted".')

    def test_commit_registers_single_suppression(self) -> None:
        stream_id = streaming_events.start_stream("turn_a", "narrative", 1, False)
        self.assertIsNotNone(stream_id)
        streaming_events.commit_stream(stream_id, "The torchlight flickers in the hall.")

        self.assertTrue(
            streaming_events.should_suppress_canonical_narration(
                "Dungeon Master: The torchlight flickers in the hall."
            )
        )
        self.assertFalse(
            streaming_events.should_suppress_canonical_narration(
                "Dungeon Master: The torchlight flickers in the hall."
            )
        )

    def test_superseded_attempt_does_not_register_canonical(self) -> None:
        stream_id = streaming_events.start_stream("turn_b", "narrative", 2, False)
        self.assertIsNotNone(stream_id)
        streaming_events.supersede_stream(stream_id, reason="validation_retry")
        streaming_events.commit_stream(stream_id, "This should never become canonical.")

        self.assertFalse(
            streaming_events.should_suppress_canonical_narration(
                "Dungeon Master: This should never become canonical."
            )
        )

    def test_startup_branch_uses_unified_policy_marker(self) -> None:
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            "Get initial AI response using unified startup streaming policy for both branches.",
            main_source,
        )

    def test_tts_queue_has_bounded_stream_pending_logic(self) -> None:
        tts_source = (ROOT / "web/static/js/tts_queue_manager.js").read_text(encoding="utf-8")
        self.assertIn("maxPending", tts_source)
        self.assertIn("cancelBySourceTag", tts_source)


if __name__ == "__main__":
    unittest.main()
