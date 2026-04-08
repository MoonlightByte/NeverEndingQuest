"""Cross-process lock helper for module refresh writes."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager

LOCK_FILE = "modules/module_refresh.lock"


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


@contextmanager
def module_refresh_lock(max_wait_seconds: float = 5.0, poll_seconds: float = 0.05):
    _ensure_parent(LOCK_FILE)
    deadline = time.time() + max_wait_seconds
    acquired = False
    while time.time() < deadline:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            os.close(fd)
            acquired = True
            break
        except FileExistsError:
            time.sleep(poll_seconds)

    if not acquired:
        yield False
        return

    try:
        yield True
    finally:
        try:
            os.remove(LOCK_FILE)
        except FileNotFoundError:
            pass
