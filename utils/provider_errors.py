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

# Structured provider error codes that mean "no amount of retrying will pay
# the bill". They arrive with HTTP 429 exactly like a rate limit; the CODE
# separates them (a structured field, never prose).
QUOTA_ERROR_CODES = frozenset({
    "insufficient_quota",
    "insufficient_credit",
    "billing_hard_limit_reached",
    "credit_balance_exhausted",
})

_PROVIDER_NAMES = {
    "openai": "OpenAI",
    "legacy": "OpenAI",
    "gemini": "Gemini (Google AI)",
    "lmstudio": "your local model server",
}


def provider_display_name(provider):
    """Player-facing name for a provider id; unknown ids read as 'the AI provider'."""
    return _PROVIDER_NAMES.get(str(provider or "").lower(), "the AI provider")


def _sentence(text):
    """Capitalize the first letter (names like 'your local model server' start sentences)."""
    return text[:1].upper() + text[1:] if text else text


# Account refusals the player fixes on their own account or server (#240,
# #284, #432). One table holds each reason and fix; account_refusal_message
# renders them for the moment the refusal reaches the player. Each reason and
# fix stays on one source line.
_ACCOUNT_REFUSALS = {
    # #1342: the game's own bounds on a player's tokens, not account faults,
    # but they reach the player at the same moments and end the same way.
    "reissue_limit": {
        "reason": "%(name)s kept failing to answer, so the game stopped retrying to save your tokens",
        "fix": "Wait a minute, or check that provider's status",
    },
    "turn_call_ceiling": {
        "reason": "That turn needed more AI calls than one turn is allowed, so the game stopped it to save your tokens",
        "fix": "Wait a moment",
    },
    "insufficient_quota": {
        "reason": "%(name)s refused the request: your account is out of funds or quota",
        "fix": "Add credit or raise the quota on that account",
    },
    "authentication_failed": {
        "reason": "%(name)s rejected your API key",
        "fix": "Check that the key is correct and still active, update it in Settings (the gear icon)",
    },
    "model_access_denied": {
        "reason": "Your API key does not have access to one of the AI models this game uses",
        "fix": "Enable that model on your provider account, or use a key that can reach it",
        # A local or custom server has no account to fix: LM Studio with no
        # model loaded answers model_not_found.
        "overrides": {
            "lmstudio": {
                "reason": "Your local or custom model server does not offer the AI model this game uses",
                "fix": "Load or select that model on that server",
            },
        },
    },
}

# #1711: with the operator's --provider-gateway the host holds the account,
# so a refused key, quota or model is never the player's to fix.
_HOSTED_ACCOUNT_REFUSAL = {
    "reason": "The game's AI service refused the request",
    "fix": "This is on the host's side, not yours: let the host know, or wait a few minutes",
}
_HOSTED_ACCOUNT_CATEGORIES = ("authentication_failed", "insufficient_quota", "model_access_denied")

_ACCOUNT_REFUSAL_MOMENTS = {
    # The turn loop's DM call: nothing from the turn has run yet.
    "turn": "%s. Nothing in your game was changed. %s, then try that action again.",
    # After the narration was shown: earlier actions may already be applied.
    "after_narration": "%s. That action could not be completed, and no further actions from that response were applied. %s, then continue.",
    # The startup welcome: no player action exists yet.
    "welcome": "%s. Nothing in your game was changed. %s, then tell the DM what you do next.",
    # A follow-up after the response was applied (#442): what happened is kept.
    "followup": "%s. What already happened in your game is kept, but the DM could not narrate what comes next. %s, then continue.",
    # A fight left after a refused combat call (#1087): it stays saved and active.
    "combat": "%s. The fight is saved as it stands. %s, then load your game to continue the fight.",
}


