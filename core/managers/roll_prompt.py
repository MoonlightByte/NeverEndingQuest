"""Process-local input boundary for a durable pending rules check.

    A prompt token changes on each input attempt. Web clients may submit it
    once; the engine owns the dice and never accepts client-authored totals.
"""
from copy import deepcopy
import threading
import uuid

_lock = threading.RLock()
_active = None
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
