# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Transport-neutral stdout line classifier for headless mode.

This is an extraction of the classification logic inside
web/web_interface.py's WebOutputCapture.write() (the ~220-line heuristic
that recovers DM narration, STARTUP_MARKER lines, prompt lines, and debug
noise from the engine's mixed stdout stream). The web module is not
modified; headless uses this standalone copy so it carries no Flask or
Socket.IO dependencies. Since narration is sink-routed (P2), this class
is only a FALLBACK for print sites the sink does not cover.

Three deliberate divergences from WebOutputCapture.write():
1. A prompt banner seen inside an open DM section flushes the section
   (web leaves it open and later merges across the prompt).
2. An unparseable STARTUP_MARKER line is emitted as debug (web drops it).
3. A noise marker inside a DM section flushes the narration BEFORE the
   debug line (web queues the debug line first) -- ordering on the debug
   stream differs, narration content does not.

Events are delivered as emit(kind, **fields) callbacks with kinds:
  startup   - parsed STARTUP_MARKER payload (fields: the marker dict)
  narration - one complete DM narration block (fields: content)
  debug     - everything else (fields: content, is_error)
"""

import json
import re

_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Hardcoded noise denylist, copied verbatim from WebOutputCapture.write()
# (web/web_interface.py). Lines containing any of these are debug, never
# narration, even inside a "Dungeon Master:" section.
NOISE_MARKERS = [
    "Lightweight chat history updated",
    "System messages removed:",
    "User messages:",
    "Assistant messages:",
    "not found. Skipping",
    "not found. Returning None",
    "has an invalid JSON format",
    "Current Time:",
    "Time Advanced:",
    "New Time:",
    "Days Passed:",
    "Loading module areas",
    "Graph built:",
    "[OK] Loaded",
]

_SECTION_END_MARKERS = ["DEBUG:", "ERROR:", "WARNING:"]


def strip_ansi(text):
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


def looks_like_prompt(clean_line):
    """True for the engine's player-prompt banner lines."""
    return clean_line.startswith("[") and (
        "HP:" in clean_line or "XP:" in clean_line)


class LineClassifier:
    """Stateful classifier over complete stdout lines.

    emit is a callable(kind, **fields); it must never raise into the
    engine's output path (failures are swallowed).
    """

    def __init__(self, emit, is_error=False):
        self._emit = emit
        self._is_error = is_error
        self._in_dm_section = False
        self._dm_buffer = []

    # -- internal helpers -------------------------------------------------

    def _safe_emit(self, kind, **fields):
        try:
            self._emit(kind, **fields)
        except Exception:
            pass

    def _debug(self, content, is_error=None):
        if is_error is None:
            is_error = self._is_error or "ERROR:" in content
        self._safe_emit("debug", content=content, is_error=is_error)

    def _flush_dm_buffer(self):
        if not self._dm_buffer:
            self._in_dm_section = False
            return
        combined = "\n".join(self._dm_buffer)
        combined = combined.replace("Dungeon Master:", "", 1).strip()
        if combined:
            self._safe_emit("narration", content=combined)
        self._in_dm_section = False
        self._dm_buffer = []

    # -- public API --------------------------------------------------------

    def feed_line(self, line):
        """Classify one complete line (newline already stripped)."""
        clean_line = strip_ansi(line)

        # Startup marker stream: structured readiness signal.
        if "STARTUP_MARKER:" in clean_line:
            try:
                marker_payload = clean_line.split("STARTUP_MARKER:", 1)[1].strip()
                marker_data = json.loads(marker_payload)
                if isinstance(marker_data, dict):
                    self._safe_emit("startup", **marker_data)
                    return
            except (ValueError, TypeError):
                pass
            self._debug(clean_line)
            return

        if looks_like_prompt(clean_line):
            # Player prompt banner: end any open DM section, route to debug.
            self._flush_dm_buffer()
            self._debug(clean_line)
            return

        if "Dungeon Master:" in clean_line:
            self._in_dm_section = True
            self._dm_buffer = [clean_line]
            return

        if self._in_dm_section:
            if line.strip() == "":
                self._dm_buffer.append("")
                return
            if (any(marker in clean_line for marker in _SECTION_END_MARKERS)
                    or clean_line.startswith(">")):
                self._flush_dm_buffer()
                self._debug(clean_line)
                return
            if any(marker in clean_line for marker in NOISE_MARKERS):
                self._flush_dm_buffer()
                self._debug(clean_line)
                return
            self._dm_buffer.append(clean_line)
            return

        if any(marker in clean_line for marker in NOISE_MARKERS):
            self._debug(clean_line)
            return
        if line.strip():
            self._debug(clean_line)

    def flush(self):
        """Emit any buffered DM narration (mirrors WebOutputCapture.flush)."""
        self._flush_dm_buffer()
