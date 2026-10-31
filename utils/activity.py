# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Process-wide activity record for GET /health (#1681, #1682).

- touch(): the time of the last player input or model send, reported as
  last_activity so a supervisor can tell an idle world from a busy one.
- model_send(): a context manager around every model send (provider child or
  in-process create_completion); sends_in_flight() is how many are running.
- save_completed() / save_seq(): a counter that moves on each completed save,
  so the desktop updater can offer an update right after one.

Plain counters under one lock; nothing here imports the engine.
"""

import contextlib
import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_STATE = {"last_activity": None, "sends": 0, "save_seq": 0}


def touch():
    with _LOCK:
        _STATE["last_activity"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


def last_activity():
    with _LOCK:
        return _STATE["last_activity"]


@contextlib.contextmanager
def model_send():
    touch()
    with _LOCK:
        _STATE["sends"] += 1
    try:
        yield
    finally:
        with _LOCK:
            _STATE["sends"] -= 1


def sends_in_flight():
    with _LOCK:
        return _STATE["sends"]


def save_completed():
    with _LOCK:
        _STATE["save_seq"] += 1


def save_seq():
    with _LOCK:
        return _STATE["save_seq"]
