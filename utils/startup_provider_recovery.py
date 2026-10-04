"""Startup configuration handback; no credentials or provider work are stored."""

import threading
import time

_condition = threading.Condition()
_selection_revision = 0
_provider_revisions = {}


def configuration_revision(provider):
    with _condition:
        return (_selection_revision, _provider_revisions.get(provider, 0))


def notify_configuration_saved(provider=None):
    """A successful Settings save deliberately retries retained startup work.

    A same-value save also counts: credit/account permissions may have changed
    remotely. Other providers' credential saves cannot retry this request.
    """
    global _selection_revision
    with _condition:
        if provider is None:
            _selection_revision += 1
        else:
            _provider_revisions[provider] = _provider_revisions.get(provider, 0) + 1
        _condition.notify_all()


def configuration_required_message(exc):
    """Classify only completed structured HTTP status, never provider prose."""
    status = getattr(exc, "http_status", None)
    if status == 401:
        reason = "The AI provider rejected the API key (HTTP 401). Check the key and endpoint"
    elif status == 403:
        reason = "The AI provider denied access (HTTP 403). Check the key, model access and account permissions"
    elif status == 402:
        reason = "The AI provider requires payment or credits (HTTP 402). Check the account balance and billing"
    else:
        return None
    return (reason + ". Open Settings and save the provider configuration to retry. "
            "Your setup choices are retained. Load, Reset or Exit can stop setup.")


def wait_for_configuration(provider, revision, scope, message, emit):
    """Keep the exact scope alive, without automatic POSTs or holding UI locks."""
    from utils.capture.live_provider_call import (
        LiveProviderSuperseded, drain_live_saves, _safe_emit,
    )

    next_status = 0.0
    while True:
        if scope.is_superseded():
            raise LiveProviderSuperseded("startup configuration wait superseded")
        drain_live_saves(scope)
        now = time.monotonic()
        if now >= next_status:
            _safe_emit(emit, message)
            next_status = now + 10.0
        with _condition:
            current = (_selection_revision, _provider_revisions.get(provider, 0))
            if current != revision:
                break
            _condition.wait(timeout=0.1)
    if scope.is_superseded():
        raise LiveProviderSuperseded("startup configuration retry superseded")
