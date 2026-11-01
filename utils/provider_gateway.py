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
