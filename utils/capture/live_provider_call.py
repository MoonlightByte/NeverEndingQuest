"""Private cancellable transport for the live pre-mutation turn seam.

This module owns no gameplay state.  It runs one already-frozen provider
request in one spawned child, returns one primitive response envelope, and
fully reaps that child before returning or reissuing.
"""

import copy
import logging
import os
import pickle
import random
import subprocess
import sys
import threading
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import uuid4


_LOGGER = logging.getLogger(__name__)


_REQUIRED_TASK_IDS = frozenset(
    {
        "T014",
        "T015",
        "T016",
        "T021",
        "T035",
        "T038",
        "T039",
        "T040",
        "T041",
        "T042",
        "T043",
        "T044",
        "T047",
        "T048",
        "T049",
        "T065",
        "T067",
        "T077",
        "T078",
        "T079",
        "T082",
        "T092",
        "T093",
        "T096",
        "T097",
        "T114",
        "T115",
        "T116",
        "T117",
        "T118",
        "T119",
        "T120",
    }
)
_ADVISORY_TASK_IDS = frozenset(
    {
        "T013",
        "T018",
        "T019",
        "T027",
        "T050",
        "T051",
        "T052",
        "T053",
        "T054",
        "T063",
        "T064",
        "T084",
        "T085",
        "T087",
        "T090",
        "T091",
        "T107",
        "T108",
        "T113",
        "T105",
        "T112",
    }
)
_LIVE_TASK_IDS = _REQUIRED_TASK_IDS | _ADVISORY_TASK_IDS
_HEARTBEAT_SECONDS = 10.0
_WATCHDOG_SECONDS = 600.0
_WIZARD_READ_INACTIVITY_SECONDS = 40.0
_WIZARD_BACKSTOP_SECONDS = 180.0
_WIZARD_TASK_IDS = frozenset({"T092", "T093"})
# Level-up interview and specialist calls answer in 10 to 30 s; a provider
# that accepts the body and never replies (run 9, 2026-09-14: one call in
# ~330) is reissued after 2 minutes instead of 10. Still a reissue trigger,
# never a terminal (#193 B2-iii); owner ruling 2026-09-14.
_LEVEL_UP_TASK_IDS = frozenset({"T047", "T048", "T115", "T116", "T117", "T118", "T119", "T120"})
_LEVEL_UP_BACKSTOP_SECONDS = 120.0
_NO_WATCHDOG_ADVISORY_TASK_IDS = frozenset({"T105", "T112"})
# Tasks whose SUCCESS envelopes are also written to the master log by the
# parent (their callers do not log_api_call themselves).
_SUCCESS_LOG_TASK_IDS = frozenset({"T047", "T048", "T105", "T108", "T113",
                                   "T115", "T116", "T117", "T118", "T119", "T120"})
_MAX_BACKOFF_SECONDS = 8.0
_PERMANENT_ERROR_SECONDS = 60.0
# Transport phases the child reports, in the order a healthy generation
# passes through them (#409 plan section 4). Evidence only: never authority.
_PHASE_NAMES = (
    "spawned", "payload_read", "connecting", "connected", "secured", "sent",
    "acknowledged", "working", "receiving", "done", "failed",
)
# Phases in which the provider has received the request but has done no
# acknowledged work yet. Only an endpoint that acknowledges BEFORE working
# (the Responses endpoint: response.created measured at 0.7-0.9 s for every
# size and effort) is subject to the pre-acknowledgment reissue trigger,
# D-409-2 (ii), owner-ruled 2026-09-19. It is a reissue trigger, never a
# terminal (#193 B2-iii), and it never fires once work is acknowledged.
_PRE_ACK_PHASES = frozenset({"sent"})
_ACK_BACKSTOP_SECONDS = 30.0
_ACK_ENDPOINTS = frozenset({"responses"})
# httpcore trace events -> transport phases (the child observes them through
# the library's own logging trace; nothing is patched).
_RETRYABLE_STREAM_ERROR_CODES = frozenset({"server_error", "rate_limit_exceeded"})
_HTTPCORE_PHASES = (
    ("connect_tcp.started", "connecting"),
    ("connect_tcp.complete", "connected"),
    ("start_tls.complete", "secured"),
    ("send_request_body.complete", "sent"),
)


class LiveProviderSuperseded(RuntimeError):
    """The player requested a lifecycle operation before mutation began."""


class LiveProviderUnavailable(RuntimeError):
    """One fully reaped advisory provider attempt was unavailable."""

    def __init__(self, task_id, envelope=None):
        self.task_id = str(task_id)
        self.envelope = dict(envelope or {})
        super().__init__("%s advisory provider attempt was unavailable" % self.task_id)


class LiveProviderCompletedError(RuntimeError):
    """A completed provider error handed back to the caller (#240).

    Deterministic errors return to the existing caller immediately; required
    transport failures reissue until recovery or supersession. The existing
    T093 completed-empty policy is unchanged. http_status remains available
    to the caller's classifier.
    """

    def __init__(self, task_id, envelope=None):
        self.task_id = str(task_id)
        self.envelope = dict(envelope or {})
        self.http_status = self.envelope.get("http_status")
        self.status_code = self.http_status
        super().__init__(
            "%s provider request completed with a %s error (%s, status %s)"
            % (self.task_id, self.envelope.get("disposition", "unknown"),
               self.envelope.get("error_class", "unknown"), self.http_status)
        )


def _can_promote_player_acted(existing, kind):
    """Return whether a destructive command may replace the welcome marker."""
    return (
        isinstance(existing, dict)
        and existing.get("kind") == "player_acted"
        and str(kind) in ("restore", "reset")
    )


@dataclass
class LiveTurnScope:
    """In-memory lifecycle state for one outer player turn."""

    phase: str = "PRE_MUTATION"
    operation_id: str = field(default_factory=lambda: str(uuid4()))
    generation: int = 0
    supersession: dict = None
    pending_saves: deque = field(default_factory=deque)
    quiescent: threading.Event = field(default_factory=threading.Event)
    lock: threading.RLock = field(default_factory=threading.RLock)
    controls_open: bool = True
    advisory_scopes: list = field(default_factory=list)
    purpose: str = "turn"

    def next_generation(self):
        with self.lock:
            self.generation += 1
            return self.generation

    def request_supersession(self, kind, operation_id=None):
        with self.lock:
            if not self.controls_open:
                return {
                    "kind": "turn_complete",
                    "operation_id": self.operation_id,
                    "accepted": False,
                }
            accepted = self.supersession is None or _can_promote_player_acted(
                self.supersession, kind
            )
            if accepted:
                self.supersession = {
                    "kind": str(kind),
                    "operation_id": operation_id or str(uuid4()),
                }
            result = dict(self.supersession)
            result["accepted"] = accepted
            advisory_scopes = tuple(self.advisory_scopes)
        for advisory_scope in advisory_scopes:
            advisory_scope.seal()
        return result

    def is_superseded(self):
        with self.lock:
            return self.supersession is not None

    def register_advisory_scopes(self, advisory_scopes):
        with self.lock:
            if self.supersession is not None or (
                not self.controls_open and self is not _executing_control_scope.get()
            ):
                return False
            self.advisory_scopes.extend(advisory_scopes)
            return True

    def seal_advisory_scopes(self):
        with self.lock:
            scopes = tuple(self.advisory_scopes)
        for advisory_scope in scopes:
            advisory_scope.seal()
        return scopes


