"""Process-local typed dice for the line the web dice tray filled (#1750).

The tray's "insert roll" puts its sentence in the input box; when the player
sends that sentence unchanged, the client sends the same faces as typed data
beside it. The web handler stores them here with the line, and the combat code
phase takes them for that line instead of reading the sentence (site C5). One
slot: every line the handler receives replaces it, so a stale entry never
answers a later line. The engine still checks the dice against the open phase.
"""
import threading

TRAY_SIDES = (4, 6, 8, 10, 12, 20)
MAX_DICE = 12

_lock = threading.Lock()
_slot = None


def typed_dice(dice):
    """[(face, sides), ...] for a well-formed payload [{sides, face}, ...], else None."""
    if not isinstance(dice, list) or not 1 <= len(dice) <= MAX_DICE:
        return None
    out = []
    for die in dice:
        if not isinstance(die, dict):
            return None
        sides, face = die.get("sides"), die.get("face")
        if type(sides) is not int or sides not in TRAY_SIDES or type(face) is not int or not 1 <= face <= sides:
            return None
        out.append((face, sides))
    return out


def put(line, dice):
    """Hold the typed dice sent with ``line`` (nothing when there are none or
    they are malformed); either way the previous entry is gone."""
    global _slot
    typed = typed_dice(dice)
    with _lock:
        _slot = (line.strip(), typed) if typed is not None and isinstance(line, str) else None


def take(line):
    """The typed dice sent with this line, once; None for any other line."""
    global _slot
    with _lock:
        if _slot is None or not isinstance(line, str) or _slot[0] != line.strip():
            return None
        dice, _slot = _slot[1], None
        return list(dice)
