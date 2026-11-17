"""Atomic module publication via build-to-temp + single directory rename.

This is the P2b replacement for the transactional module-lifecycle store's
build/publish path (utils/module_lifecycle.py + core/generators/
managed_module_builder.py, both removed in P2c). It keeps the one property that
mattered -- a module becomes live via a single atomic ``os.replace`` of a fully
built directory, so a crash mid-build leaves an orphan TEMP dir rather than a
partial live module -- and drops the manifest-digest / publication-receipt /
recover() machinery that wrapped it.

Design (isolated single-writer per the server's per-player instance model):
  1. Caller holds ``module_refresh_lock`` while it reserves (steps 2-3) and
     while it publishes (steps 4-6), but not while it generates (issue #708):
     ``reserve_build_workspace``, then generation into the private workspace,
     then ``publish_reserved``. ``publish_module_atomic`` still runs all three
     inside one held lock for callers that want that.
  2. Build into ``modules/.module_build_<uuid>/<final_name>/`` via ``build_fn``.
  3. Resolve the final module name by VALUE (auto-suffix ``_v2``) -- never a
     content digest (project ban: identity is never derived from content). A
     name inside any ``.module_build_*`` workspace counts as taken, so builds
     that overlap never pick the same name.
  4. Resolve area-ID conflicts and compute ``world_registry.json`` bytes on the
     hidden candidate BEFORE it is live (via ``prepare_registry_fn``).
  5. Atomic ``os.replace`` of the built dir into ``modules/<final_name>/`` -- the
     COMMIT POINT -- with a Windows-correct occupancy guard and a landed-state-
     proof retry (ported from the store's ``_replace_entry`` -- os.replace can
     raise a transient OSError on Windows even when the rename actually
     completed). A proven pre-rename failure leaves ``modules/<name>/``
     untouched. An indeterminate rename can leave the complete candidate live
     or absent, but never exposes a partial directory copy.
  6. Once the rename lands the module is LIVE and the publish has SUCCEEDED.
     Every remaining step is best-effort and NEVER raises: the advisory
     ``world_registry.json`` write is transient-retried and, if it still fails,
     logged loudly (the live module self-heals on the next scan) -- it is never
     turned into a "publication failed" (which would make a retry build a
     duplicate).

Idempotency note: there is deliberately NO cross-turn dedup marker. A module's
name is not reliably known before the build (createNewModule may carry only a
narrative) and the allocated final name may differ, so a name-keyed marker could
never match a retry. A crash-then-recreate therefore yields a harmless SPARE
module (a value-suffixed ``_v2``) the player can delete -- fail-forward: it never
breaks, corrupts, or stops the game.
"""

from __future__ import annotations

import errno
import os
import re
import shutil
import stat
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from utils.enhanced_logger import debug, error, info, warning
from utils.module_refresh_lock import RUNTIME_LOCKS_DIR, assert_module_refresh_lock_owned
from utils.path_transaction_lock import path_transaction_lock, path_transaction_lock_owned
from utils.transient_filesystem import (
    is_transient_filesystem_error,
    retry_transient_filesystem,
)

# Value-only module name grammar (letters/numbers with underscore separators).
_MODULE_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$")

_BUILD_WORKSPACE_PREFIX = ".module_build_"
# #2052 J3b: exactly the name reserve_build_workspace writes (uuid4().hex).
_BUILD_WORKSPACE_RE = re.compile(r"^\.module_build_[0-9a-f]{32}$")
_BUILD_LOCK_SUFFIX = ".transaction.lock"
# The startup sweep removes a leftover only when its lock is free AND nothing
# in it changed for a day (a free lock alone is not proof: a Windows-native and
# a WSL game do not see each other's locks; an older game version takes none).
_SWEEP_MIN_AGE_SECONDS = 24 * 60 * 60
_SWEEP_MAX_ENTRIES = 10_000
_HELD_BUILD_LOCKS = {}
_HELD_BUILD_LOCKS_GUARD = threading.Lock()

