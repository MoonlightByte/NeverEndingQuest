"""Path-scoped transaction locks shared by threads and worker processes.

The advisory lock file lives beside the protected target so workers that share
the target also share the lock.  Callers choose the logical path identity; the
target itself does not need to exist yet.
"""

from __future__ import annotations

import os
import errno
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from utils.transient_filesystem import (
    TRANSIENT_FILESYSTEM_ATTEMPTS,
    is_transient_filesystem_error,
)


_THREAD_LOCKS = {}
_THREAD_LOCKS_GUARD = threading.Lock()
_ACTIVE_LOCK_FILES = set()
_ACTIVE_LOCK_FILES_GUARD = threading.RLock()
_WINDOWS_LOCK_RETRY_SECONDS = 0.05


def _notify_wait(wait_callback, wait_started) -> None:
    if wait_callback is None:
        return
    try:
        wait_callback(time.monotonic() - wait_started)
    except Exception:
        pass


def _prepare_for_fork() -> None:
    """Freeze open/close registration across the fork boundary."""
    _ACTIVE_LOCK_FILES_GUARD.acquire()


def _resume_after_fork_parent() -> None:
    _ACTIVE_LOCK_FILES_GUARD.release()


def _reset_after_fork() -> None:
    """Close inherited advisory handles and discard parent thread state."""
    global _ACTIVE_LOCK_FILES, _ACTIVE_LOCK_FILES_GUARD
    global _THREAD_LOCKS, _THREAD_LOCKS_GUARD
    # A flock is tied to its open-file description.  Without closing the
    # child's inherited copies, a freshly opened descriptor can contend with
    # a lock that no surviving child thread can release.  Track Python file
    # objects (rather than bare fd numbers) so later fd reuse cannot make an
    # inherited context close or unlock an unrelated file.
    for lock_file in tuple(_ACTIVE_LOCK_FILES):
        try:
            lock_file.close()
        except Exception:
            pass
    _ACTIVE_LOCK_FILES = set()
    # The inherited registry guard was deliberately locked by the before
    # hook.  Replace it; releasing a parent-owned lock in the child is unsafe.
    _ACTIVE_LOCK_FILES_GUARD = threading.RLock()
    _THREAD_LOCKS = {}
    _THREAD_LOCKS_GUARD = threading.Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_prepare_for_fork,
        after_in_parent=_resume_after_fork_parent,
        after_in_child=_reset_after_fork,
    )


@dataclass
class _PathLockState:
    """Process-local state for one advisory lock identity."""

    thread_lock: threading.RLock = field(default_factory=threading.RLock)
    local: threading.local = field(default_factory=threading.local)


def _lock_state(target_path: str, suffix: str) -> _PathLockState:
    identity = (target_path, suffix)
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(identity, _PathLockState())


def path_transaction_lock_owned(
    target_path,
    *,
    suffix=".transaction.lock",
) -> bool:
    """Return whether the current thread owns this exact lock identity.

    Ownership is deliberately thread-scoped, not merely process-scoped.  A
    sibling thread must not be able to call an API whose ``*_locked`` contract
    is protected by another thread's advisory descriptor.  The at-fork reset
    above discards inherited state, so a child never inherits this authority.
    """
    canonical = os.path.abspath(os.path.normpath(os.fspath(target_path)))
    state = _lock_state(canonical, suffix)
    return getattr(state.local, "depth", 0) > 0


def _wait_to_retry(deadline, poll_seconds: float, wait_callback=None,
                   wait_started=None) -> bool:
    """Sleep only within the caller's acquisition budget."""
    if deadline is None:
        time.sleep(poll_seconds)
        _notify_wait(wait_callback, wait_started)
        return True
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return False
    time.sleep(min(poll_seconds, remaining))
    _notify_wait(wait_callback, wait_started)
    return deadline - time.monotonic() > 0


def _lock_windows_file(
    lock_file,
    msvcrt_module=None,
    *,
    deadline=None,
    poll_seconds: float = _WINDOWS_LOCK_RETRY_SECONDS,
    wait_callback=None,
    wait_started=None,
) -> bool:
    """Wait for a Windows byte-range lock without LK_LOCK's ten-try cap."""
    if msvcrt_module is None:
        import msvcrt as msvcrt_module

    lock_file.seek(0, os.SEEK_END)
    if lock_file.tell() == 0:
        lock_file.write(b"\0")
        lock_file.flush()

    while True:
        lock_file.seek(0)
        try:
            msvcrt_module.locking(
                lock_file.fileno(),
                msvcrt_module.LK_NBLCK,
                1,
            )
            return True
        except OSError as exc:
            # CPython reports byte-range contention as EACCES/EAGAIN (and on
            # some Windows runtimes ERROR_LOCK_VIOLATION).  Retry only those
            # conditions so invalid handles and permission errors still fail.
            retryable_errno = getattr(exc, "errno", None) in {11, 13, 36}
            retryable_winerror = getattr(exc, "winerror", None) in {33, 36}
            if not (retryable_errno or retryable_winerror):
                raise
            if not _wait_to_retry(
                deadline, poll_seconds, wait_callback, wait_started
            ):
                return False


