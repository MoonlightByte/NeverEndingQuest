"""Narrow classification and retry helpers for transient filesystem races,
and the one verdict that a denied write is not transient (a read-only target)."""

from __future__ import annotations

import errno
import os
from pathlib import Path
import threading
import time
from typing import Callable, TypeVar


TRANSIENT_FILESYSTEM_ATTEMPTS = 3
TRANSIENT_FILESYSTEM_BACKOFF_SECONDS = 0.05

_TRANSIENT_ERRNOS = frozenset(
    value
    for value in (
        errno.EAGAIN,
        errno.EBUSY,
        errno.EINTR,
        getattr(errno, "ESTALE", None),
        getattr(errno, "ETIMEDOUT", None),
    )
    if value is not None
)
_TRANSIENT_WINDOWS_ERRORS = frozenset({32, 33})


def is_transient_filesystem_error(
    exc: BaseException,
    *,
    allow_missing: bool = False,
) -> bool:
    """Return whether one I/O failure is safe to retry without guessing.

    General access denial is intentionally excluded: only Windows sharing and
    lock violations, well-known temporary POSIX errors, and an explicitly
    contextualized disappearance are retryable.
    """
    if not isinstance(exc, OSError):
        return False
    if allow_missing and isinstance(exc, FileNotFoundError):
        return True
    return (
        getattr(exc, "winerror", None) in _TRANSIENT_WINDOWS_ERRORS
        or getattr(exc, "errno", None) in _TRANSIENT_ERRNOS
    )


ResultT = TypeVar("ResultT")


def read_bytes_preserving_errors(path) -> bytes:
    """Read complete bytes without collapsing native Windows lock errors.

    No retry or ownership policy lives here. Callers retain their existing
    path validation, cancellation and transient-error handling.
    """
    if os.name != "nt":
        return Path(path).read_bytes()
    import _winapi
    import ctypes

    handle = _winapi.CreateFile(
        os.fsdecode(path), 0x80000000, 3, 0, 3, 0x80, 0,
    )  # read-only, share read/write, non-inherited, OPEN_EXISTING
    try:
        chunks = []
        while True:
            chunk, error_code = _winapi.ReadFile(handle, 64 * 1024)
            if error_code:
                raise ctypes.WinError(error_code)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        _winapi.CloseHandle(handle)


def replace_target_is_read_only(path) -> bool:
    """Return whether a native Windows target carries the READONLY attribute.

    The single home for the READONLY-attribute verdict used by the waiting
    writer loops: waiting cannot clear it, so an opted-in writer stops on it
    (issue #654). One attribute read, no handle and no retry. Anything that is
    not provably a read-only file answers False, including an unreadable
    attribute (a delete-pending name) and a directory. POSIX answers False.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        get_attributes = ctypes.WinDLL("kernel32").GetFileAttributesW
        get_attributes.argtypes = [wintypes.LPCWSTR]
        get_attributes.restype = wintypes.DWORD
        attributes = get_attributes(os.fsdecode(path))
    except Exception:
        return False
    if attributes == 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
        return False
    # FILE_ATTRIBUTE_READONLY, and not FILE_ATTRIBUTE_DIRECTORY.
    return bool(attributes & 0x1) and not attributes & 0x10


# What a shared writer loop does when its target is read-only (issue #654).
# "stop" (the default) records the save stop and raises ReadOnlySaveStop, and
# the session ends. "raise" re-raises the plain replace error and records
# nothing, for a caller that handles it. "fail" does the same for a file that
# is not game state, and its caller reports the failure as it does today.
# Once a stop is recorded, "stop" and "raise" saves write nothing and raise
# ReadOnlySaveStop at once; only "fail" saves still run. A caller chooses
# "raise" or "fail" by passing the keyword; nothing is inferred from the path.
ON_READ_ONLY_STOP = "stop"
ON_READ_ONLY_RAISE = "raise"
ON_READ_ONLY_FAIL = "fail"
_ON_READ_ONLY_MODES = frozenset({ON_READ_ONLY_STOP, ON_READ_ONLY_RAISE, ON_READ_ONLY_FAIL})


class ReadOnlySaveStop(PermissionError):
    """A game-state save met a read-only target, so the session stops.

    Raised by the shared writer loops instead of waiting forever, and by every
    later save while the stop is recorded, so nothing is written after it.
    """

    def __init__(self, path):
        path = os.fsdecode(path)
        super().__init__(errno.EACCES, "The file is read-only", path, 5)
        self.path = path


_save_stop_lock = threading.Lock()
_save_stop_path = None


def check_on_read_only(mode) -> str:
    """Return a valid ``on_read_only`` mode, or raise ValueError."""
    if mode not in _ON_READ_ONLY_MODES:
        raise ValueError(f"unknown on_read_only mode: {mode!r}")
    return mode


def record_save_stop(path) -> str:
    """Record the first read-only save of this process; return the recorded path."""
    global _save_stop_path
    with _save_stop_lock:
        if _save_stop_path is None:
            _save_stop_path = os.path.abspath(os.fsdecode(path))
        return _save_stop_path


def save_stop_path():
    """Return the recorded read-only path, or None while saves may run."""
    with _save_stop_lock:
        return _save_stop_path


def clear_save_stop() -> None:
    """Forget the recorded stop when a new game session begins."""
    global _save_stop_path
    with _save_stop_lock:
        _save_stop_path = None


def raise_if_save_stopped() -> None:
    """Raise ReadOnlySaveStop while a stop is recorded."""
    path = save_stop_path()
    if path is not None:
        raise ReadOnlySaveStop(path)


def retry_transient_filesystem(
    operation: Callable[[], ResultT],
    *,
    attempts: int = TRANSIENT_FILESYSTEM_ATTEMPTS,
    allow_missing: bool = False,
    backoff_seconds: float = TRANSIENT_FILESYSTEM_BACKOFF_SECONDS,
) -> ResultT:
    """Retry one idempotent operation within a fixed small attempt bound."""
    if type(attempts) is not int or attempts < 1:
        raise ValueError("filesystem retry attempts must be positive")
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except OSError as exc:
            if attempt == attempts or not is_transient_filesystem_error(
                exc,
                allow_missing=allow_missing,
            ):
                raise
            time.sleep(backoff_seconds * attempt)
    raise AssertionError("unreachable filesystem retry state")
