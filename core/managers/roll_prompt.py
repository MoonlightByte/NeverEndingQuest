"""Process-local input boundary for a durable pending rules check.

    A prompt token changes on each input attempt. Web clients may submit it
    once; the engine owns the dice and never accepts client-authored totals.

    #1811: line_roll() is the typed roll the line being read answers, for a
    client with no panel. A check's is built from the panel's own record; a
    hit die or a combat roll has no panel, so its read opens one with
    open_line, which no listener hears: the web panel stays the check's alone.
"""
from contextlib import contextmanager
from copy import deepcopy
import threading
import uuid

_lock = threading.RLock()
_active = None
_open_roll = None
_listener = None


def set_listener(listener):
    global _listener
    _listener = listener


def current():
    with _lock:
        return deepcopy(_active)


def publish(entry):
    global _active
    with _lock:
        _active = ({**deepcopy(entry), 'id': uuid.uuid4().hex, 'submitted': False}
                   if entry is not None else None)
        snapshot = deepcopy(_active)
    if _listener is not None:
        _listener(snapshot)


def _check_roll(entry):
    """The typed roll of a published check: what its panel shows, from the same record."""
    roll = {"kind": "check", "label": "%s for %s" % (entry.get("label"), entry.get("characterName")),
            "mode": entry.get("netMode"), "dice": [{"count": entry.get("faces"), "sides": 20}],
            "eachDie": entry.get("faces") != 1}
    if entry.get("reason"):
        roll["reason"] = entry["reason"]
    if entry.get("dc") is not None:
        roll["dc"] = entry["dc"]
    if entry.get("dice"):
        roll["addedDice"] = deepcopy(entry["dice"])
    return roll


def open_line(request):
    """Hold the typed roll of a read with no panel; None clears it."""
    global _open_roll
    with _lock:
        _open_roll = deepcopy(request)


@contextmanager
def reading_line(request):
    """The typed roll stays open only while its line is read."""
    open_line(request)
    try:
        yield
    finally:
        open_line(None)


def line_roll():
    """The typed roll the line being read answers, or None."""
    with _lock:
        return _check_roll(_active) if _active else deepcopy(_open_roll)


def submit(token, faces, enqueue):
    """Validate and enqueue under one lock, rejecting stale/duplicate tabs."""
    with _lock:
        if not _active or _active['id'] != token or _active['submitted']:
            raise ValueError('This roll is no longer waiting. Refresh the current check.')
        count = _active['faces']
        if faces is not None and (not isinstance(faces, list) or len(faces) != count
                                 or any(type(n) is not int or not 1 <= n <= 20 for n in faces)):
            raise ValueError(f'Enter {count} individual d20 result(s), from 1 to 20.')
        _active['submitted'] = True
        try:
            enqueue('' if faces is None else ' '.join(map(str, faces)))
        except BaseException:
            _active['submitted'] = False
            raise
        if _listener is not None:
            _listener(deepcopy(_active))
