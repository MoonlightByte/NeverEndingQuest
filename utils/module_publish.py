"""Atomic module publication via build-to-temp + single directory rename.

This is the P2b replacement for the transactional module-lifecycle store's
build/publish path (utils/module_lifecycle.py + core/generators/
managed_module_builder.py, both removed in P2c). It keeps the one property that
mattered -- a module becomes live via a single atomic ``os.replace`` of a fully
built directory, so a crash mid-build leaves an orphan TEMP dir rather than a
partial live module -- and drops the manifest-digest / publication-receipt /
recover() machinery that wrapped it.

Design (isolated single-writer per the server's per-player instance model):
  1. Caller holds ``module_refresh_lock`` for the whole build+publish unit.
  2. Build into ``modules/.module_build_<uuid>/<final_name>/`` via ``build_fn``.
  3. Resolve the final module name by VALUE (auto-suffix ``_v2``) -- never a
     content digest (project ban: identity is never derived from content).
  4. Optionally update ``world_registry.json`` best-effort via a caller-supplied
     ``registry_update_fn`` (advisory metadata; a failure here never bricks the
     already-live module).
  5. Atomic ``os.replace`` of the built dir into ``modules/<final_name>/`` with a
     Windows-correct occupancy guard and a landed-state-proof retry (ported from
     the store's ``_replace_entry`` -- os.replace can raise a transient OSError
     on Windows even when the rename actually completed).
  6. Write a lightweight publish MARKER (value identity = module name) so a
     crash-then-retry re-delivers the creation narration instead of building a
     duplicate ``_v2``. The marker is cleared once narration is confirmed.
  7. On any failure the temp dir is orphaned (swept later); ``modules/<name>/``
     is never touched.
"""

from __future__ import annotations

import errno
import os
import re
import shutil
import stat
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from utils.enhanced_logger import debug, warning, error
from utils.encoding_utils import safe_json_dump, safe_json_load
from utils.module_refresh_lock import assert_module_refresh_lock_owned
from utils.transient_filesystem import (
    is_transient_filesystem_error,
    retry_transient_filesystem,
)

# Value-only module name grammar (letters/numbers with underscore separators).
_MODULE_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$")

_BUILD_WORKSPACE_PREFIX = ".module_build_"
_PUBLISH_MARKER_DIR = ".publish_markers"

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
    """Case-folded names already live under modules/ (excludes hidden dirs)."""
    occupied = set()
    for entry in os.scandir(modules_dir):
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
# Publish markers (value identity = module name; replaces the receipt dedup)
# ----------------------------------------------------------------------------
def _marker_dir(modules_dir: Path) -> Path:
    return Path(modules_dir) / _PUBLISH_MARKER_DIR


def _marker_path(modules_dir: Path, module_name: str) -> Path:
    validate_module_name(module_name)
    return _marker_dir(modules_dir) / f"{module_name}.json"


def write_publish_marker(modules_dir: Path, module_name: str, build_id: str) -> None:
    """Record 'published <module_name>; narration not yet confirmed'.

    A retried createNewModule that sees this marker re-delivers the creation
    narration instead of rebuilding a duplicate module.
    """
    marker_dir = _marker_dir(modules_dir)
    marker_dir.mkdir(parents=True, exist_ok=True)
    safe_json_dump(
        {"module_name": module_name, "build_id": build_id},
        str(_marker_path(modules_dir, module_name)),
    )


def read_publish_marker(modules_dir: Path, module_name: str) -> Optional[dict]:
    """Return the marker for module_name, or None if narration is complete."""
    path = _marker_path(modules_dir, module_name)
    if not path.exists():
        return None
    data = safe_json_load(str(path))
    return data if isinstance(data, dict) else None


def clear_publish_marker(modules_dir: Path, module_name: str) -> None:
    """Drop the marker once the creation narration is confirmed delivered."""
    path = _marker_path(modules_dir, module_name)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        warning(
            f"Could not clear publish marker for {module_name}: {exc}",
            category="module_management",
        )


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
    build and publish).

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
        PublishError / PublishIndeterminateError on a build or rename failure;
        modules/<name>/ is guaranteed untouched on any raise.
    """
    assert_module_refresh_lock_owned()
    modules_root = Path(modules_dir).absolute()
    modules_root.mkdir(parents=True, exist_ok=True)

    final_name = allocate_final_name(modules_root, requested_name)
    build_id = uuid.uuid4().hex
    workspace = modules_root / f"{_BUILD_WORKSPACE_PREFIX}{build_id}"
    candidate_path = workspace / final_name

    try:
        candidate_path.mkdir(parents=True, mode=0o700)
        # 1. Build the complete module tree into the hidden temp workspace.
        build_fn(candidate_path, final_name)

        # 2. Prepare the registry on the CANDIDATE (before it is live). Any
        #    in-place rewrite (ID conflict resolution) touches only the hidden
        #    candidate; a raise here aborts cleanly with modules/ untouched.
        registry_bytes = None
        if prepare_registry_fn is not None:
            registry_bytes = prepare_registry_fn(candidate_path, final_name)

        _sync_directory(candidate_path)
        _sync_directory(workspace)

        # 3. Occupancy guard, then the single atomic rename that makes it live.
        _assert_final_path_free(modules_root, final_name)
        _replace_entry(candidate_path, modules_root / final_name)
        _sync_directory(modules_root)

        # 4. Commit the advisory registry (never bricks the now-live module).
        if registry_bytes is not None:
            try:
                _replace_exact_bytes(modules_root / registry_filename, registry_bytes)
            except Exception as registry_error:
                warning(
                    "Module published but advisory registry commit failed; "
                    f"module {final_name} is live regardless: {registry_error}",
                    category="module_management",
                )

        # 5. Marker so a crash-then-retry re-narrates instead of duplicating.
        write_publish_marker(modules_root, final_name, build_id)
    except BaseException:
        # The module never reached modules/<name>/ on this path (or the rename
        # raised before landing). Leave the temp workspace as an orphan for the
        # startup sweep rather than risk deleting a half-renamed entry here.
        raise
    finally:
        _cleanup_orphan_workspace(workspace)

    debug(
        f"Atomically published module {final_name} (build {build_id})",
        category="module_management",
    )
    return PublishResult(final_name, build_id, workspace)


def _cleanup_orphan_workspace(workspace: Path) -> None:
    """Best-effort removal of an empty/leftover temp build workspace."""
    if not workspace.exists():
        return
    try:
        shutil.rmtree(workspace)
    except OSError as exc:
        # Non-fatal: the startup orphan sweep will retire it later.
        debug(
            f"Left build workspace {workspace.name} for later sweep: {exc}",
            category="module_management",
        )
