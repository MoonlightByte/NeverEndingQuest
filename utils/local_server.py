# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Start-up pieces for a server run by the desktop shell or a world supervisor
(#1681, #1682). With none of their flags or variables set, nothing here runs.

- local_token(): the per-launch token from NEQ_LOCAL_TOKEN. Set means every
  request must carry it (header X-NEQ-Local-Token) and the server binds
  127.0.0.1 only; set but empty is refused, so a launcher bug can never open
  an unguarded server.
- desktop_mode(): NEQ_DESKTOP=1, which switches the update notices to "updates
  come through the app".
- bind_listen(): bind first, then serve. --port N binds N (0 = a free port);
  --port-or-free N binds N and falls back to a free port only if N is taken.
- port file: <data root>/run/port, {"port": n, "pid": n}, deleted at start and
  written temp + rename once the socket is bound.
- LocalGuard: WSGI middleware in front of everything (socket.io included)
  that checks the token and the Host header.
"""

import errno
import hmac
import json
import os
import socket
import sys

TOKEN_HEADER = "X-NEQ-Local-Token"
UPDATES_THROUGH_APP = "Updates come through the app."


class EmptyLocalToken(RuntimeError):
    pass


def local_token():
    """The launch token, None when NEQ_LOCAL_TOKEN is not set; set but empty raises."""
    if "NEQ_LOCAL_TOKEN" not in os.environ:
        return None
    token = os.environ["NEQ_LOCAL_TOKEN"].strip()
    if not token:
        raise EmptyLocalToken("NEQ_LOCAL_TOKEN is set but empty; refusing to start an unguarded server.")
    return token


def desktop_mode():
    return os.environ.get("NEQ_DESKTOP", "").strip() == "1"


def prompts_allowed():
    """input() may be used only on an interactive console outside desktop mode."""
    if desktop_mode():
        return False
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def bind_listen(port, or_free=False, host="127.0.0.1"):
    """A listening socket on host:port; with or_free, a free port if port is taken."""
    def attempt(p):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name != "nt":
            # Lets a relaunch reuse a port still in TIME_WAIT; a port another
            # program is listening on stays taken. (On Windows this option
            # would let two servers share a port, so it is not set there.)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, p))
            sock.listen(128)
        except OSError:
            sock.close()
            raise
        return sock

    try:
        return attempt(port)
    except OSError as exc:
        in_use = exc.errno in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", -1), 10048)
        if or_free and port != 0 and in_use:
            return attempt(0)
        raise


def port_file_path(root=None):
    return os.path.join(os.path.abspath(root or os.getcwd()), "run", "port")


def clear_port_file(root=None):
    try:
        os.remove(port_file_path(root))
    except FileNotFoundError:
        pass


def write_port_file(port, root=None):
    path = port_file_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    partial = path + ".tmp"
    with open(partial, "w", encoding="utf-8") as fh:
        json.dump({"port": int(port), "pid": os.getpid()}, fh)
    os.replace(partial, path)
    return path


class LocalGuard:
    """Refuse any request without the launch token or with a foreign Host header."""

    def __init__(self, app, token, port_getter):
        self.app = app
        self.token = token.encode("utf-8")
        self.port_getter = port_getter

    def _host_ok(self, host):
        port = self.port_getter()
        if not host or port is None:
            return False
        return host in ("127.0.0.1:%d" % port, "localhost:%d" % port)

    def __call__(self, environ, start_response):
        supplied = environ.get("HTTP_X_NEQ_LOCAL_TOKEN", "").encode("utf-8")
        if not (supplied and hmac.compare_digest(supplied, self.token)
                and self._host_ok(environ.get("HTTP_HOST", ""))):
            body = b"Forbidden"
            start_response("403 Forbidden", [("Content-Type", "text/plain"),
                                             ("Content-Length", str(len(body)))])
            return [body]
        return self.app(environ, start_response)
