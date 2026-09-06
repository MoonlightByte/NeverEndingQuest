# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Stream shims that stand in for sys.stdin/sys.stdout in headless mode.

These deliberately mirror web mode's WebInput/WebOutputCapture contracts:

- HeadlessInput implements only readline() and has NO isatty attribute.
  main.py:5099 breaks the game loop when `hasattr(sys.stdin, 'isatty') and
  not sys.stdin.isatty()`; like WebInput, lacking the attribute skips the
  guard. Do not add isatty here.
- HeadlessOutputCapture exposes `original_stream` because
  main.emit_startup_marker() duck-types on that attribute to decide whether
  to print STARTUP_MARKER lines to the live stdout (the classifier's
  readiness signal). Here it points at the raw mirror log, never at the
  protocol stream.
"""

import queue as queue_module
import threading

from core.headless.classifier import LineClassifier

# Sentinel put on the input queue to signal end-of-input. readline() then
# returns '' so the engine's input() raises EOFError and unwinds cleanly.
EOF_SENTINEL = object()


class HeadlessOutputCapture:
    """Line-buffering stdout/stderr replacement feeding a LineClassifier."""

    def __init__(self, emit, mirror_stream, is_error=False):
        # Duck-typed by main.emit_startup_marker(); must exist, must not be
        # the protocol stream (marker lines are re-printed through write()).
        self.original_stream = mirror_stream
        self.classifier = LineClassifier(emit, is_error=is_error)
        self.buffer = ""
        # The engine writes from several threads (game loop, character
        # update pool, logger); an unlocked read-modify-write on the buffer
        # loses data under contention.
        self._lock = threading.RLock()

    def write(self, text):
        try:
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            elif not isinstance(text, str):
                text = str(text)
        except Exception:
            return
        with self._lock:
            try:
                self.original_stream.write(text)
            except Exception:
                pass
            self.buffer += text
            if "\n" in self.buffer:
                lines = self.buffer.split("\n")
                for line in lines[:-1]:
                    try:
                        self.classifier.feed_line(line)
                    except Exception:
                        pass
                self.buffer = lines[-1]

    def flush(self):
        with self._lock:
            try:
                self.classifier.flush()
            except Exception:
                pass
            try:
                self.original_stream.flush()
            except Exception:
                pass

    def consume_pending(self):
        """Return and clear the unterminated tail of the buffer.

        input(prompt) writes the prompt with no trailing newline right
        before calling readline() on stdin; consuming it here both exposes
        the prompt text to the session and keeps it from being glued onto
        the next classified line.
        """
        with self._lock:
            pending = self.buffer
            self.buffer = ""
            return pending


class HeadlessInput:
    """stdin replacement; readline() blocks on a queue like web mode's.

    on_prompt is called exactly once per readline() BEFORE blocking -- it is
    the session's hook to emit the `prompt` + `state` protocol events. NO
    isatty attribute, by design (see module docstring).
    """

    def __init__(self, input_queue, on_prompt=None, is_quitting=None):
        self.queue = input_queue
        self.on_prompt = on_prompt
        self.is_quitting = is_quitting

    def _quit_requested(self):
        try:
            return self.is_quitting is not None and self.is_quitting()
        except Exception:
            return False

    def readline(self):
        from utils.capture.live_provider_call import service_live_input_boundary

        service_live_input_boundary()
        # Once quit is requested, EVERY readline returns EOF, not just the
        # one that consumes the sentinel: the combat and level-up sub-loops
        # swallow a single EOFError and drop back to the main loop, which
        # would otherwise block forever on a fresh prompt.
        if self._quit_requested():
            return ""
        try:
            from core.managers.status_manager import status_ready
            # Game thread parking for input = authoritative open-input
            # boundary, even mid-scope (combat sub-loop turns).
            status_ready(at_input_boundary=True)
        except Exception:
            pass
        if self.on_prompt is not None:
            try:
                self.on_prompt()
            except Exception:
                pass
        while True:
            drained = service_live_input_boundary()
            if self._quit_requested():
                return ""
            if drained:
                # This game thread is still parked, not processing a new input.
                # A queued Save may have published a busy wait/terminal status.
                try:
                    from core.managers.status_manager import status_ready
                    status_ready(at_input_boundary=True)
                except Exception:
                    pass
            try:
                user_input = self.queue.get(timeout=0.5)
            except queue_module.Empty:
                # #214: the game thread parks here between turns; this pump
                # services the off-thread startup-welcome lifecycle (lease
                # renewal, handback apply/discard) without fake player input.
                try:
                    from core.managers.status_manager import run_input_poll_hook
                    run_input_poll_hook()
                except Exception:
                    pass
                continue
            except Exception:
                return ""
            service_live_input_boundary()
            if user_input is EOF_SENTINEL:
                return ""
            if isinstance(user_input, str):
                return user_input + "\n"
            return str(user_input) + "\n"