@dataclass
class AdvisoryProviderScope:
    """One task-owned, beat-fenced advisory provider lifetime."""

    parent: LiveTurnScope
    beat_id: str
    completion_required: bool = False
    generation: int = 0
    sealed: threading.Event = field(default_factory=threading.Event)
    quiescent: threading.Event = field(default_factory=threading.Event)
    lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def operation_id(self):
        return self.parent.operation_id

    def next_generation(self):
        with self.lock:
            self.generation += 1
            return self.generation

    def is_superseded(self):
        return self.sealed.is_set() or self.parent.is_superseded()

    def seal(self):
        self.sealed.set()

    def finish(self):
        self.quiescent.set()


def open_advisory_scope(parent, beat_id):
    """Register one exact beat child before its monitor may start."""
    if parent is None or parent is not get_live_turn_scope():
        return None
    scopes = open_advisory_scopes(parent, beat_id, 1)
    return scopes[0] if scopes else None


def open_advisory_scopes(parent, beat_id, count, *, completion_required=False):
    """Atomically register the complete intended advisory child set."""
    if parent is None or count <= 0:
        return ()
    if (
        parent is not get_live_turn_scope()
        and parent is not get_active_welcome_scope()
        and parent is not _executing_control_scope.get()
    ):
        return ()
    scopes = tuple(
        AdvisoryProviderScope(
            parent=parent,
            beat_id=str(beat_id),
            completion_required=bool(completion_required),
        )
        for _index in range(count)
    )
    if not parent.register_advisory_scopes(scopes):
        return ()
    return scopes

_scope_guard = threading.RLock()
_active_scope = None
_closing_scopes = []
_executing_control_scope = ContextVar("executing_live_control_scope", default=None)


def open_live_turn_scope():
    """Open the sole live player-turn scope on the game thread."""
    global _active_scope
    with _scope_guard:
        if _active_scope is not None:
            raise RuntimeError("a live player-turn scope is already active")
        _active_scope = LiveTurnScope()
        return _active_scope


def get_live_turn_scope():
    with _scope_guard:
        return _active_scope


def get_live_provider_scope():
    """Accepted callback authority takes precedence only in its execution context."""
    return _executing_control_scope.get() or get_live_turn_scope()


@contextmanager
def combat_execution_authority(invocation_claim=None):
    """Borrow caller authority or own an unowned combat entry through handoff.

    This is an in-memory lifetime boundary, not additional recovery state.
    Recursive combat callers must forward the yielded claim.
    """
    from core.combat.invocation import (
        InvocationSupersededError,
        begin_invocation,
        complete_invocation,
        require_current_invocation,
    )

    scope = get_live_turn_scope()
    owns_scope = scope is None
    owns_claim = invocation_claim is None
    if owns_scope:
        scope = open_live_turn_scope()
    engine_fault = False
    try:
        if scope.is_superseded():
            raise LiveProviderSuperseded("combat entry was superseded")
        if owns_claim:
            invocation_claim = begin_invocation("combat")
        if scope.is_superseded():
            raise LiveProviderSuperseded("combat entry was superseded")
        require_current_invocation(invocation_claim)
        yield invocation_claim
    except (LiveProviderSuperseded, InvocationSupersededError):
        raise
    except BaseException:
        engine_fault = True
        raise
    finally:
        if owns_claim and invocation_claim is not None:
            complete_invocation(invocation_claim)
        if owns_scope:
            if engine_fault:
                abort_live_turn_scope(scope=scope)
            else:
                finish_live_turn_scope(scope)
            scope.quiescent.wait()


def get_lifecycle_turn_scopes():
    """Return active and closing turn scopes in one authority snapshot."""
    with _scope_guard:
        scopes = []
        if _active_scope is not None:
            scopes.append(_active_scope)
        scopes.extend(
            scope for scope in _closing_scopes
            if scope is not _active_scope and not scope.quiescent.is_set()
        )
        return tuple(scopes)


def live_provider_policy(task_id):
    """Return the reviewed policy only while a live player-turn scope exists."""
    if get_live_provider_scope() is None:
        return False
    if task_id in _REQUIRED_TASK_IDS:
        return "required"
    if task_id in _ADVISORY_TASK_IDS:
        return "advisory"
    return False


def close_live_turn_scope(scope):
    """Close only the exact active scope supplied by its game thread."""
    global _active_scope
    with _scope_guard:
        if _active_scope is not scope:
            return
        with scope.lock:
            scope.controls_open = False
        advisory_scopes = scope.seal_advisory_scopes()
        if all(item is not scope for item in _closing_scopes):
            _closing_scopes.append(scope)
        _active_scope = None
    def publish_quiescence():
        for advisory_scope in advisory_scopes:
            advisory_scope.quiescent.wait()
        scope.phase = "QUIESCENT"
        scope.quiescent.set()
        with _scope_guard:
            _closing_scopes[:] = [
                item for item in _closing_scopes if item is not scope
            ]
    if all(item.quiescent.is_set() for item in advisory_scopes):
        publish_quiescence()
    else:
        threading.Thread(
            target=publish_quiescence,
            name="live-turn-advisory-reap",
            daemon=True,
        ).start()


def request_live_turn_supersession(kind, operation_id=None, scope=None):
    """Fence the current live turn, optionally only if it is ``scope``."""
    with _scope_guard:
        if scope is None:
            target_scope = _active_scope
        elif scope is _active_scope or any(
            item is scope for item in _closing_scopes
        ):
            target_scope = scope
        else:
            target_scope = None
        if target_scope is None:
            return None
    result = target_scope.request_supersession(kind, operation_id)
    if result.get("accepted"):
        _safe_emit(_emit_working, "Applying your requested game control...")
        from core.combat.invocation import supersede_invocations
        from core.managers.campaign_manager import _party_module_transition_lock

        # Serialize the fence with combat's mutation authority. A write that
        # already owns the transition lock completes before acceptance is
        # returned; every later write observes the superseded invocation.
        with _party_module_transition_lock():
            supersede_invocations(kind)
    return result


