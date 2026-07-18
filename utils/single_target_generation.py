"""Cross-thread/process transactions for one generated file identity.

The lock covers the complete check -> model generation -> save sequence.  Its
persistent metadata remembers the actual output path when a generator is
allowed to clean or canonicalize the requested name.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import BinaryIO, Dict, Iterator, Optional

from jsonschema import SchemaError, ValidationError, validate


_locks_guard = threading.Lock()
_target_locks: Dict[str, threading.RLock] = {}


def _thread_lock(target_path: str) -> threading.RLock:
    canonical = os.path.abspath(os.path.normpath(str(target_path)))
    with _locks_guard:
        return _target_locks.setdefault(canonical, threading.RLock())


def _lock_file(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_resolved_target(handle: BinaryIO) -> Optional[str]:
    try:
        handle.seek(0)
        raw = handle.read().decode("utf-8").strip("\0 \t\r\n")
        value = json.loads(raw) if raw else {}
        target = value.get("resolved_target") if isinstance(value, dict) else None
        if isinstance(target, str) and target.strip():
            return os.path.abspath(os.path.normpath(target))
    except (UnicodeError, json.JSONDecodeError, OSError, ValueError):
        pass
    return None


def load_valid_generated_target(target_path: str, schema: dict) -> Optional[dict]:
    """Load an existing generated object only when it still satisfies schema."""
    try:
        with open(target_path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            return None
        validate(instance=value, schema=schema)
        return value
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError, SchemaError):
        return None


@dataclass
class TargetGenerationTransaction:
    """State exposed while one logical generated target is exclusively held."""

    logical_target: str
    resolved_target: Optional[str]
    _handle: BinaryIO

    def remember_target(self, target_path: str) -> None:
        """Persist the intended physical target before releasing the lock."""
        canonical = os.path.abspath(os.path.normpath(str(target_path)))
        payload = json.dumps({"resolved_target": canonical}).encode("utf-8")
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(payload)
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.resolved_target = canonical


@contextmanager
def single_target_generation(
    logical_target: str,
) -> Iterator[TargetGenerationTransaction]:
    """Exclusively hold one logical target across threads and processes."""
    canonical = os.path.abspath(os.path.normpath(str(logical_target)))
    parent = os.path.dirname(canonical)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lock_path = f"{canonical}.generation.lock"

    with _thread_lock(canonical):
        with open(lock_path, "a+b") as handle:
            _lock_file(handle)
            try:
                yield TargetGenerationTransaction(
                    logical_target=canonical,
                    resolved_target=_read_resolved_target(handle),
                    _handle=handle,
                )
            finally:
                _unlock_file(handle)
