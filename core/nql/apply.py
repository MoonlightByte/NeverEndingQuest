# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Subprocess bridge to the Firelight engine command (``bin/firelight-apply``).

One call, one process, one JSON document each way. The engine holds no state
between calls; the caller keeps the returned ``checkpoint`` and hands it back on
the next call. See Firelight's docs/PROTOCOL.md for the contract.
"""
import contextvars
import json
import os
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional

# #1253 MI-5: an attempt this long is ended and the same document sent again (B2 iii);
# only character creation's calls (on_timeout="raise", D-PKG-5) end on it.
DEFAULT_TIMEOUT_SECONDS = 30
# How often a running engine call checks for Load, Reset, Quit or a save stop.
_POLL_SECONDS = 0.25
SLOW_ENGINE_TEXT = "The rules engine is slow to answer; trying again..."
# A stop check for engine calls made outside a turn (the module builder tool's cancel).
engine_stop_check: contextvars.ContextVar = contextvars.ContextVar("engine_stop_check", default=None)


class EngineUnavailable(RuntimeError):
    """The engine binary is missing or did not produce a response."""


# #1382: the engine is being renamed; firelight-apply is looked for first and
# nql-apply stays the fallback until both names have shipped.
ENGINE_NAMES = ("firelight-apply", "nql-apply")


def _override() -> Optional[str]:
    return os.environ.get("FIRELIGHT_APPLY_BINARY") or os.environ.get("NQL_APPLY_BINARY") or None


def binary_path(repo_root: Optional[str] = None) -> str:
    override = _override()
    if override:
        return override
    root = repo_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    suffix = ".exe" if platform.system() == "Windows" else ""
    paths = [os.path.join(root, "bin", name + suffix) for name in ENGINE_NAMES]
    # Neither present: the nql-apply path, as before the rename.
    return next((path for path in paths if os.path.isfile(path)), paths[-1])


def call(document: Dict[str, Any], *, binary: Optional[str] = None, timeout: Optional[float] = DEFAULT_TIMEOUT_SECONDS,
         on_timeout: str = "reissue") -> Dict[str, Any]:
    """Run one engine invocation and return its decoded response.

    A response with ``ok`` false is returned, not raised: rejections, compile
    diagnostics and replay failures are outcomes the caller must handle.

    With ``on_timeout="reissue"`` (#1253 MI-5, B2 iii) a stuck call is sent again:
    an attempt past ``timeout`` seconds (None: no limit), a child killed by a
    signal or by any exit other than 0 or 2 without a JSON object, or a
    transient OSError at start. Each reissue shows SLOW_ENGINE_TEXT; there is no
    count. While it runs the call checks the turn's scope, a save stop and
    ``engine_stop_check``; a stop kills the child and is raised.
    EngineUnavailable is raised at once only for the bounded classes
    (D-1253mi5-1/3): a missing or unrunnable binary, an exit 0 whose reply is not
    a JSON object, and an exit 2 without one.

    ``on_timeout="raise"`` is creation's D-PKG-5 path, unchanged: one attempt, and a
    timeout raises EngineUnavailable from subprocess.TimeoutExpired.
    """
    exe = binary or binary_path()
    if not os.path.isfile(exe):
        if binary is None and _override() is None:
            raise EngineUnavailable("engine binary not found: bin/firelight-apply or bin/nql-apply "
                                    f"(looked in {os.path.dirname(exe)})")
        raise EngineUnavailable(f"engine binary not found: {exe}")
    if on_timeout == "reissue":
        return _call_reissuing(exe, json.dumps(document, ensure_ascii=True).encode("utf-8"), timeout)
    try:
        proc = subprocess.run(
            [exe],
            input=json.dumps(document, ensure_ascii=True).encode("utf-8"),
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EngineUnavailable(f"engine did not respond: {error}") from error
    try:
        response = json.loads(proc.stdout.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise EngineUnavailable(
            f"engine returned no JSON (exit {proc.returncode}): {proc.stderr.decode('utf-8', 'replace')}"
        ) from error
    if not isinstance(response, dict):
        raise EngineUnavailable("engine response is not an object")
    return response


def _check_stop() -> None:
    """Raise the stop that ends this call: the module builder's cancel, a save stop, or a superseded scope."""
    hook = engine_stop_check.get()
    if hook is not None:
        hook()
    from utils.capture.live_provider_call import _interruptible_wait, get_live_provider_scope
    _interruptible_wait(0, get_live_provider_scope(), "")


def _slow_engine_notice() -> None:
    """The status line before a reissue, then one poll interval (so a child that dies at once is not
    restarted in a tight loop), checking for a stop."""
    from utils.capture.live_provider_call import _emit_working, _safe_emit
    _safe_emit(_emit_working, SLOW_ENGINE_TEXT)
    _check_stop()
    time.sleep(_POLL_SECONDS)
    _check_stop()


def _attempt(exe: str, payload: bytes, timeout: Optional[float]):
    """One engine run: (stdout, stderr, exit code), or None once it has run ``timeout`` seconds.
    A stop, or anything else raised while it runs, kills and reaps the child first. A transient OSError at
    start returns None too, so the caller reissues; any other start error is EngineUnavailable."""
    from utils.transient_filesystem import is_transient_filesystem_error
    try:
        proc = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        if not is_transient_filesystem_error(error):
            raise EngineUnavailable(f"engine did not respond: {error}") from error
        return None
    started, first = time.monotonic(), True
    try:
        while True:
            _check_stop()
            try:
                out, err = proc.communicate(payload if first else None, timeout=_POLL_SECONDS)
                return out, err, proc.returncode
            except subprocess.TimeoutExpired:
                first = False
                if timeout is not None and time.monotonic() - started >= timeout:
                    _kill(proc)
                    return None
    except BaseException:
        _kill(proc)
        raise


def _kill(proc) -> None:
    if proc.poll() is None:
        proc.kill()
    try:
        proc.communicate()
    except (OSError, ValueError):
        pass


def _call_reissuing(exe: str, payload: bytes, timeout: Optional[float]) -> Dict[str, Any]:
    # A read-only save stop is an OSError; only the start's own errors are classified (in _attempt).
    while True:
        result = _attempt(exe, payload, timeout)
        if result is not None:
            out, err, code = result
            try:
                response = json.loads(out.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                response = None
            if isinstance(response, dict):
                return response
            if code in (0, 2):
                # D-1253mi5-1/3: the engine answered this document without a JSON object; the same
                # document gets the same answer, so this is a bounded class, not a stuck call.
                if response is None:
                    raise EngineUnavailable(f"engine returned no JSON (exit {code}): {err.decode('utf-8', 'replace')}")
                raise EngineUnavailable("engine response is not an object")
        _slow_engine_notice()


def genesis(world_source: str, *, explain: Optional[List[Dict[str, str]]] = None,
            status: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
    doc: Dict[str, Any] = {"world": world_source, "world_name": "genesis.nql"}
    if explain:
        doc["explain"] = explain
    if status:
        doc["status"] = status
    return call(doc, **kwargs)


def execute(checkpoint: Dict[str, Any], actions: str, actor_id: str, request_id: str, *,
            expected_revision: Optional[int] = None, views: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "checkpoint": checkpoint,
        "actions": actions,
        "actions_name": "actions.nql",
        "actor": {"kind": "character", "id": actor_id},
        "request": request_id,
    }
    if expected_revision is not None:
        doc["expected_revision"] = expected_revision
    if views:
        doc.update(views)
    return call(doc, **kwargs)


def observe(checkpoint: Dict[str, Any], views: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    doc: Dict[str, Any] = {"checkpoint": checkpoint}
    doc.update(views)
    return call(doc, **kwargs)
