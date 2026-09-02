"""Private cancellable transport for the live pre-mutation turn seam.

This module owns no gameplay state.  It runs one already-frozen provider
request in one spawned child, returns one primitive response envelope, and
fully reaps that child before returning or reissuing.
"""

import copy
import os
import pickle
import random
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from uuid import uuid4


_REQUIRED_TASK_IDS = frozenset(
    {
        "T014",
        "T015",
        "T016",
        "T021",
        "T035",
        "T049",
        "T065",
        "T067",
        "T077",
        "T078",
        "T079",
        "T092",
        "T093",
    }
)
_ADVISORY_TASK_IDS = frozenset(
    {
        "T013",
        "T018",
        "T019",
        "T027",
        "T038",
        "T039",
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
    }
)
_LIVE_TASK_IDS = _REQUIRED_TASK_IDS | _ADVISORY_TASK_IDS
_HEARTBEAT_SECONDS = 10.0
_WATCHDOG_SECONDS = 600.0
_WIZARD_READ_INACTIVITY_SECONDS = 40.0
_WIZARD_BACKSTOP_SECONDS = 180.0
_WIZARD_TASK_IDS = frozenset({"T092", "T093"})
_MAX_BACKOFF_SECONDS = 8.0
_PERMANENT_ERROR_SECONDS = 60.0


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

    Raised for a deterministic error on the first attempt and for a retryable
    one once _NON_WIZARD_MAX_FAILURES attempts have not healed it. The caller
    (the T067 turn loop) classifies it and tells the player; the child never
    reissues a completed error forever again. http_status is exposed so the
    caller's classifier can read it like any provider exception.
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
            accepted = self.supersession is None
            if self.supersession is None:
                self.supersession = {
                    "kind": str(kind),
                    "operation_id": operation_id or str(uuid4()),
                }
            result = dict(self.supersession)
            result["accepted"] = accepted
            return result

    def is_superseded(self):
        with self.lock:
            return self.supersession is not None

_scope_guard = threading.RLock()
_active_scope = None


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


def live_provider_policy(task_id):
    """Return the reviewed policy only while a live player-turn scope exists."""
    if get_live_turn_scope() is None:
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
        if _active_scope is scope:
            with scope.lock:
                scope.controls_open = False
            scope.phase = "QUIESCENT"
            scope.quiescent.set()
            _active_scope = None


def request_live_turn_supersession(kind, operation_id=None):
    scope = get_live_turn_scope()
    if scope is None:
        return None
    result = scope.request_supersession(kind, operation_id)
    if result.get("accepted"):
        from core.combat.invocation import supersede_invocations
        from core.managers.campaign_manager import _party_module_transition_lock

        # Serialize the fence with combat's mutation authority. A write that
        # already owns the transition lock completes before acceptance is
        # returned; every later write observes the superseded invocation.
        with _party_module_transition_lock():
            supersede_invocations(kind)
    return result


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


def queue_live_save(execute, complete, operation_id=None, scope=None):
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
    }
    with scope.lock:
        if not scope.controls_open:
            return None
        for pending in scope.pending_saves:
            if pending["operation_id"] == requested_id:
                return requested_id
        scope.pending_saves.append(record)
    return record["operation_id"]


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
        if existing is not None and not (
            existing.get("kind") == "player_acted"
            and str(kind) in ("restore", "reset")
        ):
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
    while True:
        with scope.lock:
            if not scope.pending_saves:
                if seal:
                    scope.controls_open = False
                return
            record = scope.pending_saves.popleft()
        try:
            outcome = record["execute"]()
        except BaseException as exc:
            outcome = (False, "%s: %s" % (type(exc).__name__, exc))
        try:
            record["complete"](outcome)
        except Exception:
            # Completion notification is presentational (a disconnected web
            # client makes socketio.emit raise); it must never stop the
            # drain or block the terminal's quiescence guarantee.
            pass


def finish_live_turn_scope(scope):
    """Drain accepted saves and publish game-thread quiescence."""
    drain_live_saves(scope, seal=True)
    close_live_turn_scope(scope)


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
    usage = getattr(response, "usage", None)
    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
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
    }


def _error_disposition(exc, original, status):
    """Classify from exception types/status only; provider prose is never authority."""
    if type(exc).__name__ == "ProviderEmptyResponse":
        return "empty"
    if status in {408, 409, 429} or (
        isinstance(status, int) and 500 <= status < 600
    ):
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
    status = getattr(original, "status_code", None)
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
        "disposition": _error_disposition(exc, original, status),
        "provider": str(getattr(exc, "provider", "") or request_kwargs.get("_request_provider", "")),
        "model": str(getattr(exc, "model", "") or request_kwargs.get("model", "")),
        "task_id": getattr(exc, "task_id", None) or request_kwargs.get("task_id"),
        "http_status": int(status) if isinstance(status, int) else None,
        "retry_after": retry_after if retry_after is not None and retry_after >= 0 else None,
        "finish_reason": getattr(exc, "finish_reason", None),
    }


