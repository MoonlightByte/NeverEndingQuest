"""
OpenAI Client Factory
Provides centralized client creation with LM Studio support
"""

import socket
from importlib.util import find_spec

# httpx and the provider SDK are imported by the builders below, on the first client
# (#1682): a world whose model sends all run in provider children never loads them.
# A missing package still fails here, at import, where the top-level imports failed.
for _package in ("httpx", "openai"):
    if find_spec(_package) is None:
        raise ModuleNotFoundError("No module named %r" % _package, name=_package)
import config


# TCP keepalive on every provider socket (#409, D-409-3, owner-ruled
# 2026-09-19): a path that silently stops acknowledging (NAT/vSwitch drop,
# dead peer) surfaces as a socket error within idle + interval * count
# seconds and feeds the existing reissue loop, instead of a read that waits
# until the generation backstop. A live peer that is merely slow keeps
# answering the probes and is never touched, so this is not a deadline on
# the model's work. Kernel defaults (7200 s idle on Linux) never notice a
# dead path inside a ten-minute wait. The option list is assembled once from
# the constants this platform's socket module exposes (Linux, macOS and
# Windows 10+ expose all four on Python 3.10).
_KEEPALIVE_IDLE_SECONDS = 10
_KEEPALIVE_INTERVAL_SECONDS = 5
_KEEPALIVE_PROBE_COUNT = 3


def _provider_socket_options():
    options = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
    for name, value in (
        ("TCP_KEEPIDLE", _KEEPALIVE_IDLE_SECONDS),
        ("TCP_KEEPINTVL", _KEEPALIVE_INTERVAL_SECONDS),
        ("TCP_KEEPCNT", _KEEPALIVE_PROBE_COUNT),
    ):
        constant = getattr(socket, name, None)
        if constant is not None:
            options.append((socket.IPPROTO_TCP, constant, value))
    return options


PROVIDER_SOCKET_OPTIONS = tuple(_provider_socket_options())


def _provider_http_client():
    """One httpx client shape for every OpenAI-compatible provider."""
    import httpx

    return httpx.Client(
        transport=httpx.HTTPTransport(socket_options=list(PROVIDER_SOCKET_OPTIONS)),
    )


def get_openai_client(provider=None, *, local_endpoint=None):
    """
    Create and return an OpenAI client configured for the active provider.

    Returns:
        OpenAI: Configured OpenAI client

    Behavior:
        - If MODEL_PROVIDER == "lmstudio": Connects to localhost:1234 (local LM Studio)
        - Otherwise: Connects to OpenAI API (requires config.OPENAI_API_KEY)

    Usage:
        from utils.openai_client import get_openai_client
        client = get_openai_client()
        response = client.chat.completions.create(...)
    """
    if provider is None:
        # #2018: inside a module build, the provider it started on.
        from utils.build_inputs import build_provider
        provider = build_provider()

    if provider == "lmstudio":
        # Local / OpenAI-compatible server (LM Studio, Ollama, vLLM, OpenRouter,
        # remote host). Live requests supply their frozen connection settings;
        # other callers read current settings so UI changes apply next request.
        # Defaults preserve
        # the original LM Studio localhost:1234 behavior. (Issue #120)
        # Live children receive the parent's frozen Local/Custom connection
        # settings. Other callers keep the existing live-settings behavior
        # (inside a module build: its URL and model, #2018).
        from utils.build_inputs import request_local_endpoint
        ep = local_endpoint if local_endpoint is not None else request_local_endpoint()
        from openai import OpenAI
        return OpenAI(
            base_url=ep["base_url"],
            api_key=ep["api_key"] or "not-needed",
            http_client=_provider_http_client(),
        )
    else:
        # Connect to OpenAI API (default)
        # Requires valid API key in config.py
        return openai_api_client()


# The OpenAI API host, pinned (#1399). Without an explicit base_url the SDK
# reads OPENAI_BASE_URL from the environment, which would send the player's
# OpenAI key to whatever host that names.
OPENAI_API_BASE_URL = "https://api.openai.com/v1"


