# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Check an OpenAI key when the player saves it (#1399 G1).

One models.list request with the new key: it is free (no tokens are billed)
and answers whether OpenAI accepts the key. The result is a typed slug the
web UI turns into the player's line; nothing here returns, prints or logs
the key, the raw exception or the response body (an OpenAI 401 body carries
a masked key).
"""

from utils.enhanced_logger import debug

ACCEPTED = "accepted"
REJECTED = "rejected"
RATE_LIMITED = "rate_limited"
DENIED = "denied"
NO_QUOTA = "no_quota"
UNREACHABLE = "unreachable"
RESULTS = (ACCEPTED, REJECTED, RATE_LIMITED, DENIED, NO_QUOTA, UNREACHABLE)

_CHECK_TIMEOUT_SECONDS = 15.0


def _status(exc):
    from utils.provider_errors import _provider_error_status

    try:
        status = _provider_error_status(exc)
    except Exception:
        return None
    return status if type(status) is int else None


def _retry_after_seconds(exc):
    """Seconds from the 429's Retry-After header, or None without one."""
    try:
        headers = exc.response.headers
        value = headers.get("retry-after")
        if value is None and headers.get("retry-after-ms") is not None:
            return max(1, round(float(headers["retry-after-ms"]) / 1000))
        return max(1, round(float(value))) if value is not None else None
    except Exception:
        return None


def classify_key_check_error(exc):
    """(result, status, wait_seconds) for a failed models.list."""
    from utils.provider_errors import classify_provider_error

    status = _status(exc)
    try:
        category = classify_provider_error(exc).get("category")
    except Exception:
        category = None
    # Out of credit arrives as a 429 like a rate limit; its code tells them
    # apart. Otherwise the HTTP status decides, never the message text.
    if category == "insufficient_quota":
        return NO_QUOTA, status, None
    if status == 401:
        return REJECTED, status, None
    if status == 403:
        return DENIED, status, None
    if status == 429:
        return RATE_LIMITED, status, _retry_after_seconds(exc)
    if status is None and category == "authentication_failed":
        return REJECTED, status, None
    # A timeout, a refused connection, a 5xx or anything else: the key could
    # not be checked, which says nothing against it.
    return UNREACHABLE, status, None


def check_openai_key(api_key):
    """Ask OpenAI once whether it accepts ``api_key``.

    Returns {"result": one of RESULTS, "status": int or None,
    "wait_seconds": int or None}. Never raises.
    """
    from utils.openai_client import openai_api_client

    status = None
    wait_seconds = None
    try:
        client = openai_api_client(
            api_key=api_key, timeout=_CHECK_TIMEOUT_SECONDS, max_retries=0
        )
        client.models.list()
        result = ACCEPTED
        status = 200
    except Exception as exc:  # classified only; its text is never kept
        try:
            result, status, wait_seconds = classify_key_check_error(exc)
        except Exception:
            result = UNREACHABLE
    debug(
        "[key check] result=%s status=%s" % (result, status if status is not None else "none"),
        category="web_interface",
    )
    return {"result": result, "status": status, "wait_seconds": wait_seconds}