def request_lifecycle_turn_supersession(kind, operation_id=None):
    """Atomically claim and seal every active/closing player-turn scope."""
    requested_id = operation_id or str(uuid4())
    with _scope_guard:
        scopes = []
        if _active_scope is not None:
            scopes.append(_active_scope)
        scopes.extend(
            item for item in _closing_scopes
            if item is not _active_scope and not item.quiescent.is_set()
        )
        results = tuple(
            scope.request_supersession(kind, requested_id) for scope in scopes
        )
    if any(result.get("accepted") for result in results):
        # Never acquire the status lock while holding the scope registry or a
        # scope lock. Ready admission takes those locks in the other direction.
        _safe_emit(_emit_working, "Applying your requested game control...")
        from core.combat.invocation import supersede_invocations
        from core.managers.campaign_manager import _party_module_transition_lock

        with _party_module_transition_lock():
            supersede_invocations(kind)
    return tuple(scopes), results


# --- Detached startup-welcome scope (issue #214) ---------------------------
# The off-thread startup welcome owns its OWN LiveTurnScope, deliberately NOT
# registered as _active_scope (the player-turn singleton would collide with
# open_live_turn_scope). This registry only makes that scope visible to the
# web action gate and the restore/reset handlers so Save/Load/Reset are never
# wrongly refused during a background welcome and can supersede + quiesce it.
_welcome_scope = None


def register_welcome_scope(scope):
    global _welcome_scope
    with _scope_guard:
        _welcome_scope = scope
        return scope


def get_active_welcome_scope():
    with _scope_guard:
        return _welcome_scope


def clear_welcome_scope(scope):
    """Clear only the exact registered welcome scope."""
    global _welcome_scope
    with _scope_guard:
        if _welcome_scope is scope:
            _welcome_scope = None


def queue_live_save(execute, complete, operation_id=None, scope=None, cancel=None):
    """Queue one already-acknowledged Save for the game-thread boundary.

    Default scope stays the live player-turn singleton; #214 passes the
    detached welcome scope explicitly so welcome-boundary operations drain
    on the game thread before welcome quiescence."""
    scope = scope if scope is not None else get_live_turn_scope()
    if scope is None:
        return None
    requested_id = operation_id or str(uuid4())
    record = {
        "operation_id": requested_id,
        "execute": execute,
        "complete": complete,
        "cancel": cancel,
    }
    cancelled_by = None
    with scope.lock:
        if not scope.controls_open:
            if (
                scope.purpose == "travel_recovery" and scope.supersession
                and scope.supersession.get("kind") in {"restore", "reset", "quit", "web_exit"}
            ):
                cancelled_by = dict(scope.supersession)
            else:
                return None
        else:
            for pending in scope.pending_saves:
                if pending["operation_id"] == requested_id:
                    return requested_id
            scope.pending_saves.append(record)
    if cancelled_by is not None:
        _complete_cancelled_recovery_save(record, cancelled_by)
    return record["operation_id"]


def _complete_cancelled_recovery_save(record, cause):
    try:
        if record.get("cancel") is not None:
            record["cancel"](record["operation_id"], cause)
        else:
            record["complete"]((False, "Waiting Save cancelled by %s (%s)." % (
                cause["kind"], cause["operation_id"],
            )))
    except Exception:
        # Delivery failure cannot revive this Save or block quiescence.
        pass


def cancel_recovery_saves(scope):
    """Cancel only unstarted recovery Saves after an accepted lifecycle choice.

    #248 / D-248-1: a fault or elapsed wait cannot cancel a Save. Admission is
    sealed before callbacks and before quiescence; no snapshot of partial or
    replacement state is taken. Started records have already left this deque.
    """
    with scope.lock:
        supersession = scope.supersession
        if (
            scope.purpose != "travel_recovery"
            or not supersession
            or supersession.get("kind") not in {"restore", "reset", "quit", "web_exit"}
        ):
            return False
        scope.controls_open = False
        pending = list(scope.pending_saves)
        scope.pending_saves.clear()
        cause = dict(supersession)
    for record in pending:
        _complete_cancelled_recovery_save(record, cause)
    return True


def claim_destructive_operation(scope, kind, execute, complete,
                                operation_id=None):
    """Atomically claim (or promote from player_acted) a destructive
    supersession AND append its executable record in ONE scope-lock
    transaction (#214: the seal can never split an accepted claim from its
    record; an accepted destructive operation always has a queued record).

    Returns {"status": "queued"|"conflict"|"closed", "kind", "operation_id"}.
    """
    with scope.lock:
        if not scope.controls_open:
            return {
                "status": "closed",
                "kind": "turn_complete",
                "operation_id": scope.operation_id,
            }
        existing = scope.supersession
        if existing is not None and not _can_promote_player_acted(existing, kind):
            # player_acted only cancels the welcome - the first destructive
            # request promotes past it; anything else is a real conflict.
            return {
                "status": "conflict",
                "kind": existing.get("kind"),
                "operation_id": existing.get("operation_id"),
            }
        record_id = operation_id or str(uuid4())
        scope.supersession = {"kind": str(kind), "operation_id": record_id}
        scope.pending_saves.append({
            "operation_id": record_id,
            "execute": execute,
            "complete": complete,
        })
        return {"status": "queued", "kind": str(kind),
                "operation_id": record_id}


def drain_live_saves(scope, *, seal=False):
    """Execute accepted Saves FIFO on the game thread, optionally sealing it."""
    drained = False
    while True:
        with scope.lock:
            cancelled = (
                scope.purpose == "travel_recovery" and scope.supersession
                and scope.supersession.get("kind") in {"restore", "reset", "quit", "web_exit"}
            )
            if not scope.pending_saves:
                if seal:
                    scope.controls_open = False
                return drained
            record = None if cancelled else scope.pending_saves.popleft()
        if cancelled:
            cancel_recovery_saves(scope)
            return drained
        control_scope = LiveTurnScope(
            operation_id=record["operation_id"], purpose="accepted_control",
            controls_open=False,
        )
        record["provider_scope"] = control_scope
        token = _executing_control_scope.set(control_scope)
        try:
            outcome = record["execute"]()
        except BaseException as exc:
            outcome = (False, "%s: %s" % (type(exc).__name__, exc))
        finally:
            # Synchronous provider calls have returned through their reap-finally
            # before the accepted callback completes. This is not a second turn
            # registry and must never replace or close the original turn scope.
            control_scope.phase = "QUIESCENT"
            control_scope.quiescent.set()
            _executing_control_scope.reset(token)
        try:
            record["complete"](outcome)
        except Exception:
            # Completion notification is presentational (a disconnected web
            # client makes socketio.emit raise); it must never stop the
            # drain or block the terminal's quiescence guarantee.
            pass
        drained = True