def account_refusal_message(category, provider, moment):
    """Curated player text for an account refusal at ``moment``, or None.

    ``category`` is a classify_provider_error slug; any category outside the
    table (and any non-string) returns None so callers keep their own line.
    """
    if not isinstance(category, str):
        return None
    entry = _ACCOUNT_REFUSALS.get(category)
    template = _ACCOUNT_REFUSAL_MOMENTS.get(moment)
    if entry is None or template is None:
        return None
    from utils.provider_gateway import gateway

    if category in _HOSTED_ACCOUNT_CATEGORIES and gateway() is not None:
        entry = _HOSTED_ACCOUNT_REFUSAL
    else:
        entry = entry.get("overrides", {}).get(str(provider or "").lower(), entry)
    reason = entry["reason"] % {"name": provider_display_name(provider)}
    return _sentence(template % (reason, entry["fix"]))


def _provider_of(exc):
    """Provider id carried by a provider exception or a child envelope, or ''."""
    for item in _provider_error_chain(exc):
        envelope = getattr(item, "envelope", None)
        if isinstance(envelope, dict) and envelope.get("provider"):
            return str(envelope["provider"])
        value = getattr(item, "provider", None)
        if isinstance(value, str) and value:
            return value
    return ""


def reissue_notice(disposition, http_status, provider, error_code=None,
                   last_phase=None):
    """Plain-words reason for a live reissue, shown once per class per turn.

    Owner requirement (2026-09-05): a local model must read as a lost
    connection; OpenAI and Gemini must name themselves so the player knows
    which account to look at. ``last_phase`` is the transport phase the
    child last reported (#409): the sentence states what was observed and
    never guesses a cause the transport did not see.
    """
    name = provider_display_name(provider)
    local = str(provider or "").lower() == "lmstudio"
    if isinstance(error_code, str) and error_code.lower() in QUOTA_ERROR_CODES:
        return _sentence(
            "%s reports your account is out of funds or quota. Retrying will "
            "not help; add credit or raise your quota, then try again." % name
        )
    if http_status == 429:
        return _sentence(
            "%s is rate limiting your key (or its quota is exhausted). "
            "Slowing down and retrying; if this keeps happening, check your "
            "provider account's usage and billing." % name
        )
    if isinstance(http_status, int) and http_status >= 500:
        return _sentence(
            "%s answered with a server error. Retrying with a fresh "
            "connection." % name
        )
    if local:
        return (
            "Connection to your local model server was lost. Reconnecting; "
            "check that it is still running."
        )
    phase = str(last_phase or "")
    if phase in ("spawned", "payload_read", "connecting"):
        return _sentence(
            "%s could not be reached (no connection was established). Trying "
            "a fresh connection." % name
        )
    if phase in ("connected", "secured", "sent"):
        return _sentence(
            "%s received the request but never acknowledged it. Trying a "
            "fresh connection." % name
        )
    if phase in ("acknowledged", "working", "receiving"):
        return _sentence(
            "%s stopped answering part-way through. Trying a fresh "
            "connection." % name
        )
    return _sentence(
        "%s did not answer. Trying a fresh connection." % name
    )


def player_exits_notice():
    """What the player can do while a turn keeps retrying (once per turn)."""
    return (
        "Your turn is safe and will keep retrying. Load or Reset stop it "
        "now. A Save is accepted right away and lands when the turn ends."
    )


# #1224: the packages whose exceptions carry a provider's typed verdict. Only
# their exceptions are read for a bare int `code`, a str `status` or a
# transport class; the game's own exceptions never are.
_TRANSPORT_PACKAGES = ("openai", "google.genai", "httpx", "httpcore")
# The live transport's network set (utils/capture/live_provider_call.py).
_TRANSPORT_CLASSES = frozenset({
    "APITimeoutError", "APIConnectionError", "TimeoutException",
    "TransportError", "NetworkError",
})


def _from_transport(exc):
    """True when exc's class is defined in a provider/transport package."""
    module = type(exc).__module__ or ""
    return any(module == package or module.startswith(package + ".")
               for package in _TRANSPORT_PACKAGES)


