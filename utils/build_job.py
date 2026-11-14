"""The in-game module build's background job and what it leaves for the game
thread (#2021 J1b-2).

The game loop keeps the conversation history as its own in-memory list and
saves the whole list at each turn's end, so no other thread may write history.
The build thread therefore never writes it: when the build ends it leaves one
due record here, and the game thread's pump (main.py) applies it, as the
startup welcome's handback is applied.

A record is one of:
- an announcement: the build published a new place; the pump runs the DM's
  announcement on its own scope and applies [note][reply];
- a failure: the build ended without a place; the player saw the line at once
  (the presenter below) and the pump records it in history.

Each record carries the game epoch the job started in; the pump drops a stale
one (a Load or Reset since then).
"""
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

_lock = threading.Lock()
_job = None
_due = []
_failure_presenter = None


@dataclass
class DueRecord:
    kind: str  # "announcement" or "failure"
    build_id: str
    start_epoch: int
    module_name: Optional[str] = None
    dm_note: Optional[str] = None
    line: Optional[str] = None
    message_id: Optional[str] = None
    result: Any = field(default=None, repr=False)


def register_job(thread, build_id):
    global _job
    with _lock:
        _job = (thread, build_id)


def clear_job(thread):
    global _job
    with _lock:
        if _job is not None and _job[0] is thread:
            _job = None


def active_job():
    """The running job's thread, or None."""
    with _lock:
        return _job[0] if _job is not None else None


def wait_for_job(timeout=None):
    """Join the running job, if any (teardown and tests)."""
    thread = active_job()
    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout)
    return thread is None or not thread.is_alive()


def post_due(record):
    with _lock:
        _due.append(record)


def take_due():
    """Remove and return every due record, oldest first."""
    with _lock:
        records = list(_due)
        _due.clear()
        return records


def put_back_due(records):
    """Put back records the pump could not apply yet, ahead of newer ones."""
    with _lock:
        _due[:0] = list(records)


def has_due(kind=None):
    with _lock:
        return any(kind is None or record.kind == kind for record in _due)


def drop_due():
    """Teardown: drop every record that has not started."""
    with _lock:
        dropped = len(_due)
        _due.clear()
        return dropped


def set_failure_presenter(presenter):
    """The game registers how a failed build's line is shown at once; it
    returns the line it showed."""
    global _failure_presenter
    _failure_presenter = presenter


def present_failure(result, message_id):
    presenter = _failure_presenter
    if presenter is None:
        return None
    return presenter(result, message_id)
