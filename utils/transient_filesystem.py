"""Narrow classification and retry helpers for transient filesystem races,
and the one verdict that a denied write is not transient (a read-only target)."""

from __future__ import annotations

import errno
import os
from pathlib import Path
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
