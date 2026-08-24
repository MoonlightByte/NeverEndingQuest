# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""NDJSON protocol writer/parser for headless mode.

One JSON object per line on the real stdout. Every event carries:
  type - event name (hello, startup, narration, status, prompt, state,
         debug, system, compression, module_progress, result, exit)
  seq  - monotonic sequence number
  ts   - unix timestamp (seconds, 3 decimal places)

Agent -> server lines are parsed by parse_command_line(); only two shapes
are valid:
  {"type": "input", "content": "..."}
  {"type": "command", "id": "...", "name": "...", "args": {...}}
"""

import json
import threading
import time

PROTOCOL_VERSION = 1

VALID_COMMAND_NAMES = {
    "state",
    "save",
    "list_saves",
    "restore",
    "reset",
    "delete_save",
    "quit",
}


class ProtocolWriter:
    """Thread-safe NDJSON event emitter bound to one output stream."""

    def __init__(self, stream, observer=None):
        self._stream = stream
        self._observer = observer
        self._lock = threading.Lock()
        self._seq = 0

    def emit(self, event_type, **fields):
        payload = {"type": event_type}
        payload.update(fields)
        delivered = True
        with self._lock:
            self._seq += 1
            payload["seq"] = self._seq
            payload["ts"] = round(time.time(), 3)
            try:
                self._stream.write(json.dumps(payload, ensure_ascii=True) + "\n")
                self._stream.flush()
            except (BrokenPipeError, OSError, ValueError):
                # Callers that own a durable delivery receipt need to know the
                # agent went away so they do not acknowledge output it never
                # received. Existing fire-and-forget callers may ignore this.
                delivered = False
        if self._observer is not None:
            try:
                self._observer(payload)
            except Exception:
                pass
        return delivered


def parse_command_line(line):
    """Parse one agent line. Returns (dict, None) or (None, error_string)."""
    line = line.strip()
    if not line:
        return None, None
    try:
        data = json.loads(line)
    except (ValueError, TypeError) as exc:
        return None, "invalid JSON: %s" % exc
    if not isinstance(data, dict):
        return None, "expected a JSON object"
    msg_type = data.get("type")
    if msg_type == "input":
        content = data.get("content")
        if not isinstance(content, str):
            return None, "input requires a string 'content'"
        return data, None
    if msg_type == "command":
        name = data.get("name")
        if name not in VALID_COMMAND_NAMES:
            return None, "unknown command %r (valid: %s)" % (
                name, ", ".join(sorted(VALID_COMMAND_NAMES)))
        if "args" in data and not isinstance(data["args"], dict):
            return None, "command 'args' must be an object"
        return data, None
    return None, "unknown message type %r (expected 'input' or 'command')"
