# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression checks for Start Game duplicate-click protection."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB_INTERFACE = ROOT / "web" / "web_interface.py"
GAME_INTERFACE = ROOT / "web" / "templates" / "game_interface.html"


class TestStartGameReentryGuard(unittest.TestCase):
    def setUp(self):
        self.web_source = WEB_INTERFACE.read_text(encoding="utf-8")
        self.html_source = GAME_INTERFACE.read_text(encoding="utf-8")

    def test_backend_reentry_guard_exists(self):
        self.assertIn("startup_in_progress = False", self.web_source)
        self.assertIn("startup_guard_lock = threading.Lock()", self.web_source)
        self.assertIn(
            "if startup_in_progress or (game_thread and game_thread.is_alive()):",
            self.web_source,
        )
        self.assertIn("Game is already starting or running", self.web_source)
        self.assertIn("'game_starting': is_starting", self.web_source)

    def test_backend_flag_lifecycle_exists(self):
        self.assertIn("startup_in_progress = True", self.web_source)
        self.assertIn("with startup_guard_lock:", self.web_source)
        self.assertIn("finally:\n        with startup_guard_lock:\n            startup_in_progress = False", self.web_source)
        self.assertIn("game_thread = None", self.web_source)

    def test_frontend_pending_state_exists(self):
        self.assertIn("let startupPending = false;", self.html_source)
        self.assertIn("function syncStartButtonState()", self.html_source)
        self.assertIn("startButton.textContent = 'Starting...'", self.html_source)

    def test_frontend_blocks_repeat_clicks(self):
        self.assertIn(
            "if (connected && !gameStarted && !startupPending) {",
            self.html_source,
        )
        self.assertIn("startupPending = true;", self.html_source)
        self.assertIn("socket.emit('start_game');", self.html_source)

    def test_frontend_recovers_from_error(self):
        self.assertIn("if (startupPending && !gameStarted)", self.html_source)
        self.assertIn("startupPending = false;", self.html_source)
        self.assertIn("syncStartButtonState();", self.html_source)
        self.assertIn("startupPending = !!data.game_starting && !gameStarted;", self.html_source)


if __name__ == "__main__":
    unittest.main()