def _is_transport_failure(exc):
    """A transport-package exception of the live transport's network set."""
    return _from_transport(exc) and any(
        base.__name__ in _TRANSPORT_CLASSES for base in type(exc).__mro__)


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
    # google-genai carries the HTTP status as an int `code`.
    value = getattr(exc, "code", None)
    if (_from_transport(exc) and isinstance(value, int)
            and not isinstance(value, bool) and 100 <= value <= 599):
        return value
    return None


def _provider_error_codes(exc):
    """Collect provider error code/type strings from a provider exception."""
    codes = []
    envelope = getattr(exc, "envelope", None)
    if isinstance(envelope, dict):
        # A live-provider child envelope (utils/capture/live_provider_call):
        # the wrapped exception class names carry the provider's verdict.
        for key in ("error_class", "cause_class", "disposition", "error_code"):
            value = envelope.get(key)
            if isinstance(value, str):
                codes.append(value.lower())
    for attribute in ("code", "type"):
        value = getattr(exc, attribute, None)
        if isinstance(value, str):
            codes.append(value.lower())
    # google-genai's str `status` (RESOURCE_EXHAUSTED, UNAUTHENTICATED, ...).
    value = getattr(exc, "status", None)
    if _from_transport(exc) and isinstance(value, str):
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


def _classify_provider_error(exc):
    """Classify a provider exception for retry policy and player messaging.

    Returns a dict with:
      category       - stable slug for logs
      retryable      - False when another attempt cannot possibly succeed
      player_message - text to show the player when the turn fails, or None
                       for unclassified errors (which keep the existing safe
                       failure message)
      retry_notice   - text to show the player before backing off, or None
      provider       - the provider id the classification used ('' if none)

    Classifies from exception types/status/codes only; provider prose is
    never authority (#1224): message text is never read.
    """
    status = None
    codes = []
    names = []
    transport = False
    provider = _provider_of(exc)
    name = provider_display_name(provider)
    local = provider.lower() == "lmstudio"
    for item in _provider_error_chain(exc):
        if status is None:
            status = _provider_error_status(item)
        names.append(type(item).__name__.lower())
        codes.extend(_provider_error_codes(item))
        transport = transport or _is_transport_failure(item)
    code_blob = " ".join(codes)
    name_blob = " ".join(names)

    def matches(*needles):
        return any(needle in code_blob for needle in needles)

    # #1342: a live call that hit its reissue limit, or a turn that hit its
    # generation ceiling. Checked first: the limit envelope can carry the 429
    # it ended on, and another attempt would spend the tokens the bound saved.
    for bound in ("turn_call_ceiling", "reissue_limit"):
        if bound in codes:
            return {
                "category": bound,
                "retryable": False,
                "player_message": account_refusal_message(bound, provider, "turn"),
                "retry_notice": None,
                "provider": provider,
            }

    # Out of credit arrives as a 429, exactly like a rate limit, but no number
    # of retries will pay the bill -- the error code separates them, not the
    # status.
    if matches(*sorted(QUOTA_ERROR_CODES)):
        return {
            "category": "insufficient_quota",
            "retryable": False,
            "player_message": account_refusal_message(
                "insufficient_quota", provider, "turn"
            ),
            "retry_notice": None,
            "provider": provider,
        }

    if (
        status == 401
        or "authenticationerror" in name_blob
        or matches(
            "invalid_api_key",
            "invalid_authentication",
            "unauthenticated",
        )
    ):
        return {
            "category": "authentication_failed",
            "retryable": False,
            "player_message": account_refusal_message(
                "authentication_failed", provider, "turn"
            ),
            "retry_notice": None,
            "provider": provider,
        }

    if (
        status == 403
        or "permissiondenied" in name_blob
        or matches("model_not_found", "permission_denied")
    ):
        return {
            "category": "model_access_denied",
            "retryable": False,
            "player_message": account_refusal_message(
                "model_access_denied", provider, "turn"
            ),
            "retry_notice": None,
            "provider": provider,
        }

    if status == 400 or matches("badrequesterror", "invalid_request_error"):
        # The request itself was refused. Reissuing the same request cannot
        # heal it (#240): stop now and let the player change what they asked.
        return {
            "category": "bad_request",
            "provider": provider,
            "retryable": False,
            "player_message": _sentence(
                "%s refused that request as malformed. Nothing in your game "
                "was changed. Try rephrasing the action; if it keeps "
                "happening, Load your last save." % name
            ),
            "retry_notice": None,
        }

    if (
        status == 429
        or "ratelimiterror" in name_blob
        or matches("rate_limit_exceeded", "resource_exhausted")
    ):
        return {
            "category": "rate_limited",
            "provider": provider,
            "retryable": True,
            "player_message": _sentence(
                "%s is rate limiting your key and did not answer in time. "
                "Nothing in your game was changed. Wait a moment and try that "
                "action again; if it keeps happening, check that account's "
                "usage and billing." % name
            ),
            "retry_notice": reissue_notice("retryable_http", 429, provider),
        }

    if (
        (isinstance(status, int) and status >= 500)
        or "apiconnectionerror" in name_blob
        or "apitimeouterror" in name_blob
        or "timeouterror" in name_blob
        or transport
        or matches(
            # live-provider child envelopes (class names / disposition)
            "apiconnectionerror",
            "apitimeouterror",
            "retryable_transport",
        )
    ):
        return {
            "category": "provider_unavailable",
            "provider": provider,
            "retryable": True,
            "player_message": (
                (
                    "Connection to your local model server was lost and it "
                    "did not answer. Nothing in your game was changed. Check "
                    "that it is running, then try that action again."
                )
                if local
                else _sentence(
                    "%s did not answer (connection dropped or server error). "
                    "Nothing in your game was changed. Try that action again "
                    "in a moment." % name
                )
            ),
            "retry_notice": reissue_notice(
                "retryable_transport", status, provider
            ),
        }

    return {
        "category": "unclassified",
        "provider": provider,
        "retryable": True,
        "player_message": None,
        "retry_notice": None,
    }