def _child_main():
    """Private subprocess entry: provider call only, primitive IPC only."""
    request_kwargs = {}
    protocol_stdout = sys.stdout.buffer
    try:
        payload = sys.stdin.buffer.read()
        request = pickle.loads(payload)
        messages = request["messages"]
        request_kwargs = request["request_kwargs"]
        correlation = request["correlation"]
        null_stream = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = null_stream
        sys.stderr = null_stream

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from core.ai import api_client

        response = api_client.create_completion(
            messages=messages,
            **request_kwargs,
        )
        envelope = _success_envelope(response, request_kwargs)
    except BaseException as exc:
        envelope = _primitive_error(exc, request_kwargs)
        correlation = locals().get("correlation", {})
    envelope["correlation"] = correlation
    try:
        protocol_stdout.write(pickle.dumps(envelope, protocol=pickle.HIGHEST_PROTOCOL))
        protocol_stdout.flush()
        return 0
    except BaseException:
        return 2


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


def _terminate_process(process):
    """Terminate, hard-kill if needed, wait, and close every local handle."""
    try:
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        soft_deadline = time.monotonic() + 5.0
        while process.poll() is None and time.monotonic() < soft_deadline:
            try:
                output, _ = process.communicate(timeout=0.25)
                return output
            except subprocess.TimeoutExpired:
                pass

        while process.poll() is None:
            try:
                process.kill()
            except OSError:
                if process.poll() is None:
                    time.sleep(0.05)
            try:
                output, _ = process.communicate(timeout=0.25)
                return output
            except subprocess.TimeoutExpired:
                pass

        output, _ = process.communicate()
        return output
    finally:
        _close_process_streams(process)


def _safe_emit(emit, message):
    """Presentational status failure must not interrupt provider ownership."""
    try:
        emit(message)
    except Exception:
        pass


def _interruptible_wait(seconds, scope, message, emit=None):
    emit = emit if emit is not None else _emit_working
    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        if scope is not None and scope.is_superseded():
            raise LiveProviderSuperseded("live player turn superseded")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        rendered = message() if callable(message) else message
        _safe_emit(emit, rendered)
        time.sleep(min(_HEARTBEAT_SECONDS, remaining))


# Non-wizard reissue budget per call: after this many failed attempts the
# child hands the completed error to the caller instead of looping (#240).
_NON_WIZARD_MAX_FAILURES = 6


def _delay_for_error(envelope, failure_count):
    retry_after = envelope.get("retry_after")
    if isinstance(retry_after, (int, float)) and retry_after >= 0:
        return float(retry_after)
    status = envelope.get("http_status")
    if isinstance(status, int) and 400 <= status < 500:
        return _PERMANENT_ERROR_SECONDS
    base = min(_MAX_BACKOFF_SECONDS, 0.5 * (2 ** max(0, failure_count - 1)))
    return random.uniform(base * 0.75, base)


def _reconstruct_response(envelope):
    from core.ai.api_client import _NormalizedResponse

    return _NormalizedResponse(
        content=envelope["content"],
        usage_dict=envelope["usage"],
        model=envelope.get("model", ""),
        response_id=envelope.get("response_id", ""),
        finish_reason=envelope.get("finish_reason", "unknown"),
        provider=envelope.get("provider", ""),
        task_id=envelope.get("task_id"),
        raw_response=None,
        usage_invocation_id=envelope.get("usage_invocation_id"),
    )


