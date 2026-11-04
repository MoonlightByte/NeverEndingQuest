"""Process-local boundary for a closed startup menu (#1129).

    While a menu is being read its options are published for any client that
    draws them. A prompt token changes on each read and a client may answer it
    once. A click is sent to the game as the number the player could have
    typed, so the read loop behind it is the one typing uses.
"""
from copy import deepcopy
import threading
import uuid

_lock = threading.RLock()
_active = None
_listener = None
_draws_options = None


def set_listener(listener, draws_options=None):
    """draws_options: whether the player's client shows the options as buttons."""
    global _listener, _draws_options
    _listener = listener
    _draws_options = draws_options


def draws_options():
    return bool(_draws_options is not None and _draws_options())


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


def spend():
    """A typed line answers this read, so a click behind it must not reach the next one."""
    with _lock:
        if _active:
            _active['submitted'] = True


def submit(token, number, enqueue):
    """Validate and enqueue under one lock, rejecting stale and duplicate clicks."""
    with _lock:
        if not _active or _active['id'] != token or _active['submitted']:
            raise ValueError('That choice is no longer open.')
        option = next((o for o in _active['options'] if type(number) is int and o['number'] == number), None)
        if option is None or option.get('disabled'):
            raise ValueError('That choice is not available.')
        _active['submitted'] = True
        try:
            enqueue(str(number), option['label'])
        except BaseException:
            _active['submitted'] = False
            raise
        snapshot = deepcopy(_active)
    if _listener is not None:
        _listener(snapshot)