# ---------------------------------------------------------------------------
# #1981: connection classes and the plain notice (OWNER D-CONN-2, D-CONN-3)
# ---------------------------------------------------------------------------
# One class per failure, from typed fields only (never message text, #1224).
# Each notice leads with "Connection problem:" or "Account problem:" so the
# player knows at a glance it is not the story; no try count in a card (the
# count lives on the status line).
CONNECTION_CLASSES = (
    "no_connection", "no_answer", "service_error", "rate_limited",
    "out_of_quota", "bad_key",
)
_BACKSTOP_CLASSES = frozenset(
    {"ProviderChildGenerationBackstop", "ProviderChildAcknowledgeBackstop"}
)
# The child failed to start or to read its payload: the provider was never
# asked, so it is not a connection class (plan r1 f).
_CHILD_START_CLASSES = frozenset({"ProviderChildUnavailable", "process_setup_unavailable"})
_CHILD_INTERNAL_PHASES = frozenset({None, "", "spawned", "payload_read"})
_AFTER_SEND_PHASES = frozenset({"sent", "acknowledged", "working", "receiving", "done"})
_BOUND_CODES = frozenset({"reissue_limit", "turn_call_ceiling", "advisory_reserve"})
_TIMEOUT_NAMES = frozenset(
    {"apitimeouterror", "readtimeout", "writetimeout", "timeoutexception", "pooltimeout"}
)
_CONNECT_NAMES = frozenset(
    {"apiconnectionerror", "connecterror", "connecttimeout", "gaierror", "networkerror",
     "transporterror", "remoteprotocolerror", "readerror"}
)
_AUTH_CODES = ("invalid_api_key", "invalid_authentication", "unauthenticated")