def call_live_provider(
    task_id,
    messages,
    request_kwargs,
    *,
    policy="required",
    scope=None,
    status_emit=None,
):
    """Run one frozen selected request under its required/advisory policy.

    ``scope`` lets a detached caller (the off-thread startup welcome) supply
    its own cancellable LiveTurnScope instead of the global player-turn
    singleton; existing callers pass nothing and behave byte-identically.
    ``status_emit`` routes liveness/heartbeat messages to a caller-owned sink
    (the non-input-locking welcome status channel) instead of the global
    input-locking status manager.
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
    scope = scope if scope is not None else get_live_turn_scope()
    emit = status_emit if status_emit is not None else _emit_working
    operation_id = scope.operation_id if scope is not None else str(uuid4())
    frozen_messages = copy.deepcopy(messages)
    frozen_kwargs = copy.deepcopy(request_kwargs)
    wizard_task = task_id in _WIZARD_TASK_IDS
    if wizard_task and frozen_kwargs.get("_request_provider") == "openai":
        import httpx

        frozen_kwargs["timeout"] = httpx.Timeout(
            _WATCHDOG_SECONDS,
            read=_WIZARD_READ_INACTIVITY_SECONDS,
        )
    elif frozen_kwargs.get("_request_provider") in {
        "openai",
        "legacy",
        "lmstudio",
    }:
        frozen_kwargs["timeout"] = _WATCHDOG_SECONDS
    failure_count = 0
    empty_count = 0
    logical_started = time.monotonic()

    def wizard_heartbeat():
        elapsed = max(1, int(time.monotonic() - logical_started))
        return "Still working on character setup (%d seconds elapsed)..." % elapsed

    while True:
        if scope is not None and scope.is_superseded():
            raise LiveProviderSuperseded("live player turn superseded")
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
            if policy == "advisory":
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
            )
            continue

        started = time.monotonic()
        generation_limit = (
            _WIZARD_BACKSTOP_SECONDS if wizard_task else _WATCHDOG_SECONDS
        )
        next_heartbeat = started + _HEARTBEAT_SECONDS
        envelope = None
        superseded = False
        output = None
        first_communicate = True
        backstop_exhausted = False
        try:
            while time.monotonic() - started < generation_limit:
                if scope is not None and scope.is_superseded():
                    superseded = True
                    break
                try:
                    output, _ = process.communicate(
                        input=request_payload if first_communicate else None,
                        timeout=0.25,
                    )
                    break
                except subprocess.TimeoutExpired:
                    first_communicate = False
                if time.monotonic() >= next_heartbeat:
                    _safe_emit(
                        emit,
                        wizard_heartbeat() if wizard_task else (
                            "Still working on your adventure..."
                        ),
                    )
                    next_heartbeat = time.monotonic() + _HEARTBEAT_SECONDS
            else:
                backstop_exhausted = True
        finally:
            if process.poll() is None:
                terminated_output = _terminate_process(process)
                if output is None:
                    output = terminated_output
            else:
                _close_process_streams(process)
        if superseded:
            raise LiveProviderSuperseded("live player turn superseded")
        if output:
            try:
                envelope = pickle.loads(output)
            except (EOFError, pickle.PickleError, ValueError, TypeError):
                envelope = None
        if wizard_task and not isinstance(envelope, dict):
            envelope = {
                "kind": "error",
                "error_class": (
                    "WizardGenerationBackstop"
                    if backstop_exhausted
                    else "ProviderChildUnavailable"
                ),
                "cause_class": None,
                "disposition": "retryable_transport",
                "http_status": None,
                "retry_after": None,
            }
        expected_correlation = {
            "operation_id": operation_id,
            "generation": generation,
        }
        if (
            isinstance(envelope, dict)
            and envelope.get("kind") == "success"
            and envelope.get("correlation") == expected_correlation
        ):
            return _reconstruct_response(envelope)

        failure_count += 1
        envelope = envelope if isinstance(envelope, dict) else {}
        if policy == "advisory":
            raise LiveProviderUnavailable(task_id, envelope)
        if wizard_task:
            disposition = envelope.get("disposition")
            if disposition == "empty":
                empty_count += 1
                if task_id == "T093" and empty_count >= 3:
                    raise LiveProviderCompletedError(task_id, envelope)
            elif disposition not in {
                "retryable_http",
                "retryable_transport",
            }:
                raise LiveProviderCompletedError(task_id, envelope)
        error_class = envelope.get("error_class", "transport_unavailable")
        if not wizard_task:
            # A completed deterministic error (HTTP 400/401/403, a schema
            # rejection) cannot heal through a fresh connection: reissuing it
            # every ~60s kept the turn "in progress" forever (#240). Hand it
            # to the caller now. Retryable and empty results get a bounded
            # number of attempts here; the caller's own retry policy decides
            # what to do after that.
            disposition = envelope.get("disposition")
            if disposition not in {"retryable_http", "retryable_transport", "empty"}:
                raise LiveProviderCompletedError(task_id, envelope)
            if failure_count >= _NON_WIZARD_MAX_FAILURES:
                raise LiveProviderCompletedError(task_id, envelope)
            try:
                from utils.enhanced_logger import warning

                warning(
                    "LIVE_PROVIDER_REISSUE task=%s class=%s status=%s "
                    "remote_execution=unknown usage=unknown cost=unknown"
                    % (task_id, error_class, envelope.get("http_status")),
                    category="ai_routing",
                )
            except Exception:
                pass
            _safe_emit(
                emit,
                "The provider connection needs another attempt; your turn is safe "
                "and still in progress.",
            )
        _interruptible_wait(
            _delay_for_error(envelope, failure_count),
            scope,
            wizard_heartbeat if wizard_task else (
                "Still retrying the provider connection (%s)..." % error_class
            ),
            emit,
        )


if __name__ == "__main__":
    sys.exit(_child_main())
