"""Integration test for game_started SocketIO emission."""

import pytest
from unittest.mock import MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGameStartedEmission:
    """Test that game_started event fires exactly once via a single code path."""

    def setup_method(self):
        """Save original state before each test."""
        from web import web_interface
        self.web_interface = web_interface
        self.original_socketio = web_interface.socketio
        self.original_startup_handoff_active = web_interface.startup_handoff_active
        self.original_startup_ready_emitted = web_interface.startup_ready_emitted

    def teardown_method(self):
        """Restore original state after each test."""
        self.web_interface.socketio = self.original_socketio
        self.web_interface.startup_handoff_active = self.original_startup_handoff_active
        self.web_interface.startup_ready_emitted = self.original_startup_ready_emitted

    def test_game_started_emits_on_kickoff_done_marker(self):
        """game_started should emit when startup_kickoff_done marker is detected."""
        from web.web_interface import WebOutputCapture, debug_output_queue
        from web import web_interface as wi

        # Reset global state
        wi.startup_handoff_active = True
        wi.startup_ready_emitted = False

        # Mock socketio
        mock_socketio = MagicMock()
        wi.socketio = mock_socketio

        # Create capture instance
        original_stdout = MagicMock()
        capture = WebOutputCapture(debug_output_queue, original_stdout)

        # Send the kickoff_done marker
        marker_line = 'STARTUP_MARKER:{"phase":"startup_kickoff_done","source":"test"}\n'
        capture.write(marker_line)

        # Verify game_started was emitted exactly once
        game_started_calls = [
            call for call in mock_socketio.emit.call_args_list
            if call[0][0] == 'game_started'
        ]
        assert len(game_started_calls) == 1, f"Expected 1 game_started, got {len(game_started_calls)}"
        assert wi.startup_ready_emitted is True

    def test_game_started_does_not_double_emit(self):
        """game_started should not emit twice if marker arrives twice."""
        from web.web_interface import WebOutputCapture, debug_output_queue
        from web import web_interface as wi

        wi.startup_handoff_active = True
        wi.startup_ready_emitted = False

        mock_socketio = MagicMock()
        wi.socketio = mock_socketio

        original_stdout = MagicMock()
        capture = WebOutputCapture(debug_output_queue, original_stdout)

        # Send marker twice
        marker_line = 'STARTUP_MARKER:{"phase":"startup_kickoff_done"}\n'
        capture.write(marker_line)
        capture.write(marker_line)

        # Should still only emit once
        game_started_calls = [
            call for call in mock_socketio.emit.call_args_list
            if call[0][0] == 'game_started'
        ]
        assert len(game_started_calls) == 1

    def test_fallback_emission_only_if_primary_missed(self):
        """Fallback (prompt detection) should only fire if primary path didn't."""
        from web.web_interface import WebOutputCapture, debug_output_queue
        from web import web_interface as wi

        # Primary already fired - fallback should NOT emit
        wi.startup_ready_emitted = True
        wi.startup_handoff_active = False

        mock_socketio = MagicMock()
        wi.socketio = mock_socketio

        original_stdout = MagicMock()
        capture = WebOutputCapture(debug_output_queue, original_stdout)

        # Send player prompt (would trigger fallback)
        prompt_line = '[Adventurer | HP: 10/10 | XP: 0]\n'
        capture.write(prompt_line)

        # Should NOT emit game_started (already emitted)
        game_started_calls = [
            call for call in mock_socketio.emit.call_args_list
            if call[0][0] == 'game_started'
        ]
        assert len(game_started_calls) == 0

    def test_fallback_fires_when_primary_missed(self):
        """Fallback should emit if primary marker path never fired."""
        from web.web_interface import WebOutputCapture, debug_output_queue
        from web import web_interface as wi

        # Primary never fired
        wi.startup_ready_emitted = False
        wi.startup_handoff_active = False

        mock_socketio = MagicMock()
        wi.socketio = mock_socketio

        original_stdout = MagicMock()
        capture = WebOutputCapture(debug_output_queue, original_stdout)

        # Send player prompt (triggers fallback)
        prompt_line = '[Adventurer | HP: 10/10 | XP: 0]\n'
        capture.write(prompt_line)

        # Should emit game_started as fallback
        game_started_calls = [
            call for call in mock_socketio.emit.call_args_list
            if call[0][0] == 'game_started'
        ]
        assert len(game_started_calls) == 1
        assert wi.startup_ready_emitted is True