_RETRY_LINES = {
    "no_connection": "Connection problem: the game can't reach %(P)s. Trying again.",
    "no_answer": "Connection problem: %(P)s isn't replying. Trying again.",
    "service_error": "Connection problem: %(P)s is having trouble right now. Trying again.",
    "rate_limited": "Connection problem: %(P)s is asking the game to slow down. Waiting, then trying again.",
}
_RETRY_LINES_LOCAL = {
    "no_connection": "Connection problem: the game can't reach your local model server. Check that it's running. Trying again.",
    "no_answer": "Connection problem: your local model server hasn't replied for %(N)d minutes. Trying again.",
}
_GIVE_UP_LINES = {
    "no_connection": "Connection problem: the game couldn't reach %(P)s. Check that you're online.",
    "no_answer": "Connection problem: %(P)s didn't reply in time.",
    "service_error": "Connection problem: %(P)s is having trouble right now. This is not a problem with your game. Wait a few minutes.",
    "rate_limited": "Connection problem: %(P)s is still asking the game to slow down. Wait a minute. If this happens often, your %(P)s account may have a low usage limit.",
    "out_of_quota": "Account problem: your %(P)s account has run out of credit or reached its spending limit. Add credit on the %(P)s website.",
    "bad_key": "Account problem: %(P)s didn't accept your API key. Check the key in Settings (the gear icon).",
}
_GIVE_UP_LINES_LOCAL = {
    "no_connection": "Connection problem: the game couldn't reach your local model server. Start it, or check its address in Settings > Local/Custom.",
    "no_answer": "Connection problem: your local model server didn't reply in time. Check that it's still running and not busy with something else.",
    "rate_limited": "Connection problem: your local model server is still asking the game to slow down. Wait a minute.",
    "bad_key": "Account problem: your local or custom model server didn't accept its API key. Check the key in Settings > Local/Custom.",
    "out_of_quota": "Account problem: your custom model server says its account has run out of credit or reached its spending limit. Check that account with whoever runs the server.",
}
# #1711: with the operator's gateway the host holds the account.
_HOSTED_GIVE_UP_LINE = (
    "Account problem: the game's AI service refused the request. This is on the "
    "host's side, not yours: let the host know, or wait a few minutes."
)
# What follows the give-up line, by moment. A moment not here (a follow-up
# after a kept beat, #1228) keeps its existing line.
_CONNECTION_TAILS = {
    "turn": "Nothing in your game changed. Send your action again when you're ready.",
    "combat": "The fight is saved as it stands; load your game to continue the fight.",
    "welcome": "Nothing in your game changed. Tell the DM what you do next when you're ready.",
    "level_up": "Your level-up has not been applied. Nothing changed; ask to level up again later.",
}
# A moment the account table does not name takes this one's account line
# (level-up always used the turn's, #442).
_ACCOUNT_MOMENT_FOR = {"level_up": "turn"}


def _envelope_of(item):
    if isinstance(item, dict):
        return item
    envelope = getattr(item, "envelope", None)
    return envelope if isinstance(envelope, dict) else None


def _envelope_class(envelope):
    """connection_class for a live-child envelope (typed fields only)."""
    if "connection_class" in envelope:
        # A bound (reissue_limit) carries the class of its last failure.
        return envelope["connection_class"]
    code = str(envelope.get("error_code") or "").lower()
    status = envelope.get("http_status")
    error_class = envelope.get("error_class")
    cause = str(envelope.get("cause_class") or "").lower()
    reached = envelope.get("reached_phase") or envelope.get("last_phase")
    if reached == "failed":
        reached = None
    if code in QUOTA_ERROR_CODES:
        return "out_of_quota"
    if code in _BOUND_CODES:
        return None
    if status == 401 or code in _AUTH_CODES or cause == "authenticationerror":
        return "bad_key"
    if status == 429:
        return "rate_limited"
    if isinstance(status, int) and (status >= 500 or status == 408):
        return "service_error"
    if isinstance(status, int):
        return None
    if error_class in _BACKSTOP_CLASSES:
        return "no_answer"
    if error_class in _CHILD_START_CLASSES and reached in _CHILD_INTERNAL_PHASES:
        return None
    disposition = envelope.get("disposition")
    if disposition == "retryable_http":
        # A failed Responses stream with a server code and no HTTP status.
        return "service_error"
    if disposition == "retryable_transport" or cause in _TIMEOUT_NAMES | _CONNECT_NAMES:
        return "no_answer" if reached in _AFTER_SEND_PHASES else "no_connection"
    return None