def finish_live_turn_scope(scope):
    """Drain accepted saves and publish game-thread quiescence."""
    if scope.is_superseded():
        scopes = scope.seal_advisory_scopes()
        started = time.monotonic()
        while not all(item.quiescent.wait(0.1) for item in scopes):
            _safe_emit(
                _emit_working,
                "Finishing background character work safely (%d seconds elapsed)..."
                % max(1, int(time.monotonic() - started)),
            )
    drain_live_saves(scope, seal=True)
    close_live_turn_scope(scope)


def service_live_input_boundary():
    """Service accepted controls while the game thread is safely at input.

    Deliberately called outside best-effort presentation hooks: supersession
    must unwind the game, not become EOF or a swallowed status failure.
    """
    scope = get_live_turn_scope()
    if scope is None:
        return False
    if scope.is_superseded():
        raise LiveProviderSuperseded("input boundary was superseded")
    drained = drain_live_saves(scope, seal=False)
    if scope.is_superseded():
        raise LiveProviderSuperseded("input boundary was superseded")
    return drained


def abort_live_turn_scope(
    message="the game loop stopped before a safe save boundary",
    scope=None,
):
    """Close a failed engine scope without snapshotting a partial turn."""
    scope = scope if scope is not None else get_live_turn_scope()
    if scope is None or get_live_turn_scope() is not scope:
        return
    with scope.lock:
        scope.controls_open = False
        pending = list(scope.pending_saves)
        scope.pending_saves.clear()
    for record in pending:
        try:
            record["complete"]((False, message))
        except Exception:
            pass
    close_live_turn_scope(scope)


def _primitive_usage(response):
    from core.ai.api_client import usage_detail_counts

    usage = getattr(response, "usage", None)
    cached_tokens, reasoning_tokens = usage_detail_counts(usage)
    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def _success_envelope(response, request_kwargs):
    choice = response.choices[0]
    return {
        "kind": "success",
        "content": choice.message.content,
        "response_id": str(getattr(response, "id", "") or ""),
        "provider": str(getattr(response, "provider", "") or ""),
        "task_id": getattr(response, "task_id", None),
        "model": str(getattr(response, "model", "") or request_kwargs.get("model", "")),
        "finish_reason": str(getattr(choice, "finish_reason", "unknown") or "unknown"),
        "usage": _primitive_usage(response),
        "usage_invocation_id": getattr(response, "_usage_invocation_id", None),
        "sent_messages": getattr(response, "sent_messages", None),
    }


def _http_status_of(original):
    """One coalescing HTTP-status read across provider SDK error shapes.

    openai: ``status_code`` (int) and a str ``code``; google.genai: an int
    ``code`` and no ``status_code``. Order: status_code, then the response's
    status_code, then ``code`` only when it is an int. No provider branch.
    """
    if original is None:
        return None
    for value in (
        getattr(original, "status_code", None),
        getattr(getattr(original, "response", None), "status_code", None),
        getattr(original, "code", None),
    ):
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _structured_error_code(exc, original):
    """Provider error CODE from structured fields (never the message text)."""
    for item in (original, exc):
        if item is None:
            continue
        value = getattr(item, "code", None)
        if isinstance(value, str) and value:
            return value
        body = getattr(item, "body", None)
        if isinstance(body, dict):
            detail = body.get("error")
            detail = detail if isinstance(detail, dict) else body
            value = detail.get("code")
            if isinstance(value, str) and value:
                return value
    return None


def _error_disposition(exc, original, status, error_code=None):
    """Classify from exception types/status/codes only; provider prose is never authority."""
    if type(exc).__name__ == "ProviderEmptyResponse":
        return "empty"
    if isinstance(error_code, str):
        from utils.provider_errors import QUOTA_ERROR_CODES

        if error_code.lower() in QUOTA_ERROR_CODES:
            # Out of funds arrives as a 429 like a rate limit, but no reissue
            # can pay the bill: hand it to the caller so the player is told.
            return "deterministic"
    if status in {408, 409, 429} or (
        isinstance(status, int) and 500 <= status < 600
    ):
        return "retryable_http"
    if isinstance(error_code, str) and error_code.lower() in _RETRYABLE_STREAM_ERROR_CODES:
        # A streamed Responses answer that FAILED after acknowledgment
        # carries its structured code in the terminal event instead of an
        # HTTP status; the same classes a status would make retryable.
        return "retryable_http"
    cause = original if original is not None else exc
    cause_types = {base.__name__ for base in type(cause).__mro__}
    if cause_types.intersection(
        {
            "APITimeoutError",
            "APIConnectionError",
            "TimeoutException",
            "TransportError",
            "NetworkError",
        }
    ):
        return "retryable_transport"
    return "deterministic"


def _primitive_error(exc, request_kwargs):
    original = getattr(exc, "original_error", None)
    status = _http_status_of(original)
    error_code = _structured_error_code(exc, original)
    headers = getattr(getattr(original, "response", None), "headers", None)
    retry_after = None
    if headers is not None:
        raw = headers.get("retry-after-ms")
        try:
            retry_after = float(raw) / 1000.0 if raw is not None else None
        except (TypeError, ValueError):
            retry_after = None
        if retry_after is None:
            raw = headers.get("retry-after")
            try:
                retry_after = float(raw) if raw is not None else None
            except (TypeError, ValueError):
                retry_after = None
    return {
        "kind": "error",
        "error_class": type(exc).__name__,
        "cause_class": type(original).__name__ if original is not None else None,
        "error_code": error_code,
        "disposition": _error_disposition(exc, original, status, error_code),
        "provider": str(getattr(exc, "provider", "") or request_kwargs.get("_request_provider", "")),
        "model": str(getattr(exc, "model", "") or request_kwargs.get("model", "")),
        "task_id": getattr(exc, "task_id", None) or request_kwargs.get("task_id"),
        "http_status": int(status) if isinstance(status, int) else None,
        "retry_after": retry_after if retry_after is not None and retry_after >= 0 else None,
        "finish_reason": getattr(exc, "finish_reason", None),
    }


class _ChildPhaseWriter:
    """Writes one `P {json}` line per transport phase on the protocol stdout.

    The parent's reader thread turns these into the current phase shown to
    the player and recorded in the master log. A write failure means the
    parent is gone; the provider call itself is unaffected.
    """

    def __init__(self, protocol_stdout, started):
        self._out = protocol_stdout
        self._started = started
        self._lock = threading.Lock()

    def __call__(self, phase, detail=None):
        import json

        line = json.dumps(
            {
                "phase": str(phase),
                "t": round(time.monotonic() - self._started, 3),
                "detail": detail if isinstance(detail, (str, int, float)) else None,
            }
        )
        with self._lock:
            try:
                self._out.write(("P " + line + "\n").encode("ascii", "replace"))
                self._out.flush()
            except (OSError, ValueError):
                pass