def openai_api_client(api_key=None, **kwargs):
    """The one way to build a client that carries the OpenAI key (#1399).

    base_url is OPENAI_API_BASE_URL; a caller cannot pass another. The one
    exception is the operator's --provider-gateway URL (#1682), read from
    this process's argv only (utils/provider_gateway.py), never from the
    environment or a settings file.
    ``api_key`` defaults to config.OPENAI_API_KEY, read at call time. The
    Local/Custom branch above is the only client built elsewhere: it uses
    the player's own endpoint and never the OpenAI key.
    """
    if "base_url" in kwargs:
        raise TypeError("openai_api_client pins base_url to the OpenAI API")
    from openai import OpenAI
    from utils import provider_gateway

    # #1994: no hidden SDK resends. Chat calls already set 0 per call; any
    # other call that is tried again goes through call_with_counted_reissue.
    kwargs.setdefault("max_retries", 0)
    http_client = kwargs.pop("http_client", None) or _provider_http_client()
    return OpenAI(
        api_key=api_key or config.OPENAI_API_KEY,
        base_url=provider_gateway.gateway() or OPENAI_API_BASE_URL,
        http_client=http_client,
        **kwargs,
    )


_REISSUE_POLL_SECONDS = 0.25


def _possibly_billed(exc):
    """A failure after the request was sent that the provider may bill: a
    timeout, or a 5xx answer. A refused connection or a 4xx is not."""
    import openai

    if isinstance(exc, openai.APITimeoutError):
        return True
    status = getattr(exc, "status_code", None)
    return isinstance(exc, openai.APIStatusError) and isinstance(status, int) and status >= 500


def _reissue_wait(seconds):
    """Wait before a reissue, ending at once on a save stop."""
    import time

    from utils.transient_filesystem import raise_if_save_stopped

    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        raise_if_save_stopped()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(_REISSUE_POLL_SECONDS, remaining))


def call_with_counted_reissue(fn, label, limit=1, max_delay=None):
    """Call ``fn()`` (one OpenAI SDK request on a client with no hidden
    resends) and reissue it at most ``limit`` times, counted and logged
    (#1994).

    A failure is reissued only when the SDK would have resent it (typed
    fields only, as Route P: a connection error, or a status with
    x-should-retry, 408/409/429/5xx; never a quota code) and the wait is at
    most ``max_delay`` (default RETRY_AFTER_CAP). A failure that may have
    been billed is counted in the session's spending. The error raised is
    always the SDK's own exception object, never a wrapper, so callers read
    the same typed fields as before.
    """
    from types import SimpleNamespace

    from utils.capture.live_provider_call import RETRY_AFTER_CAP
    from utils.capture.multi_model_capture import _route_p_reissue_delay
    from utils.enhanced_logger import file_only
    from utils.session_spend import record_possibly_billed

    cap = RETRY_AFTER_CAP if max_delay is None else float(max_delay)
    reissues = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if _possibly_billed(exc):
                record_possibly_billed()
            if reissues >= limit:
                raise
            delay = _route_p_reissue_delay(SimpleNamespace(original_error=exc), reissues + 1)
            if delay is None or delay > cap:
                raise
            reissues += 1
            file_only(
                "PROVIDER_REISSUE: %s failed (%s, HTTP %s); reissue %d/%d "
                "in %.1f s." % (
                    label, type(exc).__name__, getattr(exc, "status_code", None),
                    reissues, limit, delay,
                ),
                category="provider_retry",
            )
            _reissue_wait(delay)


def is_using_lm_studio():
    """
    Check if the game is configured to use LM Studio.

    Returns:
        bool: True if MODEL_PROVIDER is "lmstudio", False otherwise

    Usage:
        from utils.openai_client import is_using_lm_studio
        if is_using_lm_studio():
            print("Running with local LM Studio")
    """
    from model_config import MODEL_PROVIDER
    return MODEL_PROVIDER == "lmstudio"