def connection_class(exc_or_envelope):
    """The connection class of a provider failure, or None (#1981)."""
    envelope = _envelope_of(exc_or_envelope)
    if envelope is not None:
        return _envelope_class(envelope)
    status = None
    codes = []
    names = set()
    for item in _provider_error_chain(exc_or_envelope):
        envelope = _envelope_of(item)
        if envelope is not None:
            return _envelope_class(envelope)
        if status is None:
            status = _provider_error_status(item)
        codes.extend(_provider_error_codes(item))
        if _from_transport(item):
            names.update(base.__name__.lower() for base in type(item).__mro__)
    if any(code in QUOTA_ERROR_CODES for code in codes):
        return "out_of_quota"
    if status == 401 or any(code in _AUTH_CODES for code in codes) or "authenticationerror" in names:
        return "bad_key"
    if status == 429:
        return "rate_limited"
    if isinstance(status, int) and (status >= 500 or status == 408):
        return "service_error"
    if isinstance(status, int):
        return None
    if names & _TIMEOUT_NAMES and not {"connecttimeout"} & names:
        return "no_answer"
    if names & _CONNECT_NAMES:
        return "no_connection"
    return None


def _is_local(provider):
    return str(provider or "").lower() == "lmstudio"


def connection_retry_line(cls, provider, minutes=0):
    """The card while a connection class is being retried, or None."""
    if _is_local(provider) and cls in _RETRY_LINES_LOCAL and (cls != "no_answer" or minutes >= 2):
        # Under two whole minutes the local no_answer card takes the plain
        # form: never "0 minutes" or "1 minutes".
        return _RETRY_LINES_LOCAL[cls] % {"N": int(minutes)}
    template = _RETRY_LINES.get(cls)
    return template % {"P": provider_display_name(provider)} if template else None


def connection_give_up_line(cls, provider):
    """The line a connection class ends on, before its tail, or None."""
    from utils.provider_gateway import gateway

    if cls in ("bad_key", "out_of_quota") and gateway() is not None:
        return _HOSTED_GIVE_UP_LINE
    if _is_local(provider) and cls in _GIVE_UP_LINES_LOCAL:
        return _GIVE_UP_LINES_LOCAL[cls]
    template = _GIVE_UP_LINES.get(cls)
    return template % {"P": provider_display_name(provider)} if template else None


def connection_notice(cls, provider, moment):
    """The give-up line plus the moment's tail, or None when the class or the
    moment has none (the caller keeps its existing line)."""
    tail = _CONNECTION_TAILS.get(moment)
    line = connection_give_up_line(cls, provider) if tail else None
    return "%s %s" % (line, tail) if line else None


def provider_refusal_line(refusal, moment):
    """A classified refusal's text at ``moment``: the connection notice when it
    has a class, else the existing account line (None when neither)."""
    notice = connection_notice(refusal.get("connection_class"), refusal.get("provider"), moment)
    if notice is not None:
        return notice
    return account_refusal_message(
        refusal.get("category"), refusal.get("provider"), _ACCOUNT_MOMENT_FOR.get(moment, moment)
    )


def classify_provider_error(exc):
    """_classify_provider_error plus the #1981 connection class: a failure with
    a class ends on its plain connection or account notice."""
    result = _classify_provider_error(exc)
    cls = connection_class(exc)
    result["connection_class"] = cls
    if cls is not None:
        result["player_message"] = connection_notice(cls, result["provider"], "turn")
        if result.get("retry_notice") is not None:
            result["retry_notice"] = connection_retry_line(cls, result["provider"])
    return result


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
