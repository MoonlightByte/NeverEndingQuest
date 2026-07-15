"""Crash-releasing cross-process lock for module refresh/reconciliation."""

from __future__ import annotations

import os
from contextlib import contextmanager

from utils.path_transaction_lock import path_transaction_lock

LOCK_FILE = "modules/module_refresh.lock"


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


@contextmanager
def module_refresh_lock(max_wait_seconds: float = 5.0, poll_seconds: float = 0.05):
    # Advisory OS locks are released automatically when a worker dies. The
    # former O_EXCL sentinel could survive a crash forever and prevented the
    # very recovery operation that needed this boundary.  LOCK_FILE remains
    # only the logical identity: an old sentinel at that path is deliberately
    # ignored while the adjacent advisory lock controls ownership.
    _ensure_parent(LOCK_FILE)
    with path_transaction_lock(
        LOCK_FILE,
        suffix=".advisory.lock",
        timeout_seconds=max_wait_seconds,
        poll_seconds=poll_seconds,
    ) as acquired:
        yield acquired is not None
