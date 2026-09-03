"""Provider error classification and retry policy for the T067 turn loop.

Stdlib only, importable without the game runtime, so the policy can be unit
tested and shared by every provider call site. main.py re-exports these names.
"""

# ---------------------------------------------------------------------------
# Provider error classification
# ---------------------------------------------------------------------------
# The game runs on the player's own provider key, so a credential or billing
# failure is the player's to fix. Retrying it five times and then reporting
# "rephrase your action" hides the only fact that would let them fix it, so
# every provider call site can classify the failure here and surface the
# result to the player.

# Backoff for the failure classes where another attempt can actually succeed.
PROVIDER_RETRY_BASE_DELAY = 1.0
PROVIDER_RETRY_MAX_DELAY = 16.0


def _provider_error_chain(exc):
    """Yield exc and the provider errors it wraps (api_client wraps them)."""
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        nested = getattr(current, "original_error", None)
        if nested is None:
            nested = getattr(current, "__cause__", None)
        current = nested


def _provider_error_status(exc):
    """Best-effort HTTP status for a provider exception, or None."""
    envelope = getattr(exc, "envelope", None)
    if isinstance(envelope, dict) and isinstance(envelope.get("http_status"), int):
        return envelope["http_status"]
    for attribute in ("status_code", "http_status", "status"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    if isinstance(value, int):
        return value
    return None


def _provider_error_codes(exc):
    """Collect provider error code/type strings from a provider exception."""
    codes = []
    envelope = getattr(exc, "envelope", None)
    if isinstance(envelope, dict):
        # A live-provider child envelope (utils/capture/live_provider_call):
        # the wrapped exception class names carry the provider's verdict.
        for key in ("error_class", "cause_class", "disposition"):
            value = envelope.get(key)
            if isinstance(value, str):
                codes.append(value.lower())
    for attribute in ("code", "type"):
        value = getattr(exc, attribute, None)
        if isinstance(value, str):
            codes.append(value.lower())
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("error")
        if not isinstance(detail, dict):
            detail = body
        for key in ("code", "type", "status"):
            value = detail.get(key)
            if isinstance(value, str):
                codes.append(value.lower())
    return codes


def classify_provider_error(exc):
    """Classify a provider exception for retry policy and player messaging.

    Returns a dict with:
      category       - stable slug for logs
      retryable      - False when another attempt cannot possibly succeed
      player_message - text to show the player when the turn fails, or None
                       for unclassified errors (which keep the existing safe
                       failure message)
      retry_notice   - text to show the player before backing off, or None
    """
    status = None
    codes = []
    names = []
    texts = []
    for item in _provider_error_chain(exc):
        if status is None:
            status = _provider_error_status(item)
        names.append(type(item).__name__.lower())
        codes.extend(_provider_error_codes(item))
        texts.append(str(item).lower())
    code_blob = " ".join(codes)
    name_blob = " ".join(names)
    text_blob = " ".join(texts)

    def matches(*needles):
        return any(
            needle in code_blob or needle in text_blob for needle in needles
        )

    # Out of credit arrives as a 429, exactly like a rate limit, but no number
    # of retries will pay the bill -- the error code separates them, not the
    # status.
    if matches(
        "insufficient_quota",
        "insufficient_credit",
        "billing_hard_limit_reached",
        "exceeded your current quota",
        "check your plan and billing",
    ):
        return {
            "category": "insufficient_quota",
            "retryable": False,
            "player_message": (
                "The AI provider refused the request because your provider "
                "account is out of credit. Nothing in your game was changed. "
                "Add credit to your provider account, then try that action "
                "again."
            ),
            "retry_notice": None,
        }

    if (
        status == 401
        or "authenticationerror" in name_blob
        or matches(
            "invalid_api_key",
            "invalid_authentication",
            "incorrect api key",
            "unauthenticated",
        )
    ):
        return {
            "category": "authentication_failed",
            "retryable": False,
            "player_message": (
                "The AI provider rejected your API key. Nothing in your game "
                "was changed. Check that the key is correct and still active "
                "on your provider account, then try that action again."
            ),
            "retry_notice": None,
        }

    if (
        status == 403
        or "permissiondenied" in name_blob
        or matches("model_not_found", "permission_denied", "does not have access")
    ):
        return {
            "category": "model_access_denied",
            "retryable": False,
            "player_message": (
                "Your API key does not have access to the AI model this game "
                "uses. Nothing in your game was changed. Enable that model on "
                "your provider account, or use a key that can reach it."
            ),
            "retry_notice": None,
        }

    if status == 400 or matches("badrequesterror", "invalid_request_error"):
        # The request itself was refused. Reissuing the same request cannot
        # heal it (#240): stop now and let the player change what they asked.
        return {
            "category": "bad_request",
            "retryable": False,
            "player_message": (
                "The AI provider refused that request as malformed. Nothing "
                "in your game was changed. Try rephrasing, or a shorter "
                "action; if it keeps happening, reload the game."
            ),
            "retry_notice": None,
        }

    if (
        status == 429
        or "ratelimiterror" in name_blob
        or matches("rate_limit_exceeded", "resource_exhausted", "rate limit")
    ):
        return {
            "category": "rate_limited",
            "retryable": True,
            "player_message": (
                "The AI provider is rate limiting your key and did not answer "
                "in time. Nothing in your game was changed. Wait a moment and "
                "try that action again."
            ),
            "retry_notice": (
                "The AI provider is rate limiting your key. Slowing down and "
                "retrying..."
            ),
        }

    if (
        (isinstance(status, int) and status >= 500)
        or "apiconnectionerror" in name_blob
        or "apitimeouterror" in name_blob
        or "timeouterror" in name_blob
        or matches(
            "internal server error",
            "service unavailable",
            "bad gateway",
            "connection error",
            "timed out",
            # live-provider child envelopes (class names / disposition)
            "apiconnectionerror",
            "apitimeouterror",
            "retryable_transport",
        )
    ):
        return {
            "category": "provider_unavailable",
            "retryable": True,
            "player_message": (
                "The AI provider is having a problem and could not answer. "
                "Nothing in your game was changed. Please try that action "
                "again in a moment."
            ),
            "retry_notice": (
                "The AI provider is having a problem. Retrying..."
            ),
        }

    return {
        "category": "unclassified",
        "retryable": True,
        "player_message": None,
        "retry_notice": None,
    }


def provider_retry_delay(attempt):
    """Exponential backoff (seconds) for retryable provider failures."""
    return min(
        PROVIDER_RETRY_BASE_DELAY * (2 ** max(attempt, 0)),
        PROVIDER_RETRY_MAX_DELAY,
    )

# A provider failure ends the turn after this many attempts even when each
# attempt looked retryable. Without a bound a rate-limited or flapping
# provider spins the player forever (hosted review 2026-09-01, finding 1).
PROVIDER_MAX_FAILURES = 5


def provider_failure_policy(classification, failures, notice_shown,
                            max_failures=PROVIDER_MAX_FAILURES):
    """Decide what the turn loop does after provider failure number `failures`.

    Returns a dict:
      stop           - True when the turn must end now (non-retryable, or cap)
      notice         - retry notice to show the player once, else None
      delay          - seconds to back off before the next attempt (0 on stop
                       and for unclassified errors, which retry immediately)
      player_message - text for the player if the turn ends, or None for
                       unclassified errors (caller uses its generic text)
    """
    stop = (not classification["retryable"]) or failures >= max_failures
    notice = None
    if not stop and not notice_shown:
        notice = classification["retry_notice"]
    delay = 0.0
    if not stop and classification["category"] != "unclassified":
        delay = provider_retry_delay(failures - 1)
    return {
        "stop": stop,
        "notice": notice,
        "delay": delay,
        "player_message": classification["player_message"],
    }