_RENAME_ATTEMPTS = 3
_RENAME_BACKOFF_SECONDS = 0.05


class PublishError(Exception):
    """A module publication failed cleanly (modules/ was never touched)."""


class PublishIndeterminateError(PublishError):
    """The atomic rename crossed into an unprovable state; do not auto-retry."""


@dataclass(frozen=True)
class PublishResult:
    """Outcome of a successful atomic publish."""

    module_name: str
    build_id: str
    workspace_path: Path


@dataclass(frozen=True)
class BuildReservation:
    """A reserved final name and the private hidden workspace that holds it."""

    module_name: str
    build_id: str
    workspace_path: Path
    candidate_path: Path


# ----------------------------------------------------------------------------
# Name validation + value-based allocation (no content digests)
# ----------------------------------------------------------------------------
def validate_module_name(value: Any) -> str:
    """Return one strict top-level module name or raise ``ValueError``."""
    if not isinstance(value, str) or not _MODULE_NAME_RE.fullmatch(value):
        raise ValueError(
            "Module name must use letters/numbers with underscore separators"
        )
    if value.startswith(".") or value in {".", ".."}:
        raise ValueError("Hidden or relative module names are forbidden")
    return value


def _occupied_names(modules_dir: Path) -> set:
    """Case-folded names live under modules/ or reserved by a build workspace.

    Generation runs outside ``module_refresh_lock`` (issue #708), so a build in
    progress reserves its name through its hidden workspace. A crashed build's
    leftover workspace keeps its name too: the cost is a value suffix on the
    next build of that name. Other hidden dirs are ignored.
    """
    occupied = set()
    for entry in os.scandir(modules_dir):
        if entry.name.startswith(_BUILD_WORKSPACE_PREFIX):
            try:
                if entry.is_dir(follow_symlinks=False):
                    for reserved in os.scandir(entry.path):
                        occupied.add(reserved.name.casefold())
            except OSError:
                # Unreadable workspace: the occupancy guard at publish still
                # refuses a name that went live meanwhile.
                pass
            continue
        if entry.name.startswith("."):
            continue
        occupied.add(entry.name.casefold())
    return occupied


def allocate_final_name(modules_dir: Path, requested_name: str) -> str:
    """Return the requested name, or the next free ``_vN`` suffix (by value)."""
    base = validate_module_name(requested_name)
    occupied = _occupied_names(modules_dir)
    if base.casefold() not in occupied:
        return base
    suffix = 2
    while True:
        candidate = f"{base}_v{suffix}"
        validate_module_name(candidate)
        if candidate.casefold() not in occupied:
            return candidate
        suffix += 1
        if suffix > 1_000_000:
            raise PublishError("Module suffix space is exhausted")


# ----------------------------------------------------------------------------
# Durable filesystem primitives (ported self-contained from the store so the
# store file can be deleted in P2c). Behavior preserved verbatim.
# ----------------------------------------------------------------------------
def _entry_stat(path: Path) -> Optional[os.stat_result]:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _same_entry_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
    )


