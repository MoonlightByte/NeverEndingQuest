# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Process-local authority for serialized combat provider invocations.

This is deliberately not persisted gameplay state. It prevents two live
provider attempts from both reaching an acceptance boundary, while persisted
encounter/turn/revision/dependency values remain the durable acceptance facts.
Load, Reset, and exit supersede the current generation before proceeding.
"""

from dataclasses import dataclass
import threading
import time
import uuid


@dataclass(frozen=True)
class InvocationClaim:
    logical_invocation_id: str
    attempt_id: str
    generation: int
    callsite: str
    owner_thread_id: int


_condition = threading.Condition(threading.RLock())
_current = None
_generation = 0
_supersession_barriers = set()


class InvocationSupersededError(RuntimeError):
    """Raised when a nested boundary observes a fenced invocation."""

    def __init__(self, message, claim=None):
        super().__init__(message)
        self.claim = claim


def begin_invocation(callsite, wait_observer=None):
    """Become the sole live invocation without reviving an overlapping attempt.

    An attempt submitted while another logical operation is live waits for that
    operation to settle so callers can retain honest progress.  It is then
    rejected with its own identity instead of becoming a later provider
    dispatch against whatever state the first operation produced.  An attempt
    submitted while only a Load/Reset barrier is active may start after the
    barrier ends because it did not overlap an accepted gameplay operation.
    """
    global _current, _generation
    last_notice = 0.0
    with _condition:
        _generation += 1
        claim = InvocationClaim(
            logical_invocation_id="combat-invocation:%s" % uuid.uuid4().hex,
            attempt_id="combat-attempt:%s" % uuid.uuid4().hex,
            generation=_generation,
            callsite=str(callsite),
            owner_thread_id=threading.get_ident(),
        )
        overlapped_live_invocation = _current is not None
        while _current is not None or _supersession_barriers:
            if _current is not None:
                overlapped_live_invocation = True
            now = time.monotonic()
            if wait_observer is not None and now - last_notice >= 1.0:
                try:
                    wait_observer(_current)
                except Exception:
                    pass
                last_notice = now
            _condition.wait(timeout=0.25)
        if overlapped_live_invocation:
            raise InvocationSupersededError(
                "Combat invocation overlapped a completed or superseded "
                "logical operation and cannot dispatch later",
                claim=claim,
            )
        _current = claim
        return claim


def invocation_is_current(claim):
    with _condition:
        return _current == claim


def require_current_invocation(claim):
    """Return the claim only while it still owns acceptance authority."""
    if not invocation_is_current(claim):
        raise InvocationSupersededError(
            "Combat provider invocation was superseded before acceptance"
        )
    return claim


def complete_invocation(claim):
    """Release only the exact current claim; stale completions are no-ops."""
    global _current
    with _condition:
        if _current == claim:
            _current = None
            _condition.notify_all()
            return True
        return False


def supersede_invocations(reason):
    """Fence the live generation before Load, Reset, or process exit."""
    global _current, _generation
    with _condition:
        superseded = _current
        _current = None
        _generation += 1
        _condition.notify_all()
        return {
            "reason": str(reason),
            "attemptId": superseded.attempt_id if superseded else None,
            "generation": _generation,
        }


def begin_invocation_supersession(reason):
    """Fence current work and block new dispatch until a lifecycle operation ends."""
    global _current, _generation
    token = "combat-supersession:%s" % uuid.uuid4().hex
    with _condition:
        superseded = _current
        _current = None
        _generation += 1
        _supersession_barriers.add(token)
        _condition.notify_all()
        return {
            "token": token,
            "reason": str(reason),
            "attemptId": superseded.attempt_id if superseded else None,
            "generation": _generation,
        }


def end_invocation_supersession(barrier):
    """Release exactly one lifecycle barrier after its mutation boundary exits."""
    token = barrier.get("token") if isinstance(barrier, dict) else barrier
    with _condition:
        removed = token in _supersession_barriers
        _supersession_barriers.discard(token)
        _condition.notify_all()
        return removed


def reset_invocation_authority_for_tests():
    global _current, _generation
    with _condition:
        _current = None
        _generation = 0
        _supersession_barriers.clear()
        _condition.notify_all()
