"""Small transactional JSON-mapping store for shared runtime caches.

Cache files are still disposable, but concurrent workers must not corrupt them
or erase each other's entries. This module serializes each read/modify/write
transaction across threads, instances, and processes, then commits with a
unique temporary file and ``os.replace``.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


_PROCESS_LOCKS = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def _process_lock(path: Path):
    absolute = str(path.resolve())
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(absolute, threading.RLock())


@contextmanager
def _locked_path(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(f"{path}.lock")
    with _process_lock(path):
        with lock_path.open("a+b") as lock_file:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield path
            finally:
                if os.name == "nt":
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_mapping_unlocked(path: Path):
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        quarantine = Path(f"{path}.corrupt-{stamp}-{uuid4().hex}")
        os.replace(path, quarantine)
        return {}


def _write_mapping_unlocked(path: Path, value):
    temporary = Path(
        f"{path}.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}.tmp"
    )
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_json_mapping(path):
    """Return a locked snapshot of a JSON object, or an empty object."""
    with _locked_path(path) as locked_path:
        return dict(_read_mapping_unlocked(locked_path))


def merge_json_mapping(path, updates=None, remove_keys=()):
    """Atomically merge entries/removals and return the committed mapping."""
    updates = dict(updates or {})
    remove_keys = tuple(remove_keys)
    with _locked_path(path) as locked_path:
        current = _read_mapping_unlocked(locked_path)
        for key in remove_keys:
            current.pop(key, None)
        current.update(updates)
        if updates or remove_keys:
            _write_mapping_unlocked(locked_path, current)
        return dict(current)


def replace_json_mapping(path, value):
    """Atomically replace a cache mapping and return a detached copy."""
    value = dict(value)
    with _locked_path(path) as locked_path:
        _write_mapping_unlocked(locked_path, value)
    return dict(value)
