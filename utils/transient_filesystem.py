"""Narrow classification and retry helpers for transient filesystem races,
and the one verdict that a denied write is not transient (a read-only target)."""

from __future__ import annotations

import errno
import logging
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
        # B1 busy = wait: running a program while it is rewritten (a game update
        # replacing the engine binary) or opening a running one for writing.
        getattr(errno, "ETXTBSY", None),
    )
    if value is not None
)
_TRANSIENT_WINDOWS_ERRORS = frozenset({32, 33})

# A rename that another program blocks is retried every 0.1 s, as before. It is
# reported after a short grace and then on a heartbeat (#653 item 6).
REPLACE_CONTENTION_SLEEP_SECONDS = 0.1
REPLACE_CONTENTION_GRACE_SECONDS = 2.0
REPLACE_CONTENTION_HEARTBEAT_SECONDS = 10.0

_LOGGER = logging.getLogger(__name__)


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


def scandir_names(dirname, wait, *, pattern, dironly=False):
    """The names glob would list in ``dirname``, and whether the listing completed.

    Glob's name rule: no leading ".", and ``pattern`` matched under
    ``os.path.normcase``; with ``dironly`` only directories. A busy listing
    (anywhere in the iteration, ``is_dir()`` included) drops what it has,
    calls ``wait()`` and lists again from scratch; ``wait`` is a no-argument
    callable and a stop it raises propagates. A non-transient error keeps the
    names listed so far, as glob does, and returns ``complete`` False, as does
    an entry skipped because its ``is_dir()`` failed.
    """
    import fnmatch

    match = os.path.normcase(pattern)
    while True:
        names = []
        complete = True
        try:
            with os.scandir(dirname) as listing:
                for item in listing:
                    if item.name.startswith("."):
                        continue
                    if dironly:
                        try:
                            if not item.is_dir():
                                continue
                        except ReadOnlySaveStop:
                            raise
                        except OSError as exc:
                            if is_transient_filesystem_error(exc):
                                raise
                            complete = False
                            continue
                    if fnmatch.fnmatchcase(os.path.normcase(item.name), match):
                        names.append(item.name)
            return names, complete
        except ReadOnlySaveStop:
            raise
        except OSError as exc:
            if not is_transient_filesystem_error(exc):
                return names, False
        wait()


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


# The waiting lines on screen now, by line, so a wait that ends after the one
# whose line it covered restores what that one covered (#803).
_SHOWN_LINES = {}
_SHOWN_LINES_GUARD = threading.Lock()


class ReplaceContention:
    """One writer's wait while another program blocks its rename (#653 item 6).

    Windows refuses the rename (WinError 5/32) while a scanner, a sync client
    or another program holds the target. The write is never given up on a
    timer. ``tick`` waits one step; after a short grace it logs a warning, and
    during a live turn it shows one status line, both on a heartbeat.
    ``finish`` puts the earlier status back if that line is still showing.
    A read-only stop recorded during the wait ends it, except for a writer
    that passed on_read_only="fail" (``check_save_stop`` False, #654).
    """

    def __init__(self, filepath, check_save_stop: bool = True):
        self._path = os.fsdecode(filepath)
        self._check_save_stop = check_save_stop
        self._started = None
        self._next_report = None
        self._line = None
        self._previous = None
        self._previous_owner = None

    def tick(self, winerror=None) -> None:
        if self._check_save_stop:
            raise_if_save_stopped()
        now = time.monotonic()
        if self._started is None:
            self._started = now
            self._next_report = now + REPLACE_CONTENTION_GRACE_SECONDS
        elif now >= self._next_report:
            self._next_report = now + REPLACE_CONTENTION_HEARTBEAT_SECONDS
            self._report(now - self._started, winerror)
        time.sleep(REPLACE_CONTENTION_SLEEP_SECONDS)

    def _report(self, elapsed, winerror) -> None:
        _LOGGER.warning(
            "Waiting to save %s: the rename is refused (WinError %s) for %.0f s, "
            "another program holds the file; still retrying",
            self._path, winerror, elapsed,
        )
        self._show_line(
            "Waiting to save %s: another program on this computer is using "
            "it. Closing that program lets the game continue."
            % os.path.basename(self._path)
        )

    def _show_line(self, line) -> None:
        try:
            # Only a live turn shows the line: outside one, nothing would clear
            # the processing flag after the write lands.
            from utils.capture.live_provider_call import get_live_turn_scope

            if get_live_turn_scope() is None:
                return
            from core.managers.status_manager import status_manager

            # Restore what was showing before this line: a status that came in
            # since the last line is the newer one to put back.
            current = status_manager.get_status()
            if self._line is None or current[0] != self._line:
                self._previous = current
                with _SHOWN_LINES_GUARD:
                    owner = _SHOWN_LINES.get(current[0])
                self._previous_owner = owner if owner is not self else None
            status_manager.update_status(line, True)
            self._line = line
            with _SHOWN_LINES_GUARD:
                _SHOWN_LINES[line] = self
        except Exception:  # noqa: BLE001 - a status line never breaks a save
            pass

    def finish(self) -> None:
        line, self._line = self._line, None
        if line is None or self._previous is None:
            return
        with _SHOWN_LINES_GUARD:
            if _SHOWN_LINES.get(line) is self:
                del _SHOWN_LINES[line]
            # A covered wait that has ended too hands on what it covered.
            previous, owner, seen = self._previous, self._previous_owner, {id(self)}
            while owner is not None and owner._line is None and id(owner) not in seen:
                seen.add(id(owner))
                previous, owner = owner._previous, owner._previous_owner
        try:
            from core.managers.status_manager import status_manager

            if status_manager.get_status()[0] == line:
                message, processing = previous
                status_manager.update_status(message, processing)
        except Exception:  # noqa: BLE001 - a status line never breaks a save
            pass


class LockContention(ReplaceContention):
    """One writer's wait for a file lock another part of the game holds (#803).

    The lock is reentrant per thread, so the holder is another thread or
    another copy of the game open on the same folder. The wait is never given
    up on a timer, and the lock call itself waits each step, so ``tick`` does
    not sleep. After the same grace it logs a warning on the heartbeat; a
    ``wait_reporter`` (Save's or Load's own waiting line) is called instead
    of the status line, and without one a live turn shows one line. A read-only
    stop recorded during the wait ends it only when ``check_save_stop`` is
    set, which write_json does for its own lock.
    """

    def __init__(self, filepath, check_save_stop: bool = False, wait_reporter=None):
        super().__init__(filepath, check_save_stop)
        self._wait_reporter = wait_reporter

    def tick(self, winerror=None) -> None:
        if self._check_save_stop:
            raise_if_save_stopped()
        now = time.monotonic()
        if self._started is None:
            self._started = now
            self._next_report = now + REPLACE_CONTENTION_GRACE_SECONDS
            return
        elapsed = now - self._started
        if elapsed < REPLACE_CONTENTION_GRACE_SECONDS:
            return
        if self._wait_reporter is not None:
            try:
                self._wait_reporter(elapsed)
            except Exception:  # noqa: BLE001 - a status line never breaks a save
                pass
        if now >= self._next_report:
            self._next_report = now + REPLACE_CONTENTION_HEARTBEAT_SECONDS
            self._report(elapsed, winerror)

    def _report(self, elapsed, winerror) -> None:
        _LOGGER.warning(
            "Waiting to save %s: another part of the game has held its lock "
            "for %.0f s; still waiting",
            self._path, elapsed,
        )
        if self._wait_reporter is None:
            self._show_line(
                "Waiting to save %s: another part of the game is still saving it."
                % os.path.basename(self._path)
            )


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
