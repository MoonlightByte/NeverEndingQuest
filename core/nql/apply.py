# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Subprocess bridge to the ``nql-apply`` engine command.

One call, one process, one JSON document each way. The engine holds no state
between calls; the caller keeps the returned ``checkpoint`` and hands it back on
the next call. See the engine's ``cmd/nql-apply`` for the contract.
"""
import json
import os
import platform
import subprocess
from typing import Any, Dict, List, Optional

DEFAULT_TIMEOUT_SECONDS = 30


class EngineUnavailable(RuntimeError):
    """The engine binary is missing or did not produce a response."""


def binary_path(repo_root: Optional[str] = None) -> str:
    override = os.environ.get("NQL_APPLY_BINARY")
    if override:
        return override
    root = repo_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    name = "nql-apply.exe" if platform.system() == "Windows" else "nql-apply"
    return os.path.join(root, "bin", name)


def call(document: Dict[str, Any], *, binary: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Run one engine invocation and return its decoded response.

    Raises EngineUnavailable when the process cannot run or returns no JSON.
    A response with ``ok`` false is returned, not raised: rejections, compile
    diagnostics and replay failures are outcomes the caller must handle.
    """
    exe = binary or binary_path()
    if not os.path.isfile(exe):
        raise EngineUnavailable(f"engine binary not found: {exe}")
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
            f"engine returned no JSON (exit {proc.returncode}): {proc.stderr.decode('utf-8', 'replace')[:400]}"
        ) from error
    if not isinstance(response, dict):
        raise EngineUnavailable("engine response is not an object")
    return response


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
