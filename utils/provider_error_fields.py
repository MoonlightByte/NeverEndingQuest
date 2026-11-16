"""Typed fields of a failed provider call, for the debug log only (#2046).

One reader for both routes: the live child puts these fields in its error
envelope and the parent logs them; the in-process route (Route P) logs them
where it handles the error. Only structured attributes are read: class names,
the HTTP status, the error's code/type/param, the stream event's type name,
the error body's key names, an empty answer's finish reason. The error's
message text is never read.

Every string value is bounded: at most 64 characters from [A-Za-z0-9_.-],
anything else is recorded as "<other>". This keeps provider prose (or
anything quoted from a prompt) out of the log even if it arrives in a field
that is normally a short code.
"""

import re

_BOUNDED = re.compile(r"[A-Za-z0-9_.-]{1,64}")
OTHER = "<other>"
_MAX_BODY_KEYS = 24

# The order of the fields in the log line; both routes write all of them.
FIELD_ORDER = (
    "error_class",
    "cause_class",
    "http_status",
    "code",
    "type",
    "param",
    "disposition",
    "arrival",
    "event_type",
    "body_keys",
    "finish_reason",
    "incomplete_reason",
)

_TRANSPORT_CLASSES = frozenset({
    "APITimeoutError",
    "APIConnectionError",
    "TimeoutException",
    "TransportError",
    "NetworkError",
})


def bounded(value):
    """A short identifier as it is, None as None, anything else "<other>"."""
    if value is None:
        return None
    if isinstance(value, bool):
        return OTHER
    if isinstance(value, int):
        value = str(value)
    if isinstance(value, str) and _BOUNDED.fullmatch(value):
        return value
    return OTHER


def _chain(exc):
    original = getattr(exc, "original_error", None)
    return [item for item in (original, exc) if item is not None]


def _body_detail(item):
    body = getattr(item, "body", None)
    if not isinstance(body, dict):
        return None, None
    detail = body.get("error")
    return body, (detail if isinstance(detail, dict) else body)


def _first_str(exc, name):
    """The first non-empty str attribute ``name`` on the chain, else the body's."""
    for item in _chain(exc):
        value = getattr(item, name, None)
        if isinstance(value, str) and value:
            return value
        _body, detail = _body_detail(item)
        if detail is not None:
            value = detail.get(name)
            if isinstance(value, str) and value:
                return value
    return None


def _http_status(exc):
    for item in _chain(exc):
        for value in (
            getattr(item, "status_code", None),
            getattr(getattr(item, "response", None), "status_code", None),
            getattr(item, "code", None),
        ):
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def _key(key):
    """A body key name, or "_other" when it is not a short identifier."""
    return key if isinstance(key, str) and bounded(key) == key else "_other"


def _body_keys(exc):
    for item in _chain(exc):
        body, detail = _body_detail(item)
        if body is None:
            continue
        keys = [_key(key) for key in body]
        if detail is not body:
            keys += ["error." + _key(key) for key in detail]
        keys = sorted(set(keys))
        if len(keys) > _MAX_BODY_KEYS:
            keys = keys[:_MAX_BODY_KEYS] + ["_more"]
        return keys
    return None


def _arrival(exc, status):
    """How the failure arrived:
    "status"       an HTTP error status (>= 400);
    "stream_event" an APIError with no status (openai raises one for an error
                   event inside an answered stream), or the game's
                   ResponsesStreamFailed;
    "other"        anything else: transport, an empty answer, a 200 the SDK
                   could not parse (APIResponseValidationError), ...
    The http_status field keeps whatever status was found."""
    if isinstance(status, int) and status >= 400:
        return "status"
    cause = getattr(exc, "original_error", None) or exc
    names = {base.__name__ for base in type(cause).__mro__}
    if "ResponsesStreamFailed" in names:
        return "stream_event"
    if (
        status is None
        and "APIError" in names
        and not names & _TRANSPORT_CLASSES
        and "APIResponseValidationError" not in names
    ):
        # openai raises a plain APIError (no status) for an error event in an
        # HTTP 200 stream (openai/_streaming.py).
        return "stream_event"
    return "other"


def error_fields(exc, disposition=None):
    """The bounded typed fields of ``exc`` (a ProviderCallError or any error)."""
    original = getattr(exc, "original_error", None)
    status = _http_status(exc)
    event_type = None
    for item in _chain(exc):
        value = getattr(item, "event_type", None)
        if isinstance(value, str) and value:
            event_type = value
            break
    return {
        "error_class": bounded(type(exc).__name__),
        "cause_class": bounded(type(original).__name__) if original is not None else None,
        "http_status": bounded(status),
        "code": bounded(_first_str(exc, "code")),
        "type": bounded(_first_str(exc, "error_type") or _first_str(exc, "type")),
        "param": bounded(_first_str(exc, "param")),
        "disposition": bounded(disposition),
        "arrival": _arrival(exc, status),
        "event_type": bounded(event_type),
        "body_keys": _body_keys(exc),
        "finish_reason": bounded(getattr(exc, "finish_reason", None)),
        "incomplete_reason": bounded(getattr(exc, "incomplete_reason", None)),
    }


def fields_line(route, task_id, fields):
    """One log line: PROVIDER_ERROR_FIELDS route=... task=... key=value ..."""
    fields = fields if isinstance(fields, dict) else {}
    parts = ["PROVIDER_ERROR_FIELDS", "route=%s" % bounded(route),
             "task=%s" % bounded(task_id)]
    for name in FIELD_ORDER:
        value = fields.get(name)
        if isinstance(value, list):
            value = ",".join(bounded(item) or OTHER for item in value
                             if isinstance(item, str)) or "none"
        else:
            value = bounded(value) if value is not None else "none"
        parts.append("%s=%s" % (name, value))
    return " ".join(parts)