def _lock_file(lock_file, *, deadline=None, poll_seconds: float = 0.05,
               wait_callback=None, wait_started=None) -> bool:
    if os.name == "nt":
        return _lock_windows_file(
            lock_file,
            deadline=deadline,
            poll_seconds=poll_seconds,
            wait_callback=wait_callback,
            wait_started=wait_started,
        )
    else:
        import fcntl

        if deadline is None and wait_callback is None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            return True
        while True:
            try:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
                return True
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                    raise
                if not _wait_to_retry(
                    deadline, poll_seconds, wait_callback, wait_started
                ):
                    return False


def _open_lock_file(lock_path, *, deadline=None, poll_seconds: float = 0.05,
                    wait_callback=None, wait_started=None):
    """Open the persistent lock identity within the acquisition budget."""
    def windows_opener(path, flags):
        # A native lockfile probe exposed CRT open() collapsing WinError 32 to
        # EACCES without winerror. Preserve the actual error, rather than
        # treating all permission denials as transient sharing contention.
        import ctypes
        from ctypes import wintypes
        import msvcrt

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = (
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        )
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateFileW(
            os.fsdecode(path),
            0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
            1 | 2,  # FILE_SHARE_READ | FILE_SHARE_WRITE; do not unlink held locks
            None, 4, 0x80, None,  # non-inherited, OPEN_ALWAYS, normal attributes
        )
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return msvcrt.open_osfhandle(
                handle, os.O_RDWR | os.O_APPEND | os.O_BINARY | os.O_NOINHERIT
            )
        except BaseException:
            kernel.CloseHandle(handle)
            raise

    attempts = 0
    while True:
        try:
            return open(
                lock_path, "a+b", opener=windows_opener if os.name == "nt" else None
            )
        except OSError as exc:
            attempts += 1
            if not is_transient_filesystem_error(exc):
                raise
            if deadline is not None and attempts >= TRANSIENT_FILESYSTEM_ATTEMPTS:
                raise
            if not _wait_to_retry(
                deadline, poll_seconds, wait_callback, wait_started
            ):
                return None


def _unlock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def path_transaction_lock(
    target_path,
    *,
    suffix=".transaction.lock",
    timeout_seconds=None,
    poll_seconds: float = 0.05,
    wait_callback=None,
):
    """Exclusively hold one logical target across threads and processes.

    Locks are scoped to the canonical target path plus ``suffix``.  Distinct
    targets therefore remain independent and can be processed concurrently.
    """
    canonical = os.path.abspath(os.path.normpath(os.fspath(target_path)))
    lock_path = f"{canonical}{suffix}"
    parent = os.path.dirname(lock_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if timeout_seconds is not None:
        timeout_seconds = max(0.0, float(timeout_seconds))
    poll_seconds = max(0.001, float(poll_seconds))
    deadline = (
        None
        if timeout_seconds is None
        else time.monotonic() + timeout_seconds
    )

    wait_started = time.monotonic()
    state = _lock_state(canonical, suffix)
    if deadline is None and wait_callback is None:
        thread_acquired = state.thread_lock.acquire()
    elif deadline is None:
        thread_acquired = False
        while not thread_acquired:
            thread_acquired = state.thread_lock.acquire(timeout=poll_seconds)
            if not thread_acquired:
                _notify_wait(wait_callback, wait_started)
    else:
        thread_acquired = state.thread_lock.acquire(
            timeout=max(0.0, deadline - time.monotonic())
        )
    if not thread_acquired:
        yield None
        return
    try:
        depth = getattr(state.local, "depth", 0)
        if depth:
            state.local.depth = depth + 1
            try:
                yield canonical
            finally:
                state.local.depth -= 1
            return

        lock_file = _open_lock_file(
            lock_path,
            deadline=deadline,
            poll_seconds=poll_seconds,
            wait_callback=wait_callback,
            wait_started=wait_started,
        )
        if lock_file is None:
            yield None
            return
        with _ACTIVE_LOCK_FILES_GUARD:
            _ACTIVE_LOCK_FILES.add(lock_file)
        owner_pid = os.getpid()
        locked = False
        try:
            locked = _lock_file(
                lock_file,
                deadline=deadline,
                poll_seconds=poll_seconds,
                wait_callback=wait_callback,
                wait_started=wait_started,
            )
            if not locked:
                yield None
                return
            state.local.depth = 1
            try:
                yield canonical
            finally:
                state.local.depth = 0
                # An at-fork child closes inherited handles before user code
                # resumes.  The inherited context must not unlock a reused fd
                # or raise EBADF when its finally block later runs.
                if locked and os.getpid() == owner_pid and not lock_file.closed:
                    _unlock_file(lock_file)
        finally:
            with _ACTIVE_LOCK_FILES_GUARD:
                try:
                    lock_file.close()
                finally:
                    _ACTIVE_LOCK_FILES.discard(lock_file)
    finally:
        state.thread_lock.release()
