# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Python client for headless mode.

Wraps `run_headless.py serve` in a subprocess and exposes a turn-based API
for harnesses and agents:

    from core.headless.client import HeadlessClient

    with HeadlessClient(module="The_Thornwood_Watch",
                        character="pc.json",
                        game_dir="/tmp/neq-test") as game:
        opening = game.opening          # TurnResult for the startup kickoff
        turn = game.play("I look around the room")
        print(turn.narration)           # combined DM narration for the turn
        print(turn.state["player"])     # hp, xp, location, ...
        game.save("checkpoint")

Each play() blocks until the engine asks for the next input (the `prompt`
protocol event), which is the turn boundary. See docs/HEADLESS_MODE.md for
the underlying protocol.
"""

import json
import os
import queue
import subprocess
import sys
import threading

from core.headless.protocol import VALID_EVENT_TYPES


class HeadlessProtocolError(RuntimeError):
    """The serve process ended or misbehaved mid-conversation."""


class TurnResult:
    """Everything the engine emitted between an input and the next prompt."""

    def __init__(self, events):
        self.events = events
        self.narration = "\n\n".join(
            e.get("content", "") for e in events
            if e.get("type") == "narration" and e.get("content"))
        self.prompt = next(
            (e for e in reversed(events) if e.get("type") == "prompt"), None)
        self.state = next(
            (e for e in reversed(events) if e.get("type") == "state"), None)
        self.exit = next(
            (e for e in events if e.get("type") == "exit"), None)

    @property
    def ended(self):
        return self.exit is not None


class HeadlessClient:
    def __init__(self, repo_root=None, game_dir=None, module=None,
                 character=None, debug=False, python=None,
                 turn_timeout=300.0):
        self.repo_root = os.path.abspath(
            repo_root
            or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", ".."))
        self.game_dir = game_dir
        self.module = module
        self.character = character
        self.debug = debug
        self.python = python or sys.executable
        self.turn_timeout = turn_timeout
        self.opening = None
        self._process = None
        self._events = queue.Queue()
        self._command_seq = 0

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        argv = [self.python,
                os.path.join(self.repo_root, "run_headless.py"), "serve"]
        if self.game_dir:
            argv += ["--game-dir", self.game_dir]
        if self.module:
            argv += ["--module", self.module]
        if self.character:
            argv += ["--character", self.character]
        if self.debug:
            argv.append("--debug")
        self._process = subprocess.Popen(
            argv, cwd=self.repo_root, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8")
        reader = threading.Thread(
            target=self._read_loop, name="headless-client-reader", daemon=True)
        reader.start()
        # The engine narrates the startup kickoff before the first prompt.
        self.opening = self._collect_until_prompt()
        return self

    def close(self):
        if self._process is None:
            return
        if self._process.poll() is None:
            try:
                self._send({"type": "command", "name": "quit",
                            "id": self._next_id()})
                self._process.wait(timeout=30)
            except Exception:
                self._process.kill()
        self._process = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # -- turn API ----------------------------------------------------------

    def play(self, text, timeout=None):
        """Send one player input; block until the next prompt (or exit)."""
        self._send({"type": "input", "content": text})
        return self._collect_until_prompt(timeout)

    def command(self, name, args=None, timeout=60.0):
        """Send an out-of-band command; return its `result` event."""
        command_id = self._next_id()
        self._send({"type": "command", "id": command_id, "name": name,
                    "args": args or {}})
        deadline_events = []
        while True:
            event = self._next_event(timeout)
            deadline_events.append(event)
            if event.get("type") == "result" and \
                    event.get("id") == command_id:
                return event
            if event.get("type") == "exit":
                raise HeadlessProtocolError(
                    "session ended while waiting for %r result: %s"
                    % (name, event))

    def state(self):
        return self.command("state")["data"]

    def save(self, description=""):
        return self.command("save", {"description": description})

    def list_saves(self):
        return self.command("list_saves")["data"]

    # -- internals ---------------------------------------------------------

    def _next_id(self):
        self._command_seq += 1
        return "c%d" % self._command_seq

    def _send(self, message):
        if self._process is None or self._process.poll() is not None:
            raise HeadlessProtocolError("serve process is not running")
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()

    def _read_loop(self):
        try:
            for line in self._process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    self._report_protocol_issue("invalid_ndjson")
                    continue
                if not isinstance(event, dict):
                    self._report_protocol_issue("non_object_event")
                    continue
                if (
                    event.get("type") not in VALID_EVENT_TYPES
                    or type(event.get("seq")) is not int
                    or not isinstance(event.get("ts"), (int, float))
                    or isinstance(event.get("ts"), bool)
                ):
                    self._report_protocol_issue("non_protocol_object")
                    continue
                self._events.put(event)
        except Exception:
            self._report_protocol_issue("reader_failure")
        self._events.put(None)  # stream closed

    def _report_protocol_issue(self, reason):
        """Report a bounded transport warning without replaying leaked text."""
        self._events.put(
            {
                "type": "protocol_warning",
                "detail": str(reason)[:80],
            }
        )

    def _next_event(self, timeout=None):
        try:
            event = self._events.get(
                timeout=timeout if timeout is not None else self.turn_timeout)
        except queue.Empty:
            raise HeadlessProtocolError(
                "no engine event within %ss"
                % (timeout if timeout is not None else self.turn_timeout))
        if event is None:
            raise HeadlessProtocolError("serve process closed its stream")
        return event

    def _collect_until_prompt(self, timeout=None):
        events = []
        while True:
            event = self._next_event(timeout)
            events.append(event)
            if event.get("type") == "exit":
                return TurnResult(events)
            if event.get("type") == "state" and any(
                    e.get("type") == "prompt" for e in events):
                # state always directly follows its prompt; having both means
                # the turn is fully reported.
                return TurnResult(events)
