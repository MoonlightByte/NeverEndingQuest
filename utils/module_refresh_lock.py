"""Crash-releasing cross-process lock for module refresh/reconciliation."""

from __future__ import annotations

import os
from contextlib import contextmanager

from utils.path_transaction_lock import (
    path_transaction_lock,
    path_transaction_lock_owned,
)


GAME_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
)
RUNTIME_LOCKS_DIR = os.path.join(GAME_ROOT, ".runtime_locks")
LOCK_FILE = os.path.join(RUNTIME_LOCKS_DIR, "module_refresh")
LOCK_SUFFIX = ".advisory.lock"


class ModuleRefreshLockOwnershipError(RuntimeError):
    """Raised when a locked-only API is called without refresh ownership."""


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def module_refresh_lock_owned() -> bool:
    """Return whether the current thread owns the global refresh boundary."""
    return path_transaction_lock_owned(LOCK_FILE, suffix=LOCK_SUFFIX)


def assert_module_refresh_lock_owned() -> None:
    """Fail closed unless the current thread owns module refresh."""
    if not module_refresh_lock_owned():
        raise ModuleRefreshLockOwnershipError(
            "The current thread does not own module refresh"
        )


@contextmanager
def module_refresh_lock(max_wait_seconds: float = 5.0, poll_seconds: float = 0.05,
                        wait_callback=None):
    # Advisory OS locks are released automatically when a worker dies. The
    # former O_EXCL sentinel could survive a crash forever and prevented the
    # very recovery operation that needed this boundary.  LOCK_FILE remains
    # only the logical identity: an old sentinel at that path is deliberately
    # ignored while the adjacent advisory lock controls ownership.
    #
    # IMPORTANT DEPLOYMENT CONTRACT: this absolute, game-root-derived identity
    # replaces the historical ``modules/module_refresh.lock.advisory.lock``.
    # Every worker must be stopped before deploying this change and restarted
    # from the same version. Mixed old/new workers would lock different inodes
    # and are therefore unsupported. The advisory file is persistent by
    # design; unlinking it after release can split waiters and newcomers across
    # two inodes.
    _ensure_parent(LOCK_FILE)
    with path_transaction_lock(
        LOCK_FILE,
        suffix=LOCK_SUFFIX,
        timeout_seconds=max_wait_seconds,
        poll_seconds=poll_seconds,
        wait_callback=wait_callback,
    ) as acquired:
        yield acquired is not None