def _sync_directory(path: Path) -> None:
    """fsync a directory entry (POSIX durability). No-op on Windows."""
    if os.name == "nt":
        return
    unsupported = {
        errno.EINVAL,
        getattr(errno, "ENOTSUP", errno.EINVAL),
        getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        getattr(errno, "ENOSYS", errno.EINVAL),
    }

    def synchronize() -> None:
        descriptor = None
        try:
            descriptor = os.open(
                os.fspath(path),
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(descriptor)
            except OSError as exc:
                if exc.errno not in unsupported:
                    raise
        finally:
            if descriptor is not None:
                os.close(descriptor)

    retry_transient_filesystem(synchronize)


def _replace_entry(source: Path, destination: Path) -> None:
    """Move one entry with bounded sharing retry and landed-state proof.

    Ported verbatim from ModuleLifecycleStore._replace_entry: on Windows an
    ``os.replace`` can raise a transient sharing/lock OSError even when the
    rename actually landed, so we re-stat both paths and compare inode/device/
    file-type identity before deciding success vs indeterminate vs retry.
    """
    expected = retry_transient_filesystem(
        lambda: os.lstat(source),
        allow_missing=True,
    )
    for attempt in range(1, _RENAME_ATTEMPTS + 1):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            if not is_transient_filesystem_error(exc, allow_missing=True):
                raise
            source_after = retry_transient_filesystem(
                lambda: _entry_stat(source)
            )
            destination_after = retry_transient_filesystem(
                lambda: _entry_stat(destination)
            )
            if source_after is None and destination_after is not None:
                if _same_entry_identity(expected, destination_after):
                    return
                raise PublishIndeterminateError(
                    "Filesystem move destination identity differs"
                ) from exc
            if (
                source_after is None
                or destination_after is not None
                or not _same_entry_identity(expected, source_after)
            ):
                raise PublishIndeterminateError(
                    "Filesystem move state is indeterminate"
                ) from exc
            if attempt == _RENAME_ATTEMPTS:
                raise
            time.sleep(_RENAME_BACKOFF_SECONDS * attempt)


def _replace_exact_bytes(path: Path, payload: bytes) -> None:
    """Durably replace one file with already-computed exact bytes.

    Ported self-contained from ModuleStitcher._replace_exact_registry_bytes so
    the atomic-publish path keeps the Issue #134 fix without depending on the
    (P2c-deleted) store or importing the heavy stitcher. Without O_BINARY the
    Windows CRT text mode expands LF->CRLF during os.write, so the landed bytes
    differ from `payload` and the exact-byte readback below fails on every write.
    """
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        descriptor = os.open(os.fspath(temporary), flags, 0o600)
        view = memoryview(payload)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if not isinstance(count, int) or count <= 0:
                raise OSError("Exact-byte write made no progress")
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(
                os.fspath(path.parent),
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        if path.read_bytes() != payload:
            raise OSError("Exact-byte readback differs")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _assert_final_path_free(modules_dir: Path, final_name: str) -> None:
    """Windows-correct occupancy guard: os.replace cannot target an existing
    directory. Doubled check (exact path + case-insensitive alias scan) so a
    case-only collision on a case-insensitive filesystem is still caught."""
    final_path = modules_dir / final_name
    if os.path.lexists(final_path):
        raise PublishError(f"Final module path is occupied: {final_name}")
    for entry in os.scandir(modules_dir):
        if entry.name.casefold() == final_name.casefold():
            raise PublishError(f"A final-name alias is occupied: {final_name}")


# ----------------------------------------------------------------------------
# The atomic publish orchestrator
# ----------------------------------------------------------------------------
def publish_module_atomic(
    requested_name: str,
    build_fn: Callable[[Path, str], Any],
    *,
    modules_dir: os.PathLike | str = "modules",
    prepare_registry_fn: Optional[Callable[[Path, str], Optional[bytes]]] = None,
    registry_filename: str = "world_registry.json",
) -> PublishResult:
    """Build a module in a temp workspace and atomically publish it live.

    Caller MUST already hold ``module_refresh_lock`` (this mirrors the store,
    which never acquired the lock itself so one uninterrupted scope can span
    build and publish). A caller that should not hold the lock while it
    generates uses ``reserve_build_workspace`` and ``publish_reserved``
    instead (issue #708); this function is exactly those two around
    ``build_fn``.

    Args:
        requested_name: the desired module name (validated; value-suffixed on
            collision with an existing module).
        build_fn: ``build_fn(candidate_path, final_name)`` writes the complete
            module tree into ``candidate_path`` (a fresh empty directory).
            Its return value (the build payload) is returned to the caller via
            the closure; this function ignores it.
        modules_dir: the modules root.
        prepare_registry_fn: optional ``prepare_registry_fn(candidate_path, final_name)``
            invoked on the built candidate BEFORE the rename (so any in-place
            rewrite it performs -- e.g. area-ID conflict resolution -- happens on
            the hidden candidate, never on a live module). It returns the exact
            ``world_registry.json`` bytes to commit, or ``None`` to skip the
            registry update. If it RAISES, the publish is aborted and
            modules/<name>/ is never touched (a genuine conflict must not go
            live). The returned bytes are committed AFTER the rename; a failure
            of that final byte-write is advisory (logged, swallowed) because the
            module is already live and the registry is advisory metadata.
        registry_filename: the registry file to commit next to modules_dir.

    Returns:
        PublishResult(module_name, build_id, workspace_path).

    Raises:
        PublishError / PublishIndeterminateError on a build or rename failure.
        A proven pre-commit failure leaves modules/<name>/ untouched. In the
        rare indeterminate-rename case, the complete candidate may be live or
        absent, but a partially copied public module is never exposed.
    """
    assert_module_refresh_lock_owned()
    reservation = reserve_build_workspace(requested_name, modules_dir=modules_dir)
    try:
        # 1. Build the complete module tree into the hidden temp workspace.
        build_fn(reservation.candidate_path, reservation.module_name)
    except BaseException:
        discard_reservation(reservation)
        raise
    return publish_reserved(
        reservation,
        prepare_registry_fn=prepare_registry_fn,
        registry_filename=registry_filename,
    )


def reserve_build_workspace(
    requested_name: str,
    *,
    modules_dir: os.PathLike | str = "modules",
) -> BuildReservation:
    """Reserve a final name and create its empty private build workspace.

    Caller MUST hold ``module_refresh_lock``: the name is allocated against
    the live modules and every other reservation. The caller may then release
    the lock and generate into ``candidate_path``; nothing else writes there.
    """
    assert_module_refresh_lock_owned()
    modules_root = Path(modules_dir).absolute()
    modules_root.mkdir(parents=True, exist_ok=True)

    final_name = allocate_final_name(modules_root, requested_name)
    build_id = uuid.uuid4().hex
    workspace = modules_root / f"{_BUILD_WORKSPACE_PREFIX}{build_id}"
    candidate_path = workspace / final_name
    # #2052 J3b: the build's own lock BEFORE its workspace exists, held until
    # publish_reserved or discard_reservation returns (the OS drops it if the
    # process dies), so the startup sweep never takes a live workspace.
    _acquire_build_lock(build_id)
    try:
        candidate_path.mkdir(parents=True, mode=0o700)
    except BaseException:
        _cleanup_orphan_workspace(workspace)
        _release_build_lock(build_id)
        raise
    return BuildReservation(final_name, build_id, workspace, candidate_path)


def discard_reservation(reservation: BuildReservation) -> None:
    """Remove a reservation whose build failed. The refresh lock is not
    needed: the workspace is private to its build, and modules/<name> was
    never touched. The build's own lock is released after."""
    try:
        _cleanup_orphan_workspace(reservation.workspace_path)
    finally:
        _release_build_lock(reservation.build_id)


def publish_reserved(
    reservation: BuildReservation,
    *,
    prepare_registry_fn: Optional[Callable[[Path, str], Optional[bytes]]] = None,
    registry_filename: str = "world_registry.json",
) -> PublishResult:
    """Publish a reserved, fully generated candidate (steps 4-6 of the design).

    Caller MUST hold ``module_refresh_lock`` again here: the registry
    preparation, the occupancy guard, the rename and the registry write are
    the steps that read or publish shared module state, so they stay
    serialized. ``prepare_registry_fn`` and the failure contract are as for
    ``publish_module_atomic``.
    """
    assert_module_refresh_lock_owned()
    workspace = reservation.workspace_path
    modules_root = workspace.parent
    final_name = reservation.module_name
    build_id = reservation.build_id
    candidate_path = reservation.candidate_path

    try:
        # #2021: an in-game build stopped (Load, Reset, Quit) while it waited
        # for the lock spends nothing more here.
        _raise_if_build_superseded()
        # 2. Prepare the registry on the CANDIDATE (before it is live). Any
        #    in-place rewrite (ID conflict resolution) touches only the hidden
        #    candidate; a raise here aborts cleanly with modules/ untouched.
        registry_bytes = None
        if prepare_registry_fn is not None:
            registry_bytes = prepare_registry_fn(candidate_path, final_name)

        _sync_directory(candidate_path)
        _sync_directory(workspace)

        # 3. Occupancy guard, then the single atomic rename -- the COMMIT POINT.
        #    A failure before this rename leaves modules/<name>/ untouched. In
        #    the rare indeterminate-rename case, the complete candidate may be
        #    live or absent; the operation never exposes a partial copy.
        _assert_final_path_free(modules_root, final_name)
        # #2021: the decisive check, the last point before the module goes
        # live. A Load moves the game epoch under this same lock, so either
        # the Load came first and this refuses, or the rename did.
        _raise_if_build_superseded()
        _replace_entry(candidate_path, modules_root / final_name)
    except BaseException:
        _cleanup_orphan_workspace(workspace)
        _release_build_lock(build_id)
        raise

    # ---- THE MODULE IS NOW LIVE ON DISK; nothing below may raise ----
    # The publish has SUCCEEDED the instant the rename landed. Every remaining
    # step is best-effort and must NEVER turn a live module into a "publication
    # failed" -- that would make a retry build a duplicate. A registry-write
    # failure is logged LOUDLY (never swallowed): the module is live and will be
    # re-registered by the next scan_and_integrate, so it self-heals.
    try:
        _sync_directory(modules_root)
    except Exception as sync_error:
        debug(
            f"Post-publish directory sync deferred for {final_name}: {sync_error}",
            category="module_management",
        )
    if registry_bytes is not None:
        try:
            retry_transient_filesystem(
                lambda: _replace_exact_bytes(
                    modules_root / registry_filename, registry_bytes
                )
            )
        except Exception as registry_error:
            error(
                f"Module PUBLISHED but its world_registry.json update failed; "
                f"{final_name} is LIVE on disk and will be re-registered on the "
                f"next module scan: {registry_error}",
                category="module_management",
            )
    _cleanup_orphan_workspace(workspace)
    _release_build_lock(build_id)
    debug(
        f"Atomically published module {final_name} (build {build_id})",
        category="module_management",
    )
    return PublishResult(final_name, build_id, workspace)


def _raise_if_build_superseded() -> None:
    """Stop an in-game build whose fence was superseded; no-op otherwise."""
    from utils.capture.live_provider_call import raise_if_build_superseded

    raise_if_build_superseded()


def _cleanup_orphan_workspace(workspace: Path) -> None:
    """Best-effort removal of this invocation's temp build workspace."""
    if not workspace.exists():
        return
    try:
        shutil.rmtree(workspace)
    except OSError as exc:
        # Non-fatal: hidden workspaces are ignored; P2c owns the orphan sweep.
        debug(
            f"Left build workspace {workspace.name} for later sweep: {exc}",
            category="module_management",
        )


# ----------------------------------------------------------------------------
# #2052 J3b: the build lock and the startup sweep of stale build workspaces
# ----------------------------------------------------------------------------
def _build_lock_target(build_id: str) -> str:
    """The lock identity of one build: under the data root's .runtime_locks,
    never inside modules/."""
    return os.path.join(RUNTIME_LOCKS_DIR, "module_build_%s" % build_id)


def _acquire_build_lock(build_id: str) -> None:
    lock = path_transaction_lock(_build_lock_target(build_id), timeout_seconds=5.0)
    if lock.__enter__() is None:
        lock.__exit__(None, None, None)
        raise PublishError("The new build's lock could not be taken")
    with _HELD_BUILD_LOCKS_GUARD:
        _HELD_BUILD_LOCKS[build_id] = (lock, threading.get_ident())


def _release_build_lock(build_id: str) -> None:
    """Release this build's lock (once; on the thread that took it) and remove
    its lock file. Best-effort: process death releases the lock anyway."""
    with _HELD_BUILD_LOCKS_GUARD:
        held = _HELD_BUILD_LOCKS.get(build_id)
        if held is None or held[1] != threading.get_ident():
            if held is not None:
                debug(
                    "Build lock %s not released here: another thread holds it" % build_id,
                    category="module_management",
                )
            return
        del _HELD_BUILD_LOCKS[build_id]
    try:
        held[0].__exit__(None, None, None)
    except Exception as exc:
        debug("Build lock %s release: %s" % (build_id, type(exc).__name__), category="module_management")
        return
    _remove_lock_file(build_id)


def _remove_lock_file(build_id: str) -> None:
    try:
        os.remove(_build_lock_target(build_id) + _BUILD_LOCK_SUFFIX)
    except OSError:
        pass


def _data_modules_root() -> str:
    """The game's modules folder as an absolute data-root path (NEQ_DATA_DIR,
    else the game root: RUNTIME_LOCKS_DIR's parent), never the cwd's."""
    return os.path.join(os.path.dirname(os.path.abspath(RUNTIME_LOCKS_DIR)), "modules")


def _real_directory(path: str, real_root: str) -> Optional[os.stat_result]:
    """The entry's lstat when it is a real directory directly in the modules
    root (no link, junction or reparse point; realpath's parent is the root),
    else None."""
    st = os.lstat(path)
    if not _plain_directory(path, st):
        return None
    if os.path.dirname(os.path.realpath(path)) != real_root:
        return None
    return st


def _plain_directory(path: str, st: os.stat_result) -> bool:
    """True when the lstat st of path is a directory that is not a link, a
    junction or any other reparse point."""
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode) or os.path.islink(path):
        return False
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(path):
        return False
    if getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return False
    return True


def _extended_path(root: str) -> str:
    """The Windows long-path form of an absolute path: the extended prefix
    before a drive path, and the extended UNC prefix (in place of the two
    leading backslashes) for a network share; a path already in an extended
    or device form is returned unchanged."""
    if root.startswith("\\\\?\\") or root.startswith("\\\\.\\"):
        return root
    if root.startswith("\\\\"):
        return "\\\\?\\UNC\\" + root[2:]
    return "\\\\?\\" + root


def _newest_mtime(path: str) -> Optional[float]:
    """The newest mtime in a workspace by an lstat walk that never follows a
    link; None past _SWEEP_MAX_ENTRIES entries."""
    newest = os.lstat(path).st_mtime
    count = 0
    stack = [path]
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                count += 1
                if count > _SWEEP_MAX_ENTRIES:
                    return None
                st = entry.stat(follow_symlinks=False)
                newest = max(newest, st.st_mtime)
                if entry.is_dir(follow_symlinks=False) and not stat.S_ISLNK(st.st_mode):
                    stack.append(entry.path)
    return newest


def _remove_workspace(path: str) -> None:
    """rmtree confined to one workspace. A failure on a non-link path inside
    it clears the read-only bit (on the path and its parent) and retries once;
    anything else is raised. On Windows the extended path form is used."""
    root = os.path.abspath(path)
    if os.name == "nt":
        root = _extended_path(root)
    retried = set()

    def handler(func, failed, exc_info):
        failed_abs = os.path.abspath(failed)
        inside = os.path.commonpath([failed_abs, root]) == root and failed_abs != root
        if not inside or os.path.islink(failed_abs) or failed_abs in retried:
            raise exc_info[1] if isinstance(exc_info, tuple) else exc_info
        retried.add(failed_abs)
        for target in (failed_abs, os.path.dirname(failed_abs)):
            try:
                mode = os.lstat(target).st_mode
                if not stat.S_ISLNK(mode):
                    os.chmod(target, stat.S_IMODE(mode) | stat.S_IWRITE | stat.S_IREAD | (stat.S_IEXEC if stat.S_ISDIR(mode) else 0))
            except OSError:
                pass
        func(failed)

    if sys.version_info >= (3, 12):
        shutil.rmtree(root, onexc=lambda f, p, e: handler(f, p, e))
    else:
        shutil.rmtree(root, onerror=lambda f, p, e: handler(f, p, e))


def _drop_pipeline_state(path: str, expected: tuple) -> None:
    """Before removing a workspace: its story-first resume state goes first, so
    a workspace the sweep touched (a removal that failed halfway) can never be
    adopted as a resumable build. ``expected``: the workspace's checked
    (st_dev, st_ino); the removal refuses a folder that is not that one."""
    with os.scandir(path) as entries:
        children = [entry.name for entry in entries]
    for child_name in children:
        child = os.path.join(path, child_name)
        story = os.path.join(child, ".story_first")
        try:
            if not _plain_directory(child, os.lstat(child)):
                continue
            if not _plain_directory(story, os.lstat(story)):
                continue
        except FileNotFoundError:
            continue
        _remove_regular_file(path, child_name, expected)


def _remove_regular_file(workspace: str, child_name: str, expected: tuple) -> None:
    """Remove <workspace>/<child>/.story_first/pipeline_state.json when it is a
    regular file. On POSIX every step opens a directory fd with O_NOFOLLOW, so
    a component swapped for a link after the checks is refused, never
    followed, and the workspace fd must be the checked folder (``expected``,
    its (st_dev, st_ino)); on Windows the plain path (its components were
    checked)."""
    name = "pipeline_state.json"
    flags = getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if os.name == "nt" or not flags or os.open not in os.supports_dir_fd or os.unlink not in os.supports_dir_fd:
        state = os.path.join(workspace, child_name, ".story_first", name)
        try:
            st = os.lstat(state)
        except FileNotFoundError:
            return
        if stat.S_ISREG(st.st_mode):
            os.remove(state)
        return
    fds = []
    try:
        fds.append(os.open(workspace, os.O_RDONLY | flags))
        opened = os.fstat(fds[0])
        if (opened.st_dev, opened.st_ino) != tuple(expected):
            raise OSError(errno.ESTALE, "the workspace changed after its checks")
        fds.append(os.open(child_name, os.O_RDONLY | flags, dir_fd=fds[-1]))
        fds.append(os.open(".story_first", os.O_RDONLY | flags, dir_fd=fds[-1]))
        try:
            st = os.stat(name, dir_fd=fds[-1], follow_symlinks=False)
        except FileNotFoundError:
            return
        if stat.S_ISREG(st.st_mode):
            os.unlink(name, dir_fd=fds[-1])
    finally:
        for fd in reversed(fds):
            os.close(fd)


def sweep_stale_build_workspaces(now: Optional[float] = None) -> list:
    """#2052 J3b, once at game start (reconcile_campaign_state, under
    module_refresh_lock): remove the hidden build workspaces a dead session
    left in the game's modules folder. A candidate is an entry named exactly
    .module_build_<32 hex> that is a real directory in that folder. It is
    removed only when its build lock is taken with no wait AND nothing in it
    changed for _SWEEP_MIN_AGE_SECONDS (a future mtime counts as young). Every
    failure is a skip; the sweep never raises. Returns the removed names."""
    removed = []
    try:
        modules_root = _data_modules_root()
        info("Startup sweep of unfinished new-adventure folders in %s" % modules_root,
             category="module_management")
        if not os.path.isdir(modules_root):
            return removed
        real_root = os.path.realpath(modules_root)
        with os.scandir(modules_root) as entries:
            names = sorted(entry.name for entry in entries)
    except Exception as exc:
        debug("Startup sweep skipped: %s" % type(exc).__name__, category="module_management")
        return removed
    clock = time.time() if now is None else now
    for name in names:
        if not _BUILD_WORKSPACE_RE.fullmatch(name):
            continue
        try:
            reason = _sweep_one(modules_root, real_root, name, clock)
        except Exception as exc:
            reason = "error %s" % type(exc).__name__
        if reason is None:
            removed.append(name)
            info("Removed an unfinished new-adventure folder left by an earlier session: %s" % name,
                 category="module_management")
        elif reason.startswith("removal failed"):
            warning("Could not remove the unfinished new-adventure folder %s (%s); a later start tries again"
                    % (name, reason), category="module_management")
        else:
            debug("Startup sweep kept %s: %s" % (name, reason), category="module_management")
    return removed


def _sweep_one(modules_root: str, real_root: str, name: str, clock: Optional[float]) -> Optional[str]:
    """None when the workspace was removed, else the reason it was kept.
    clock None: no age gate (discard_stale_workspace: the build record names
    the workspace, so it is known to be that build's)."""
    path = os.path.join(modules_root, name)
    first = _real_directory(path, real_root)
    if first is None:
        return "not a real directory in the modules folder"
    build_id = name[len(_BUILD_WORKSPACE_PREFIX):]
    target = _build_lock_target(build_id)
    if path_transaction_lock_owned(target, suffix=_BUILD_LOCK_SUFFIX):
        return "lock held by this thread"
    with path_transaction_lock(target, timeout_seconds=0) as acquired:
        if acquired is None:
            return "lock held"
        again = _real_directory(path, real_root)
        if again is None or (again.st_dev, again.st_ino) != (first.st_dev, first.st_ino):
            return "lock free; changed before removal"
        age = 0.0
        if clock is not None:
            newest = _newest_mtime(path)
            if newest is None:
                return "lock free; more than %d entries" % _SWEEP_MAX_ENTRIES
            age = clock - newest
            if age < 0:
                return "lock free; newest change in the future (%.0f s)" % age
            if age < _SWEEP_MIN_AGE_SECONDS:
                return "lock free; newest change %.0f s ago" % age
        try:
            _drop_pipeline_state(path, (again.st_dev, again.st_ino))
            _remove_workspace(path)
        except Exception as exc:
            return "removal failed (lock free; age %.0f s): %s" % (age, type(exc).__name__)
    _remove_lock_file(build_id)
    return None


def discard_stale_workspace(workspace_hex: str) -> Optional[str]:
    """#2052 J3c: remove one hidden build workspace that a build record names
    (an earlier process's attempt), as the startup sweep removes one but with
    no age gate: the name rule and the real-directory checks, its build lock
    taken with no wait (held: kept, a live process owns it), the same-inode
    re-check, the pipeline state first, then the confined removal. None when
    it was removed or was already gone, else the reason it was kept. Never
    raises."""
    name = "%s%s" % (_BUILD_WORKSPACE_PREFIX, workspace_hex)
    try:
        if not isinstance(workspace_hex, str) or not _BUILD_WORKSPACE_RE.fullmatch(name):
            return "not a build workspace name"
        modules_root = _data_modules_root()
        if not os.path.lexists(os.path.join(modules_root, name)):
            # No folder: its lock file goes only under that lock. reserve
            # takes the lock before its mkdir, so a held lock with no folder
            # is a live reservation; unlinking its file would let another
            # process lock a new file of the same name.
            target = _build_lock_target(workspace_hex)
            if path_transaction_lock_owned(target, suffix=_BUILD_LOCK_SUFFIX):
                return "lock held by this thread"
            with path_transaction_lock(target, timeout_seconds=0) as acquired:
                if acquired is None:
                    return "held"
                if os.path.lexists(os.path.join(modules_root, name)):
                    return "appeared while checking; kept"
                _remove_lock_file(workspace_hex)
            return None
        reason = _sweep_one(modules_root, os.path.realpath(modules_root), name, None)
    except Exception as exc:
        reason = "error %s" % type(exc).__name__
    if reason is None:
        info("Removed the unfinished new-adventure folder %s of an earlier session's build" % name,
             category="module_management")
    else:
        debug("Kept %s: %s" % (name, reason), category="module_management")
    return reason