class _HttpcoreTraceHandler(logging.Handler):
    """Maps httpcore's trace log lines to transport phases (observation only)."""

    def __init__(self, phase_emit):
        super().__init__(level=logging.DEBUG)
        self._emit = phase_emit

    def emit(self, record):
        try:
            message = record.getMessage()
        except Exception:
            return
        for event, phase in _HTTPCORE_PHASES:
            if event in message:
                self._emit(phase)
                return


def _child_main():
    """Private subprocess entry: provider call only, primitive IPC only."""
    request_kwargs = {}
    protocol_stdout = sys.stdout.buffer
    started = time.monotonic()
    phase = _ChildPhaseWriter(protocol_stdout, started)
    try:
        payload = sys.stdin.buffer.read()
        request = pickle.loads(payload)
        messages = request["messages"]
        request_kwargs = request["request_kwargs"]
        correlation = request["correlation"]
        phase("payload_read", len(payload))
        null_stream = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = null_stream
        sys.stderr = null_stream
        trace_logger = logging.getLogger("httpcore")
        trace_logger.setLevel(logging.DEBUG)
        trace_logger.addHandler(_HttpcoreTraceHandler(phase))

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from core.ai import api_client

        response = api_client.create_completion(
            messages=messages,
            _phase_emit=phase,
            **request_kwargs,
        )
        envelope = _success_envelope(response, request_kwargs)
        phase("done")
    except BaseException as exc:
        envelope = _primitive_error(exc, request_kwargs)
        correlation = locals().get("correlation", {})
        phase(
            "failed",
            "%s: %s" % (
                envelope.get("cause_class") or envelope.get("error_class"),
                str(exc).replace("\n", " "),
            ),
        )
    envelope["correlation"] = correlation
    try:
        body = pickle.dumps(envelope, protocol=pickle.HIGHEST_PROTOCOL)
        protocol_stdout.write(("E %d\n" % len(body)).encode("ascii"))
        protocol_stdout.write(body)
        protocol_stdout.flush()
        return 0
    except BaseException:
        return 2


class _GenerationReader(threading.Thread):
    """Owns the child's stdout for one generation.

    Consumes `P` phase lines into the shared state as they arrive and keeps
    the framed final envelope. EOF (the child exited or was reaped) ends it;
    the parent never blocks on this thread while the child lives.
    """

    def __init__(self, stream, started):
        super().__init__(name="live-provider-reader", daemon=True)
        self._stream = stream
        self._generation_started = started
        self._lock = threading.Lock()
        self.phases = {}
        self.current = "spawned"
        self.last_progress = None
        self.detail = None
        self.endpoint = None
        self.output = None
        self.finished = False

    def _record(self, line):
        import json

        try:
            event = json.loads(line)
            name = str(event.get("phase"))
            offset = float(event.get("t"))
        except (ValueError, TypeError, AttributeError):
            # Evidence loss only (a malformed frame); the envelope protocol
            # and the provider call are unaffected. Logged, not swallowed.
            _LOGGER.warning("LIVE_PROVIDER_PHASE_FRAME_UNREADABLE %r", line[:120])
            return
        with self._lock:
            if name == "endpoint":
                self.endpoint = event.get("detail")
                return
            self.phases.setdefault(name, offset)
            self.current = name
            self.detail = event.get("detail")
            if name in ("acknowledged", "working", "receiving"):
                self.last_progress = offset

    def snapshot(self):
        with self._lock:
            return {
                "phases": dict(self.phases),
                "current": self.current,
                "last_progress": self.last_progress,
                "detail": self.detail,
                "endpoint": self.endpoint,
            }

    def run(self):
        try:
            while True:
                line = self._stream.readline()
                if not line:
                    break
                if line.startswith(b"P "):
                    self._record(line[2:].decode("ascii", "replace"))
                elif line.startswith(b"E "):
                    try:
                        length = int(line[2:].strip())
                    except ValueError:
                        break
                    body = self._stream.read(length)
                    if len(body) == length:
                        self.output = body
                    break
        except (OSError, ValueError):
            pass
        finally:
            self.finished = True


def _emit_working(message):
    from core.managers.status_manager import status_manager

    status_manager.update_status(message, True)


def _close_process_streams(process):
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _terminate_process(process, reader=None):
    """Terminate, hard-kill if needed, wait, drain the reader, close handles.

    The child's stdout belongs to the generation reader, never to
    communicate(): once the child is dead the reader sees EOF and ends, and
    whatever final envelope it captured is returned.
    """
    try:
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        soft_deadline = time.monotonic() + 5.0
        while process.poll() is None and time.monotonic() < soft_deadline:
            try:
                process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                pass

        while process.poll() is None:
            try:
                process.kill()
            except OSError:
                if process.poll() is None:
                    time.sleep(0.05)
            try:
                process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                pass

        if reader is not None:
            reader.join()
            return reader.output
        return None
    finally:
        _close_process_streams(process)


def _feed_request(request_stdin, request_payload):
    """Deliver one generation's request on its own pipe, then close it.

    Written by its own thread on a pipe communicate() never sees:
    communicate(input=..., timeout=...) registers stdin for writing only on
    the call that carries `input`, so a 250 ms poll with the payload
    part-written (any request over the pipe buffer whose child has not
    drained it yet) left the remainder unsent forever (d3c4cbf9). The pipe
    and payload arrive as arguments, never through a closure the next
    generation could rebind (#428). The writer blocks only while the child
    drains; a dead child breaks the pipe and releases it.
    """
    try:
        request_stdin.write(request_payload)
    except (BrokenPipeError, OSError, ValueError):
        pass
    finally:
        try:
            request_stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass


def phase_status_line(provider_name, attempt, state, elapsed, generation_elapsed=None):
    """The player's wait line, rendered from the child's reported phase.

    One renderer for every caller (the level-up manager reuses it). The
    stopwatch is context, never the claim of activity; the claim is the
    phase the child actually reported and when the provider last did
    something (D-PROVIDER-LIVENESS-20260913). ``elapsed`` is the logical
    call's age (shown); ``generation_elapsed`` is this attempt's age, the
    clock the child's phase offsets are relative to.
    """
    seconds = max(1, int(elapsed))
    if generation_elapsed is None:
        generation_elapsed = elapsed
    shown = "%d min" % (seconds // 60) if seconds >= 120 else "%d s" % seconds
    prefix = "Attempt %d, %s: " % (attempt, shown)
    suffix = " Your turn is safe."
    if not state:
        return prefix + "starting a connection to %s..." % provider_name + suffix
    current = state.get("current")
    if current in ("spawned", "payload_read", "connecting"):
        body = "connecting to %s..." % provider_name
    elif current in ("connected", "secured"):
        body = "connected to %s; sending your request..." % provider_name
    elif current == "sent":
        waited = max(
            0, int(generation_elapsed - float(state["phases"].get("sent", 0.0)))
        )
        body = (
            "request delivered to %s; waiting for it to acknowledge (%d s)..."
            % (provider_name, waited)
        )
    elif current in ("acknowledged", "working"):
        since = state.get("last_progress")
        ago = max(0, int(generation_elapsed - float(since))) if since is not None else 0
        body = "%s is working on it (last activity %d s ago)..." % (
            provider_name, ago,
        )
    elif current == "receiving":
        body = "answer arriving from %s..." % provider_name
    elif current == "done":
        body = "answer received from %s; finishing..." % provider_name
    elif current == "failed":
        body = "%s connection failed; reconnecting..." % provider_name
    else:
        body = "waiting for %s..." % provider_name
    return prefix + body + suffix


def _safe_emit(emit, message):
    """Presentational status failure must not interrupt provider ownership."""
    try:
        emit(message)
    except Exception:
        pass


def _check_live_authority(scope, authority_check=None):
    """Check caller authority without acquiring a scope or filesystem lock.

    The optional callback must perform a non-waiting observation: False means
    superseded; OSError means unreadable, never evidence of supersession.
    """
    if scope is not None and scope.is_superseded():
        raise LiveProviderSuperseded("live player turn superseded")
    if authority_check is not None:
        current = authority_check()
        if current is False:
            raise LiveProviderSuperseded("live request authority superseded")
        if current is not True:
            raise OSError("Live request authority observation is unavailable")


def _interruptible_wait(seconds, scope, message, emit=None, authority_check=None):
    emit = emit if emit is not None else _emit_working
    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        try:
            _check_live_authority(scope, authority_check)
        except OSError:
            # Do not infer cancellation from an unreadable authority file.
            # The next generation cannot start until its own check succeeds.
            pass
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        rendered = message() if callable(message) else message
        _safe_emit(emit, rendered)
        time.sleep(min(_HEARTBEAT_SECONDS, remaining))


def _wait_for_live_authority(scope, authority_check=None):
    """#311: wait outside locks/provider calls without losing pending memory."""
    while True:
        try:
            _check_live_authority(scope, authority_check)
            return
        except OSError:
            _interruptible_wait(
                0.25, scope,
                "Checking the current adventure before recording companion memory...",
                authority_check=authority_check,
            )


def _delay_for_error(envelope, failure_count):
    retry_after = envelope.get("retry_after")
    if isinstance(retry_after, (int, float)) and retry_after >= 0:
        return float(retry_after)
    status = envelope.get("http_status")
    if isinstance(status, int) and 400 <= status < 500:
        return _PERMANENT_ERROR_SECONDS
    # Exponent capped at 4: 0.5 * 2**4 already equals _MAX_BACKOFF_SECONDS,
    # and an unbounded count overflows float at 2**1024 (#284 review C3-1).
    base = min(
        _MAX_BACKOFF_SECONDS,
        0.5 * (2 ** max(0, min(failure_count - 1, 4))),
    )
    return random.uniform(base * 0.75, base)


def _synthesized_envelope(error_class, task_id, request_kwargs, operation_id,
                          generation):
    """Envelope for a generation the parent reaped without a child reply.

    The request may already have reached the provider, so the generation is
    marked billing=possible for the master log (#284 cost visibility).
    """
    return {
        "kind": "error",
        "error_class": error_class,
        "cause_class": None,
        "error_code": None,
        "disposition": "retryable_transport",
        "provider": str(request_kwargs.get("_request_provider", "") or ""),
        "model": str(request_kwargs.get("model", "") or ""),
        "task_id": task_id,
        "http_status": None,
        "retry_after": None,
        "billing": "possible",
        "correlation": {
            "operation_id": operation_id,
            "generation": generation,
        },
    }


def _log_generation(task_id, frozen_messages, envelope, started):
    """Evidence only: one master-log line per terminal envelope (#284)."""
    try:
        from utils.api_logger import log_live_provider_envelope

        sent = envelope.get("sent_messages") if isinstance(envelope, dict) else None
        log_live_provider_envelope(
            task_id,
            sent if isinstance(sent, list) else frozen_messages,
            envelope,
            latency_seconds=time.monotonic() - started,
        )
    except Exception:
        # Evidence loss only; api_logger counts its own append failures.
        pass


def _reconstruct_response(envelope):
    from core.ai.api_client import _NormalizedResponse

    response = _NormalizedResponse(
        content=envelope["content"],
        usage_dict=envelope["usage"],
        model=envelope.get("model", ""),
        response_id=envelope.get("response_id", ""),
        finish_reason=envelope.get("finish_reason", "unknown"),
        provider=envelope.get("provider", ""),
        task_id=envelope.get("task_id"),
        raw_response={
            "liveProviderCorrelation": dict(envelope["correlation"]),
            "liveProviderPhases": dict(envelope.get("phases") or {}),
        },
        usage_invocation_id=envelope.get("usage_invocation_id"),
    )
    sent = envelope.get("sent_messages")
    if isinstance(sent, list):
        response.sent_messages = sent
    return response


def call_live_provider(
    task_id,
    messages,
    request_kwargs,
    *,
    policy="required",
    scope=None,
    status_emit=None,
    authority_check=None,
):
    """Run one frozen selected request under its required/advisory policy.

    ``scope`` lets a detached caller (the off-thread startup welcome) supply
    its own cancellable LiveTurnScope instead of the global player-turn
    singleton; existing callers pass nothing and behave byte-identically.
    ``status_emit`` routes liveness/heartbeat messages to a caller-owned sink
    (the non-input-locking welcome status channel) instead of the global
    input-locking status manager.
    ``authority_check`` optionally observes the completion epoch in the parent,
    outside locks. It is never serialized into the provider request.
    """
    if task_id not in _LIVE_TASK_IDS:
        raise ValueError("task is outside the reviewed live provider allowlist")
    if policy not in {"required", "advisory"}:
        raise ValueError("live provider policy must be required or advisory")
    expected_policy = "required" if task_id in _REQUIRED_TASK_IDS else "advisory"
    if policy != expected_policy:
        raise ValueError(
            "%s is classified %s, not %s" % (task_id, expected_policy, policy)
        )
    scope = scope if scope is not None else get_live_provider_scope()
    emit = status_emit if status_emit is not None else _emit_working
    completion_required = bool(
        isinstance(scope, AdvisoryProviderScope)
        and scope.completion_required
    )
    if completion_required and task_id == "T105":
        # The request-local batch owns player-facing progress. Per-child transport
        # details remain developer-only so parallel workers cannot race narration.
        emit = lambda _message: None
    operation_id = scope.operation_id if scope is not None else str(uuid4())
    frozen_messages = copy.deepcopy(messages)
    frozen_kwargs = copy.deepcopy(request_kwargs)
    wizard_task = task_id in _WIZARD_TASK_IDS
    # The per-generation transport deadline is the REISSUE TRIGGER, never a
    # terminal (#193 B2-iii). It is set for every provider; each adapter
    # translates it (OpenAI-compatible: request option with SDK retries
    # zeroed; Gemini: http_options timeout). The task-level exclusion for
    # plain-advisory T105/T112 is unchanged (D-VS-3).
    level_up_task = task_id in _LEVEL_UP_TASK_IDS
    if level_up_task:
        frozen_kwargs["timeout"] = _LEVEL_UP_BACKSTOP_SECONDS
    elif completion_required:
        frozen_kwargs["timeout"] = _WATCHDOG_SECONDS
    elif wizard_task and frozen_kwargs.get("_request_provider") == "openai":
        import httpx

        frozen_kwargs["timeout"] = httpx.Timeout(
            _WATCHDOG_SECONDS,
            read=_WIZARD_READ_INACTIVITY_SECONDS,
        )
    elif task_id not in _NO_WATCHDOG_ADVISORY_TASK_IDS:
        frozen_kwargs["timeout"] = _WATCHDOG_SECONDS
    failure_count = 0
    logical_started = time.monotonic()
    notices_shown = set()
    player_turn = scope is not None and scope is get_live_turn_scope()

    from utils.provider_errors import provider_display_name

    provider_name = provider_display_name(frozen_kwargs.get("_request_provider"))
    current_reader = {"reader": None, "started": None}

    def turn_heartbeat(_generation_number=None):
        # Attempt = this call's own physical attempts (failure_count + 1), not
        # the scope generation, which other tasks in the turn also consume.
        # The line names the transport phase the child has actually reported
        # (D-PROVIDER-LIVENESS: never a bare stopwatch as proof of activity).
        attempt = failure_count + 1
        reader = current_reader["reader"]
        state = reader.snapshot() if reader is not None else None
        now = time.monotonic()
        generation_elapsed = (
            now - current_reader["started"]
            if current_reader["started"] is not None else 0.0
        )
        return phase_status_line(
            provider_name, attempt, state, now - logical_started,
            generation_elapsed,
        )

    def notify_player_once(key, text):
        """One system-channel card per class per turn (never the status line)."""
        if not player_turn or completion_required or key in notices_shown:
            return
        notices_shown.add(key)

        def deliver(_message):
            from web.shared_state import emit_player_output

            emit_player_output(
                {"type": "narration", "channel": "system", "content": text}
            )

        _safe_emit(deliver, text)

    def wizard_heartbeat():
        elapsed = max(1, int(time.monotonic() - logical_started))
        return "Still working on character setup (%d seconds elapsed)..." % elapsed

    while True:
        try:
            _check_live_authority(scope, authority_check)
        except OSError:
            failure_count += 1
            _interruptible_wait(
                _delay_for_error({}, failure_count), scope,
                "Still working; checking the current adventure...", emit,
                authority_check,
            )
            continue
        generation = (
            scope.next_generation() if scope is not None else failure_count + 1
        )
        request_payload = pickle.dumps(
            {
                "messages": frozen_messages,
                "request_kwargs": frozen_kwargs,
                "correlation": {
                    "operation_id": operation_id,
                    "generation": generation,
                },
            },
            protocol=pickle.HIGHEST_PROTOCOL,
        )
        helper_path = os.path.abspath(__file__)
        try:
            process = subprocess.Popen(
                [sys.executable, helper_path, "--provider-child"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=os.getcwd(),
            )
        except BaseException:
            _log_generation(
                task_id,
                frozen_messages,
                _synthesized_envelope(
                    "process_setup_unavailable",
                    task_id,
                    frozen_kwargs,
                    operation_id,
                    generation,
                ),
                time.monotonic(),
            )
            if policy == "advisory" and not completion_required:
                raise LiveProviderUnavailable(
                    task_id, {"error_class": "process_setup_unavailable"}
                )
            failure_count += 1
            _interruptible_wait(
                _delay_for_error({}, failure_count),
                scope,
                wizard_heartbeat if wizard_task else (
                    "Still working; preparing a fresh provider connection..."
                ),
                emit,
                authority_check,
            )
            continue

        started = time.monotonic()
        generation_limit = (
            _LEVEL_UP_BACKSTOP_SECONDS
            if level_up_task
            else _WATCHDOG_SECONDS
            if completion_required
            else (
                None
                if task_id in _NO_WATCHDOG_ADVISORY_TASK_IDS
                else (_WIZARD_BACKSTOP_SECONDS if wizard_task else _WATCHDOG_SECONDS)
            )
        )
        # The request is written by its own thread on a pipe that communicate()
        # never sees. communicate(input=..., timeout=...) registers stdin for
        # writing only on the call that carries `input`; once the 250 ms poll
        # below expires with the payload part-written (any request over the
        # pipe buffer whose child has not drained it yet), every later
        # communicate(None) leaves the remainder unsent and stdin open, so the
        # child waits on stdin and the parent waits on stdout forever.
        # Observed 2026-09-13 on a fresh-install T092 (~80 KB request): the
        # wizard heartbeat ran indefinitely with no request ever reaching the
        # provider. The writer blocks only while the child drains; a dead child
        # breaks the pipe and releases it.
        # The writer is bound to THIS generation's pipe and payload by
        # argument and joined before the next generation starts (#428): a
        # late-waking writer can no longer close a newer child's stdin.
        request_stdin = process.stdin
        process.stdin = None
        writer = threading.Thread(
            target=_feed_request,
            args=(request_stdin, request_payload),
            name="live-provider-request",
            daemon=True,
        )
        writer.start()
        # The child's stdout carries phase lines and then the framed final
        # envelope; one reader thread per generation owns it (#409 Task 1).
        reader = _GenerationReader(process.stdout, started)
        process.stdout = None
        reader.start()
        current_reader["reader"] = reader
        current_reader["started"] = started
        next_heartbeat = started + _HEARTBEAT_SECONDS
        envelope = None
        superseded = False
        output = None
        backstop_exhausted = False
        ack_backstop_exhausted = False
        authority_unavailable = False
        try:
            while True:
                try:
                    _check_live_authority(scope, authority_check)
                except LiveProviderSuperseded:
                    superseded = True
                    break
                except OSError:
                    authority_unavailable = True
                    break
                if process.poll() is not None and reader.finished:
                    output = reader.output
                    break
                state = reader.snapshot()
                now = time.monotonic()
                if (
                    state["endpoint"] in _ACK_ENDPOINTS
                    and state["current"] in _PRE_ACK_PHASES
                    and now - started - state["phases"][state["current"]]
                    >= _ACK_BACKSTOP_SECONDS
                ):
                    ack_backstop_exhausted = True
                    break
                # Once the provider has acknowledged the request and reported
                # progress, the generation backstop measures INACTIVITY since
                # the last progress event, never total time: a request that
                # keeps emitting events is never killed for being long
                # (D-PROVIDER-LIVENESS clarification; review finding 1).
                # Endpoints without an acknowledgment signal keep today's
                # behaviour (bound from generation start), a documented
                # limitation, not a healthy signal.
                if state["last_progress"] is not None:
                    idle_reference = started + float(state["last_progress"])
                else:
                    idle_reference = started
                if (
                    generation_limit is not None
                    and now - idle_reference >= generation_limit
                ):
                    backstop_exhausted = True
                    break
                time.sleep(0.25)
                if time.monotonic() >= next_heartbeat:
                    _safe_emit(
                        emit,
                        wizard_heartbeat() if wizard_task else (
                            turn_heartbeat(generation)
                        ),
                    )
                    next_heartbeat = time.monotonic() + _HEARTBEAT_SECONDS
        finally:
            if process.poll() is None:
                terminated_output = _terminate_process(process, reader)
                if output is None:
                    output = terminated_output
            else:
                reader.join()
                if output is None:
                    output = reader.output
                _close_process_streams(process)
            writer.join()
        phase_state = reader.snapshot()
        if superseded:
            raise LiveProviderSuperseded("live player turn superseded")
        try:
            _check_live_authority(scope, authority_check)
        except OSError:
            authority_unavailable = True
        if output and not authority_unavailable:
            try:
                envelope = pickle.loads(output)
            except (EOFError, pickle.PickleError, ValueError, TypeError):
                envelope = None
        expected_correlation = {
            "operation_id": operation_id,
            "generation": generation,
        }
        correlation_accepted = (
            isinstance(envelope, dict)
            and envelope.get("correlation") == expected_correlation
        )
        valid_envelope = correlation_accepted and (
            (
                envelope.get("kind") == "success"
                and isinstance(envelope.get("content"), str)
                and bool(envelope["content"].strip())
                and isinstance(envelope.get("usage"), dict)
            )
            or (
                envelope.get("kind") == "error"
                and envelope.get("disposition") in (
                    "retryable_transport", "retryable_http", "empty", "deterministic",
                )
            )
        )
        if not valid_envelope:
            envelope = _synthesized_envelope(
                (
                    "ProviderChildGenerationBackstop"
                    if backstop_exhausted
                    else "ProviderChildAcknowledgeBackstop"
                    if ack_backstop_exhausted
                    else "ProviderChildUnavailable"
                ),
                task_id,
                frozen_kwargs,
                operation_id,
                generation,
            )
        if isinstance(envelope, dict):
            envelope["correlation_accepted"] = correlation_accepted
            envelope["phases"] = phase_state["phases"]
            envelope["last_phase"] = phase_state["current"]
            envelope["last_progress"] = phase_state["last_progress"]
            # Every error or reaped generation of every task is evidence
            # (#284 F6); success rows keep the existing gate because those
            # callers already log their own successes.
            if (
                envelope.get("kind") != "success"
                or not correlation_accepted
                or wizard_task
                or task_id in _SUCCESS_LOG_TASK_IDS
            ):
                _log_generation(task_id, frozen_messages, envelope, started)
        if (
            isinstance(envelope, dict)
            and envelope.get("kind") == "success"
            and correlation_accepted
        ):
            response = _reconstruct_response(envelope)
            try:
                _check_live_authority(scope, authority_check)
            except OSError:
                failure_count += 1
                _interruptible_wait(
                    _delay_for_error({}, failure_count), scope,
                    "Still working; checking the current adventure...", emit,
                    authority_check,
                )
                continue
            return response

        failure_count += 1
        envelope = envelope if isinstance(envelope, dict) else {}
        if (
            policy == "advisory"
            and completion_required
            and envelope.get("disposition") in {
                "retryable_http",
                "retryable_transport",
            }
        ):
            _LOGGER.warning(
                "LIVE_PROVIDER_REISSUE task=%s class=%s status=%s",
                task_id,
                envelope.get("error_class", "transport_unavailable"),
                envelope.get("http_status"),
            )
            _interruptible_wait(
                _delay_for_error(envelope, failure_count),
                scope,
                "",
                emit,
                authority_check,
            )
            continue
        if policy == "advisory":
            raise LiveProviderUnavailable(task_id, envelope)
        if wizard_task:
            disposition = envelope.get("disposition")
            if disposition not in {
                "empty",
                "retryable_http",
                "retryable_transport",
            }:
                raise LiveProviderCompletedError(task_id, envelope)
        error_class = envelope.get("error_class", "transport_unavailable")
        if not wizard_task:
            # A completed deterministic error (HTTP 400/401/403, a schema
            # rejection) cannot heal through a fresh connection: reissuing it
            # every ~60s kept the turn "in progress" forever (#240). Hand it
            # to the caller now. Transport/empty failures instead retain the
            # same logical call until recovery or genuine supersession.
            disposition = envelope.get("disposition")
            if disposition not in {"retryable_http", "retryable_transport", "empty"}:
                raise LiveProviderCompletedError(task_id, envelope)
            try:
                # Diagnostics stay in the debug log; in headless the console
                # warning handler landed in the narration stream (#233).
                from utils.enhanced_logger import debug

                debug(
                    "LIVE_PROVIDER_REISSUE task=%s class=%s status=%s "
                    "generation=%d billing=%s"
                    % (task_id, error_class, envelope.get("http_status"),
                       generation, envelope.get("billing") or "n/a"),
                    category="ai_routing",
                )
            except Exception:
                pass
            from utils.provider_errors import player_exits_notice, reissue_notice

            reason = reissue_notice(
                envelope.get("disposition"),
                envelope.get("http_status"),
                frozen_kwargs.get("_request_provider"),
                envelope.get("error_code"),
                last_phase=envelope.get("last_phase"),
            )
            notify_player_once("exits", player_exits_notice())
            notify_player_once(
                "class:%s" % envelope.get("disposition"), reason
            )
            _safe_emit(emit, "%s %s" % (turn_heartbeat(generation), reason))
        _interruptible_wait(
            _delay_for_error(envelope, failure_count),
            scope,
            wizard_heartbeat if wizard_task else (
                lambda: turn_heartbeat(generation)
            ),
            emit,
            authority_check,
        )


if __name__ == "__main__":
    sys.exit(_child_main())
