# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Headless CLI mode for agentic automation and testing.

This package lets an external agent (a test harness, a shell script, or an
AI coding agent) drive the full game engine without the HTML interface. It
mirrors the proven web-mode pattern: swap sys.stdin/sys.stdout around an
unmodified main_game_loop(), but speak newline-delimited JSON on the real
stdio instead of Socket.IO.

Protocol spec: docs/HEADLESS_MODE.md
Design plan:   docs/plans/2026-08-06-headless-cli-mode-plan.md

Import order matters: HeadlessSession installs the stream shims BEFORE
importing main, so enhanced_logger's StreamHandler (which binds sys.stdout
at import time) also flows through the classifier.
"""
