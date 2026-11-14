# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Operator-only provider gateway (#1682).

A hosted world is started with ``--provider-gateway <url>``. The OpenAI and
Gemini clients then send to that URL instead of the provider's own API: the
gateway holds the real key and meters spend, and the world's key slot holds a
low-value token for it. Asked by the hosted server agent
(NeverEndingQuest-Server #315).

The URL is read ONLY from a process's own argv. It is never read from the
environment (OPENAI_BASE_URL stays ignored, #1399) or from any file a player
can write, such as user_settings.json. Each entry point calls
take_from_argv(sys.argv) before anything else parses its arguments, and every
child the game spawns gets child_argv() so it receives the flag the same way.
Unset, nothing changes.
"""

from urllib.parse import urlsplit

FLAG = "--provider-gateway"

_gateway = None


def _checked(value):
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or any(c.isspace() for c in value):
        raise SystemExit("%s needs an http(s) URL, got %r" % (FLAG, value))
    return value


def take_from_argv(argv):
    """Remove every ``--provider-gateway URL`` (or ``=URL``) from argv in place
    and remember the last one. Returns the gateway URL or None."""
    global _gateway
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == FLAG:
            if i + 1 >= len(argv):
                raise SystemExit("%s needs a URL" % FLAG)
            value = argv[i + 1]
            del argv[i:i + 2]
        elif arg.startswith(FLAG + "="):
            value = arg[len(FLAG) + 1:]
            del argv[i]
        else:
            i += 1
            continue
        _gateway = _checked(value)
    return _gateway


def gateway():
    """The gateway URL this process was started with, or None."""
    return _gateway


def child_argv(argv):
    """``argv`` for a child process, with the flag appended when it is set."""
    if _gateway is None:
        return argv
    return list(argv) + [FLAG, _gateway]


# #1995: on a hosted world (operator gateway) the provider, keys, endpoint,
# updates and the module toolkit belong to the host.
HOSTED_ENDPOINT_TEST_DETAIL = "Not available on a hosted game: the host sets the AI service."
HOSTED_UPDATES = "Updates come from the host."
_HOSTED_TOOLKIT_PREFIXES = ("/toolkit", "/api/toolkit")


def hosted_settings_refusal(emit, event):
    """#1995: refuse a settings, update or toolkit socket event on a hosted
    world. Called first in each handler, before any write or network call;
    never echoes the request. Returns True when the event was refused."""
    if _gateway is None:
        return False
    emit("settings_refused", {"event": event, "reason": "hosted"})
    if event == "test_local_endpoint":
        # The Settings page waits for this result.
        emit("local_endpoint_test_result",
             {"ok": False, "reason": "hosted", "detail": HOSTED_ENDPOINT_TEST_DETAIL})
    elif event == "trigger_update":
        emit("update_error", {"error": HOSTED_UPDATES})
    return True


def hosted_toolkit_path(path):
    """#1995: True for a module toolkit page or API path on a hosted world."""
    if _gateway is None:
        return False
    return any(path == p or path.startswith(p + "/") for p in _HOSTED_TOOLKIT_PREFIXES)


def refuse_local_provider_on_gateway():
    """#1995: a hosted world must send through the gateway. A saved
    Local/Custom provider (written before the hosted guard, or by hand) would
    send every request to that address instead, so the world refuses to start:
    exit 2 with one [SETUP] line on stderr, before any bind or request. Call
    it after take_from_argv; at import time the gateway is not known yet."""
    if _gateway is None:
        return
    import sys
    import model_config

    if model_config.get_provider() != "lmstudio":
        return
    print(
        "[SETUP] This world was started with %s, but its saved settings choose "
        "Local/Custom (model_provider \"lmstudio\" in %s). A hosted world must use "
        "the gateway. Set model_provider to openai, legacy or gemini in that file, "
        "or remove it, then start the world again."
        % (FLAG, model_config._USER_SETTINGS_FILE),
        file=sys.stderr,
    )
    sys.stderr.flush()
    raise SystemExit(2)
