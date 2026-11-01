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
        import model_config
        provider = model_config.get_provider()

    if provider == "lmstudio":
        # Local / OpenAI-compatible server (LM Studio, Ollama, vLLM, OpenRouter,
        # remote host). Live requests supply their frozen connection settings;
        # other callers read current settings so UI changes apply next request.
        # Defaults preserve
        # the original LM Studio localhost:1234 behavior. (Issue #120)
        import model_config
        # Live children receive the parent's frozen Local/Custom connection
        # settings. Other callers keep the existing live-settings behavior.
        ep = local_endpoint if local_endpoint is not None else model_config.get_local_endpoint()
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

    base_url is always OPENAI_API_BASE_URL; a caller cannot pass another.
    ``api_key`` defaults to config.OPENAI_API_KEY, read at call time. The
    Local/Custom branch above is the only client built elsewhere: it uses
    the player's own endpoint and never the OpenAI key.
    """
    if "base_url" in kwargs:
        raise TypeError("openai_api_client pins base_url to the OpenAI API")
    from openai import OpenAI

    http_client = kwargs.pop("http_client", None) or _provider_http_client()
    return OpenAI(
        api_key=api_key or config.OPENAI_API_KEY,
        base_url=OPENAI_API_BASE_URL,
        http_client=http_client,
        **kwargs,
    )


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
