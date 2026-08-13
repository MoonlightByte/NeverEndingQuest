"""Durable hidden workspace lifecycle for generated adventure modules.

This module deliberately owns only build visibility and exact filesystem
evidence.  Registry publication is layered on top by the module stitcher.  A
candidate is never made public until its complete tree has been synchronized,
manifested, and atomically activated under ``.module_transactions``.

All destructive-looking failure handling is an identity-bound rename into the
hidden ``resolved`` namespace.  The foundation never recursively deletes a
caller-supplied path or a public module directory.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union
from uuid import UUID, uuid4

from utils.transient_filesystem import (
    TRANSIENT_FILESYSTEM_ATTEMPTS,
    TRANSIENT_FILESYSTEM_BACKOFF_SECONDS,
    is_transient_filesystem_error,
    retry_transient_filesystem,
)


SCHEMA_VERSION = 1
TRANSACTION_ROOT_NAME = ".module_transactions"
_MODULE_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_REPARSE_POINT = 0x0400
_STORY_FIRST_RESUME_FILE = "story_first_resume.json"
_STORY_FIRST_FAILURE_CLASSES = frozenset(
    {
        "interrupted",
        "timeout",
        "empty_response",
        "duplicate_json_key",
        "malformed_json",
        "schema",
        "semantic",
        "provider",
        "capacity",
        "authentication",
        "pipeline",
    }
)
_STORY_FIRST_DIAGNOSTIC_FIELDS = frozenset({"invariant", "offending", "expectation"})
_CREDENTIAL_SHAPED_TEXT = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~-]{12,}|sk-[A-Za-z0-9_-]{12,}|"
    r"AIza[A-Za-z0-9_-]{20,})"
)
_MANIFEST_MAX_ATTEMPTS = TRANSIENT_FILESYSTEM_ATTEMPTS
_MANIFEST_RETRY_BACKOFF_SECONDS = TRANSIENT_FILESYSTEM_BACKOFF_SECONDS


def assert_module_refresh_owned() -> None:
    """Fail closed unless this thread owns the shared module-refresh lock."""
    from utils.module_refresh_lock import assert_module_refresh_lock_owned

    assert_module_refresh_lock_owned()


class ModuleLifecycleError(RuntimeError):
    """Base error for a lifecycle operation that did not prove its result."""


class LifecycleIndeterminateError(ModuleLifecycleError):
    """Disk state was not one of the exact states the lifecycle owns."""


class LifecycleBusyError(ModuleLifecycleError):
    """The shared module-refresh boundary could not be acquired."""


class LifecycleKind(str, Enum):
    ACTION = "ACTION"
    TOOLKIT = "TOOLKIT"
    DISCOVERY = "DISCOVERY"


class LifecyclePhase(str, Enum):
    BUILDING = "BUILDING"
    READY = "READY"
    GENERATED = "GENERATED"
    PUBLISHED = "PUBLISHED"
    NOT_PUBLISHED = "NOT_PUBLISHED"


class LifecycleStatus(str, Enum):
    READY = "READY"
    GENERATED = "GENERATED"
    PUBLISHED = "PUBLISHED"
    NOT_PUBLISHED = "NOT_PUBLISHED"
    INDETERMINATE = "INDETERMINATE"


class RecoveryStatus(str, Enum):
    STABLE = "STABLE"
    RECOVERED = "RECOVERED"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class BuildWorkspace:
    build_id: str
    token: str
    kind: LifecycleKind
    requested_name: str
    final_name: str
    transaction_path: Path
    candidate_path: Path


@dataclass(frozen=True)
class ActiveCandidate:
    build_id: str
    token: str
    kind: LifecycleKind
    requested_name: str
    final_name: str
    transaction_path: Path
    candidate_path: Path
    final_path: Path
    manifest: Mapping[str, Mapping[str, Any]]
    manifest_digest: str
    prior_registry_digest: Optional[str] = None
    candidate_registry_digest: Optional[str] = None


@dataclass(frozen=True)
class RegistryPreparation:
    """Exact registry bytes prepared while the module is still hidden."""

    prior_registry_bytes: bytes
    candidate_registry_bytes: bytes


@dataclass(frozen=True)
class LifecycleOutcome:
    build_id: str
    token: str
    kind: LifecycleKind
    module_name: str
    status: LifecycleStatus
    manifest_digest: Optional[str]
    acknowledged: bool
    reason_code: str
    message_id: Optional[str] = None
    message_digest: Optional[str] = None
    idempotency_key: Optional[str] = None


@dataclass(frozen=True)
class GeneratedModule:
    build_id: str
    token: str
    kind: LifecycleKind
    module_name: str
    final_path: Path
    manifest_digest: str
    status: LifecycleStatus = LifecycleStatus.GENERATED


@dataclass(frozen=True)
class PendingReceipt:
    build_id: str
    module_name: str
    status: LifecycleStatus
    manifest_digest: str
    message_id: str
    message_digest: str
    idempotency_key: str
    acknowledged: bool = False


@dataclass(frozen=True)
class ReceiptDeliveryPlan:
    """Exact history suffix declared before a committed delivery save."""

    build_id: str
    message_ids: Tuple[str, ...]
    suffix_digest: str


@dataclass(frozen=True)
class PublicationReceiptMetadata:
    """Durable delivery identity staged before ACTION publication begins."""

    build_id: str
    token: str
    module_name: str
    manifest_digest: str
    message_id: str
    message_digest: str
    idempotency_key: str


@dataclass(frozen=True)
class RecoveryReport:
    status: RecoveryStatus
    outcomes: Tuple[LifecycleOutcome, ...] = ()
    reason: str = ""

    def __bool__(self) -> bool:
        raise TypeError("RecoveryReport has no implicit truth value; inspect .status")


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value is forbidden: {value}")


def _strict_object(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )


def _strict_json_bytes(payload: bytes) -> Any:
    if not isinstance(payload, bytes):
        raise ValueError("Registry snapshot must be exact bytes")
    text = payload.decode("utf-8")
    return json.loads(
        text,
        object_pairs_hook=_strict_object,
        parse_constant=_reject_constant,
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _is_reparse(path_stat: os.stat_result) -> bool:
    return bool(getattr(path_stat, "st_file_attributes", 0) & _REPARSE_POINT)


def _validate_uuid(value: Any) -> str:
    if not isinstance(value, str) or not _UUID_RE.fullmatch(value):
        raise ValueError("Lifecycle identity must be a canonical UUID4")
    parsed = UUID(value)
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("Lifecycle identity must be a canonical UUID4")
    return value


def validate_module_name(value: Any) -> str:
    """Return one strict top-level module name or raise ``ValueError``."""
    if not isinstance(value, str) or not _MODULE_NAME_RE.fullmatch(value):
        raise ValueError(
            "Module name must use letters/numbers with underscore separators"
        )
    if value.startswith(".") or value in {".", ".."}:
        raise ValueError("Hidden or relative module names are forbidden")
    return value


class ModuleLifecycleStore:
    """Contained durable store for hidden builds and exact outcomes.

    Callers that can race another process must own ``module_refresh_lock``.
    The store intentionally does not acquire that lock internally so higher
    layers can keep one uninterrupted lock scope across build and publication.
    """

    def __init__(
        self,
        modules_dir: Union[os.PathLike, str] = "modules",
    ):
        self.modules_dir = Path(modules_dir).absolute()
        self.transaction_root = self.modules_dir / TRANSACTION_ROOT_NAME
        self.staging_root = self.transaction_root / "staging"
        self.active_root = self.transaction_root / "active"
        self.resolved_root = self.transaction_root / "resolved"

    # ------------------------------------------------------------------
    # Durable and containment primitives
    # ------------------------------------------------------------------
    @staticmethod
    def _sync_directory(path: Path) -> None:
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

    @staticmethod
    def _same_entry_identity(left: os.stat_result, right: os.stat_result) -> bool:
        return (
            left.st_dev == right.st_dev
            and left.st_ino == right.st_ino
            and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
        )

    @classmethod
    def _replace_entry(cls, source: Path, destination: Path) -> None:
        """Move one entry with bounded sharing retry and landed-state proof."""
        expected = retry_transient_filesystem(
            lambda: os.lstat(source),
            allow_missing=True,
        )
        for attempt in range(1, _MANIFEST_MAX_ATTEMPTS + 1):
            try:
                os.replace(source, destination)
                return
            except OSError as exc:
                if not is_transient_filesystem_error(exc, allow_missing=True):
                    raise
                source_after = retry_transient_filesystem(
                    lambda: cls._entry_stat(source)
                )
                destination_after = retry_transient_filesystem(
                    lambda: cls._entry_stat(destination)
                )
                if source_after is None and destination_after is not None:
                    if cls._same_entry_identity(expected, destination_after):
                        return
                    raise LifecycleIndeterminateError(
                        "Filesystem move destination identity differs"
                    ) from exc
                if (
                    source_after is None
                    or destination_after is not None
                    or not cls._same_entry_identity(expected, source_after)
                ):
                    raise LifecycleIndeterminateError(
                        "Filesystem move state is indeterminate"
                    ) from exc
                if attempt == _MANIFEST_MAX_ATTEMPTS:
                    raise
                time.sleep(_MANIFEST_RETRY_BACKOFF_SECONDS * attempt)

    @classmethod
    def _replace_file_payload(
        cls,
        temporary: Path,
        destination: Path,
        payload: bytes,
    ) -> None:
        """Commit exact bytes, recognizing a replace that already landed."""
        for attempt in range(1, _MANIFEST_MAX_ATTEMPTS + 1):
            try:
                os.replace(temporary, destination)
                return
            except OSError as exc:
                if not is_transient_filesystem_error(exc, allow_missing=True):
                    raise
                try:
                    landed = destination.read_bytes()
                except FileNotFoundError:
                    landed = None
                except OSError as read_error:
                    if not is_transient_filesystem_error(
                        read_error,
                        allow_missing=True,
                    ):
                        raise
                    landed = None
                if landed == payload:
                    return
                if attempt == _MANIFEST_MAX_ATTEMPTS:
                    raise
                time.sleep(_MANIFEST_RETRY_BACKOFF_SECONDS * attempt)

    @classmethod
    def _atomic_write_bytes(cls, path: Path, payload: bytes) -> None:
        parent = path.parent
        temporary = parent / f".{path.name}.{uuid4().hex}.tmp"
        descriptor = None
        created = False
        try:
            descriptor = os.open(
                os.fspath(temporary),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            created = True
            offset = 0
            while offset < len(payload):
                written = os.write(descriptor, payload[offset:])
                if not isinstance(written, int) or written <= 0:
                    raise OSError("Atomic lifecycle write made no progress")
                offset += written
            retry_transient_filesystem(lambda: os.fsync(descriptor))
            os.close(descriptor)
            descriptor = None
            cls._replace_file_payload(temporary, path, payload)
            created = os.path.lexists(temporary)
            cls._sync_directory(parent)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if created:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    @classmethod
    def _atomic_write_json(cls, path: Path, value: Any) -> None:
        cls._atomic_write_bytes(path, _canonical_json_bytes(value))

    @staticmethod
    def _entry_stat(path: Path) -> Optional[os.stat_result]:
        try:
            return os.lstat(path)
        except FileNotFoundError:
            return None

    @classmethod
    def _require_plain_directory(
        cls,
        path: Path,
        *,
        allow_mount: bool = False,
    ) -> os.stat_result:
        path_stat = cls._entry_stat(path)
        if path_stat is None or not stat.S_ISDIR(path_stat.st_mode):
            raise LifecycleIndeterminateError(
                f"Expected directory is unavailable: {path}"
            )
        if stat.S_ISLNK(path_stat.st_mode) or _is_reparse(path_stat):
            raise LifecycleIndeterminateError(
                f"Directory is a link/reparse point: {path}"
            )
        if not allow_mount and os.path.ismount(path):
            raise LifecycleIndeterminateError(
                f"Directory is an unexpected mount: {path}"
            )
        return path_stat

    @classmethod
    def _mkdir_exact(cls, path: Path, *, parent: Path) -> None:
        cls._require_plain_directory(parent, allow_mount=True)
        existing_names = [entry.name for entry in os.scandir(parent)]
        if any(name.casefold() == path.name.casefold() for name in existing_names):
            raise FileExistsError(f"Lifecycle entry is occupied: {path.name}")
        os.mkdir(path, 0o700)
        cls._require_plain_directory(path)
        cls._sync_directory(parent)

    def ensure_layout(self) -> None:
        assert_module_refresh_owned()
        if self._entry_stat(self.modules_dir) is None:
            self.modules_dir.mkdir(parents=True, mode=0o700)
        self._require_plain_directory(self.modules_dir, allow_mount=True)

        if self._entry_stat(self.transaction_root) is None:
            self._mkdir_exact(self.transaction_root, parent=self.modules_dir)
        else:
            self._require_plain_directory(self.transaction_root)
        for root in (self.staging_root, self.active_root, self.resolved_root):
            if self._entry_stat(root) is None:
                self._mkdir_exact(root, parent=self.transaction_root)
            else:
                self._require_plain_directory(root)

        for root in (self.staging_root, self.active_root, self.resolved_root):
            self._require_plain_directory(root)

    def _require_layout(self) -> None:
        """Read-only verification; unlike ensure_layout, creates nothing."""
        self._require_plain_directory(self.modules_dir, allow_mount=True)
        self._require_plain_directory(self.transaction_root)
        for root in (self.staging_root, self.active_root, self.resolved_root):
            self._require_plain_directory(root)

    def _transaction_path(self, root: Path, build_id: str) -> Path:
        _validate_uuid(build_id)
        candidate = root / build_id
        if candidate.parent != root:
            raise LifecycleIndeterminateError("Transaction path is not contained")
        return candidate

    # ------------------------------------------------------------------
    # Strict manifests
    # ------------------------------------------------------------------
    @classmethod
    def create_manifest(
        cls,
        root: Union[os.PathLike, str],
    ) -> Dict[str, Dict[str, Any]]:
        """Return one strict manifest, tolerating only bounded transient races.

        Files synchronized by OneDrive and similar services can be rebound or
        re-statted immediately after the generator closes them.  A failed walk
        is discarded in full: every retry starts from the root and repeats all
        available identity, link, device, size, timestamp, and digest checks.
        Filesystems without stable file IDs receive two complete content reads.
        Persistent or unsafe trees therefore remain indeterminate after the
        fixed attempt limit.
        """
        last_error: Optional[BaseException] = None
        for attempt in range(1, _MANIFEST_MAX_ATTEMPTS + 1):
            try:
                return cls._create_manifest_once(root)
            except (LifecycleIndeterminateError, OSError) as exc:
                if isinstance(exc, OSError) and not is_transient_filesystem_error(
                    exc,
                    allow_missing=True,
                ):
                    raise
                last_error = exc
                if attempt == _MANIFEST_MAX_ATTEMPTS:
                    raise LifecycleIndeterminateError(
                        f"{exc} after {attempt} manifest attempts"
                    ) from exc
                time.sleep(_MANIFEST_RETRY_BACKOFF_SECONDS * attempt)
        raise AssertionError(f"unreachable manifest retry state: {last_error}")

    @classmethod
    def _create_manifest_once(
        cls,
        root: Union[os.PathLike, str],
    ) -> Dict[str, Dict[str, Any]]:
        """Perform exactly one complete strict manifest walk."""
        root_path = Path(root)
        root_stat = cls._require_plain_directory(root_path)
        root_device = root_stat.st_dev
        stable_file_ids = cls._manifest_file_ids_are_stable(
            root_path,
            root_stat,
            root_device,
        )
        entries, observations = cls._walk_manifest_once(
            root_path,
            root_device,
            stable_file_ids=stable_file_ids,
        )
        if stable_file_ids:
            return entries

        verified_entries, verified_observations = cls._walk_manifest_once(
            root_path,
            root_device,
            stable_file_ids=False,
        )
        if (
            verified_entries != entries
            or verified_observations != observations
        ):
            raise LifecycleIndeterminateError(
                "Manifest changed between content verification reads"
            )
        return entries

    @classmethod
    def _manifest_file_ids_are_stable(
        cls,
        root_path: Path,
        root_stat: os.stat_result,
        root_device: int,
    ) -> bool:
        """Probe whether path and handle stats expose stable nonzero file IDs."""

        def usable(path_stat: os.stat_result) -> bool:
            return (
                isinstance(getattr(path_stat, "st_dev", None), int)
                and isinstance(getattr(path_stat, "st_ino", None), int)
                and path_stat.st_ino != 0
            )

        rebound_root = os.lstat(root_path)
        if (
            not usable(root_stat)
            or not usable(rebound_root)
            or not cls._same_entry_identity(root_stat, rebound_root)
        ):
            return False

        def find_probe(directory: Path) -> Optional[Path]:
            for child in sorted(os.scandir(directory), key=lambda item: item.name):
                child_path = directory / child.name
                child_stat = os.lstat(child_path)
                if stat.S_ISLNK(child_stat.st_mode) or _is_reparse(child_stat):
                    raise LifecycleIndeterminateError(
                        "Manifest contains a link/reparse point"
                    )
                if child_stat.st_dev != root_device:
                    raise LifecycleIndeterminateError(
                        "Manifest crossed a device boundary"
                    )
                if stat.S_ISDIR(child_stat.st_mode):
                    if os.path.ismount(child_path):
                        raise LifecycleIndeterminateError(
                            "Manifest contains a mount point"
                        )
                    probe = find_probe(child_path)
                    if probe is not None:
                        return probe
                    continue
                if not stat.S_ISREG(child_stat.st_mode):
                    raise LifecycleIndeterminateError(
                        "Manifest contains a special file"
                    )
                return child_path
            return None

        probe_path = find_probe(root_path)
        if probe_path is None:
            return True

        path_stat = os.lstat(probe_path)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptors = []
        try:
            for _attempt in range(2):
                descriptor = os.open(os.fspath(probe_path), flags)
                descriptors.append(descriptor)
            opened_stats = [os.fstat(descriptor) for descriptor in descriptors]
        finally:
            for descriptor in descriptors:
                os.close(descriptor)
        rebound = os.lstat(probe_path)
        identities = (path_stat, *opened_stats, rebound)
        return all(usable(value) for value in identities) and all(
            cls._same_entry_identity(path_stat, value)
            for value in identities[1:]
        )

    @staticmethod
    def _manifest_stat_observation(path_stat: os.stat_result) -> Tuple[int, int]:
        size = getattr(path_stat, "st_size", None)
        modified_ns = getattr(path_stat, "st_mtime_ns", None)
        if not isinstance(size, int) or not isinstance(modified_ns, int):
            raise LifecycleIndeterminateError(
                "Manifest content-stability metadata is unavailable"
            )
        return size, modified_ns

    @classmethod
    def _walk_manifest_once(
        cls,
        root_path: Path,
        root_device: int,
        *,
        stable_file_ids: bool,
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Tuple[int, int]]]:
        """Read one manifest pass using identity or content-stability proof."""
        entries: Dict[str, Dict[str, Any]] = {".": {"kind": "directory"}}
        observations: Dict[str, Tuple[int, int]] = {}

        def walk(directory: Path, relative: Path) -> None:
            before = cls._require_plain_directory(directory)
            if before.st_dev != root_device:
                raise LifecycleIndeterminateError("Manifest crossed a device boundary")
            children = sorted(os.scandir(directory), key=lambda item: item.name)
            folded = set()
            for child in children:
                folded_name = child.name.casefold()
                if folded_name in folded:
                    raise LifecycleIndeterminateError("Manifest contains a case alias")
                folded.add(folded_name)
                child_path = directory / child.name
                child_relative = relative / child.name
                relative_text = child_relative.as_posix()
                child_stat = os.lstat(child_path)
                if stat.S_ISLNK(child_stat.st_mode) or _is_reparse(child_stat):
                    raise LifecycleIndeterminateError(
                        "Manifest contains a link/reparse point"
                    )
                if child_stat.st_dev != root_device:
                    raise LifecycleIndeterminateError(
                        "Manifest crossed a device boundary"
                    )
                if stat.S_ISDIR(child_stat.st_mode):
                    if os.path.ismount(child_path):
                        raise LifecycleIndeterminateError(
                            "Manifest contains a mount point"
                        )
                    entries[relative_text] = {"kind": "directory"}
                    walk(child_path, child_relative)
                    continue
                if not stat.S_ISREG(child_stat.st_mode):
                    raise LifecycleIndeterminateError(
                        "Manifest contains a special file"
                    )
                digest = hashlib.sha256()
                total = 0
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(os.fspath(child_path), flags)
                try:
                    opened = os.fstat(descriptor)
                    if stable_file_ids:
                        if (
                            opened.st_dev != child_stat.st_dev
                            or opened.st_ino != child_stat.st_ino
                            or not stat.S_ISREG(opened.st_mode)
                        ):
                            raise LifecycleIndeterminateError(
                                "Manifest file identity changed"
                            )
                    elif (
                        opened.st_dev != child_stat.st_dev
                        or not stat.S_ISREG(opened.st_mode)
                        or cls._manifest_stat_observation(opened)
                        != cls._manifest_stat_observation(child_stat)
                    ):
                        raise LifecycleIndeterminateError(
                            "Manifest file changed before read"
                        )
                    while True:
                        chunk = os.read(descriptor, 1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        total += len(chunk)
                    final_stat = os.fstat(descriptor)
                    rebound = os.lstat(child_path)
                    if stable_file_ids:
                        if (
                            final_stat.st_dev != child_stat.st_dev
                            or final_stat.st_ino != child_stat.st_ino
                            or rebound.st_dev != child_stat.st_dev
                            or rebound.st_ino != child_stat.st_ino
                            or total != final_stat.st_size
                        ):
                            raise LifecycleIndeterminateError(
                                "Manifest file changed while read"
                            )
                    else:
                        observation = cls._manifest_stat_observation(child_stat)
                        if (
                            final_stat.st_dev != child_stat.st_dev
                            or rebound.st_dev != child_stat.st_dev
                            or not stat.S_ISREG(final_stat.st_mode)
                            or not stat.S_ISREG(rebound.st_mode)
                            or cls._manifest_stat_observation(final_stat)
                            != observation
                            or cls._manifest_stat_observation(rebound)
                            != observation
                            or total != final_stat.st_size
                        ):
                            raise LifecycleIndeterminateError(
                                "Manifest file changed while read"
                            )
                finally:
                    os.close(descriptor)
                entries[relative_text] = {
                    "kind": "file",
                    "size": total,
                    "sha256": digest.hexdigest(),
                }
                if not stable_file_ids:
                    observations[relative_text] = observation
            after = os.lstat(directory)
            if stable_file_ids:
                if before.st_dev != after.st_dev or before.st_ino != after.st_ino:
                    raise LifecycleIndeterminateError(
                        "Manifest directory identity changed"
                    )
            else:
                if (
                    after.st_dev != root_device
                    or not stat.S_ISDIR(after.st_mode)
                    or cls._manifest_stat_observation(after)
                    != cls._manifest_stat_observation(before)
                ):
                    raise LifecycleIndeterminateError(
                        "Manifest directory changed while read"
                    )
                observations[relative.as_posix()] = (
                    cls._manifest_stat_observation(before)
                )

        walk(root_path, Path("."))
        return dict(sorted(entries.items())), dict(sorted(observations.items()))

    @staticmethod
    def manifest_digest(manifest: Mapping[str, Mapping[str, Any]]) -> str:
        return hashlib.sha256(_canonical_json_bytes(manifest)).hexdigest()

    @classmethod
    def _sync_tree(cls, root: Path) -> None:
        # Validate first, then synchronize every regular file and directory.
        cls.create_manifest(root)
        directories: List[Path] = []
        for directory, child_dirs, child_files in os.walk(root, followlinks=False):
            directory_path = Path(directory)
            directories.append(directory_path)
            child_dirs.sort()
            child_files.sort()
            for filename in child_files:
                path = directory_path / filename
                path_stat = os.lstat(path)
                if not stat.S_ISREG(path_stat.st_mode) or _is_reparse(path_stat):
                    raise LifecycleIndeterminateError("Tree sync found an unsafe file")
                descriptor = os.open(
                    os.fspath(path),
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                )
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        for directory in reversed(directories):
            cls._sync_directory(directory)

    # ------------------------------------------------------------------
    # Intent/outcome serialization
    # ------------------------------------------------------------------
    @staticmethod
    def _intent_value(
        *,
        build_id: str,
        token: str,
        kind: LifecycleKind,
        requested_name: str,
        final_name: str,
        phase: LifecyclePhase,
        manifest_digest: Optional[str],
        prior_registry_digest: Optional[str] = None,
        candidate_registry_digest: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "build_id": build_id,
            "token": token,
            "kind": kind.value,
            "requested_name": requested_name,
            "final_name": final_name,
            "phase": phase.value,
            "manifest_digest": manifest_digest,
            "prior_registry_digest": prior_registry_digest,
            "candidate_registry_digest": candidate_registry_digest,
        }

    @classmethod
    def _load_intent(cls, transaction: Path) -> Dict[str, Any]:
        value = _strict_json_load(transaction / "intent.json")
        required = {
            "schema_version",
            "build_id",
            "token",
            "kind",
            "requested_name",
            "final_name",
            "phase",
            "manifest_digest",
            "prior_registry_digest",
            "candidate_registry_digest",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise LifecycleIndeterminateError("Lifecycle intent shape is invalid")
        if value["schema_version"] != SCHEMA_VERSION:
            raise LifecycleIndeterminateError("Lifecycle intent version is unsupported")
        _validate_uuid(value["build_id"])
        _validate_uuid(value["token"])
        try:
            LifecycleKind(value["kind"])
            LifecyclePhase(value["phase"])
        except (TypeError, ValueError) as exc:
            raise LifecycleIndeterminateError(
                "Lifecycle intent enum is invalid"
            ) from exc
        validate_module_name(value["requested_name"])
        validate_module_name(value["final_name"])
        for digest_field in (
            "manifest_digest",
            "prior_registry_digest",
            "candidate_registry_digest",
        ):
            digest = value[digest_field]
            if digest is not None and (
                not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise LifecycleIndeterminateError(
                    f"Lifecycle {digest_field} is invalid"
                )
        if (value["prior_registry_digest"] is None) != (
            value["candidate_registry_digest"] is None
        ):
            raise LifecycleIndeterminateError(
                "Lifecycle registry preparation is incomplete"
            )
        return value

    @classmethod
    def _write_intent(
        cls,
        transaction: Path,
        intent: Mapping[str, Any],
        *,
        phase: LifecyclePhase,
        manifest_digest: Optional[str] = None,
    ) -> Dict[str, Any]:
        updated = dict(intent)
        updated["phase"] = phase.value
        updated["manifest_digest"] = manifest_digest
        cls._atomic_write_json(transaction / "intent.json", updated)
        return updated

    @staticmethod
    def _outcome_value(
        intent: Mapping[str, Any],
        status: LifecycleStatus,
        *,
        manifest_digest: Optional[str],
        reason_code: str,
        acknowledged: bool = True,
        message_id: Optional[str] = None,
        message_digest: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "build_id": intent["build_id"],
            "token": intent["token"],
            "kind": intent["kind"],
            "module_name": intent["final_name"],
            "status": status.value,
            "manifest_digest": manifest_digest,
            "reason_code": reason_code,
            "acknowledged": acknowledged,
            "message_id": message_id,
            "message_digest": message_digest,
            "idempotency_key": idempotency_key,
        }

    @classmethod
    def _load_outcome(cls, transaction: Path) -> LifecycleOutcome:
        value = _strict_json_load(transaction / "outcome.json")
        required = {
            "schema_version",
            "build_id",
            "token",
            "kind",
            "module_name",
            "status",
            "manifest_digest",
            "reason_code",
            "acknowledged",
            "message_id",
            "message_digest",
            "idempotency_key",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise LifecycleIndeterminateError("Lifecycle outcome shape is invalid")
        if value["schema_version"] != SCHEMA_VERSION:
            raise LifecycleIndeterminateError(
                "Lifecycle outcome version is unsupported"
            )
        build_id = _validate_uuid(value["build_id"])
        token = _validate_uuid(value["token"])
        try:
            kind = LifecycleKind(value["kind"])
            status_value = LifecycleStatus(value["status"])
        except (TypeError, ValueError) as exc:
            raise LifecycleIndeterminateError(
                "Lifecycle outcome enum is invalid"
            ) from exc
        module_name = validate_module_name(value["module_name"])
        digest = value["manifest_digest"]
        if digest is not None and (
            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise LifecycleIndeterminateError("Lifecycle outcome digest is invalid")
        if type(value["acknowledged"]) is not bool:
            raise LifecycleIndeterminateError("Lifecycle acknowledgment is invalid")
        reason = value["reason_code"]
        if not isinstance(reason, str) or not re.fullmatch(r"[A-Z0-9_]+", reason):
            raise LifecycleIndeterminateError("Lifecycle reason code is invalid")
        for field_name in ("message_id", "message_digest", "idempotency_key"):
            field_value = value[field_name]
            if field_value is not None and (
                not isinstance(field_value, str) or not field_value
            ):
                raise LifecycleIndeterminateError(f"Lifecycle {field_name} is invalid")
        if value["message_digest"] is not None and not re.fullmatch(
            r"[0-9a-f]{64}", value["message_digest"]
        ):
            raise LifecycleIndeterminateError("Lifecycle message digest is invalid")
        return LifecycleOutcome(
            build_id,
            token,
            kind,
            module_name,
            status_value,
            digest,
            value["acknowledged"],
            reason,
            value["message_id"],
            value["message_digest"],
            value["idempotency_key"],
        )

    @classmethod
    def _write_outcome(
        cls,
        transaction: Path,
        intent: Mapping[str, Any],
        status: LifecycleStatus,
        *,
        manifest_digest: Optional[str],
        reason_code: str,
        acknowledged: bool = True,
        message_id: Optional[str] = None,
        message_digest: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> LifecycleOutcome:
        value = cls._outcome_value(
            intent,
            status,
            manifest_digest=manifest_digest,
            reason_code=reason_code,
            acknowledged=acknowledged,
            message_id=message_id,
            message_digest=message_digest,
            idempotency_key=idempotency_key,
        )
        cls._atomic_write_json(transaction / "outcome.json", value)
        return cls._load_outcome(transaction)

    @staticmethod
    def _load_manifest(transaction: Path) -> Dict[str, Dict[str, Any]]:
        value = _strict_json_load(transaction / "candidate_manifest.json")
        if not isinstance(value, dict) or not value:
            raise LifecycleIndeterminateError("Candidate manifest is invalid")
        for relative_path, entry in value.items():
            if not isinstance(relative_path, str) or not relative_path:
                raise LifecycleIndeterminateError("Candidate manifest path is invalid")
            if relative_path != ".":
                parts = relative_path.split("/")
                if any(part in {"", ".", ".."} for part in parts):
                    raise LifecycleIndeterminateError("Candidate manifest traverses")
            if not isinstance(entry, dict) or entry.get("kind") not in {
                "directory",
                "file",
            }:
                raise LifecycleIndeterminateError("Candidate manifest entry is invalid")
            if entry["kind"] == "directory" and set(entry) != {"kind"}:
                raise LifecycleIndeterminateError("Directory manifest entry is invalid")
            if entry["kind"] == "file":
                if set(entry) != {"kind", "size", "sha256"}:
                    raise LifecycleIndeterminateError("File manifest entry is invalid")
                if type(entry["size"]) is not int or entry["size"] < 0:
                    raise LifecycleIndeterminateError("Manifest file size is invalid")
                if not isinstance(entry["sha256"], str) or not re.fullmatch(
                    r"[0-9a-f]{64}", entry["sha256"]
                ):
                    raise LifecycleIndeterminateError("Manifest file digest is invalid")
        return value

    # ------------------------------------------------------------------
    # Build allocation / activation / promotion
    # ------------------------------------------------------------------
    def _occupied_names(self) -> set[str]:
        self.ensure_layout()
        occupied = {entry.name.casefold() for entry in os.scandir(self.modules_dir)}
        for root in (self.staging_root, self.active_root):
            for transaction in self._transaction_directories(root):
                intent = self._load_intent(transaction)
                occupied.add(intent["final_name"].casefold())
        return occupied

    def allocate_final_name(self, requested_name: str) -> str:
        base = validate_module_name(requested_name)
        assert_module_refresh_owned()
        occupied = self._occupied_names()
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
                raise LifecycleIndeterminateError("Module suffix space is exhausted")

    def begin_build(
        self,
        requested_name: str,
        kind: LifecycleKind,
        *,
        final_name: Optional[str] = None,
    ) -> BuildWorkspace:
        requested = validate_module_name(requested_name)
        if not isinstance(kind, LifecycleKind):
            raise ValueError("Lifecycle kind must be explicit")
        final = validate_module_name(final_name or requested)
        assert_module_refresh_owned()
        self.ensure_layout()
        build_id = str(uuid4())
        token = str(uuid4())
        transaction = self._transaction_path(self.staging_root, build_id)
        self._mkdir_exact(transaction, parent=self.staging_root)
        candidate_root = transaction / "candidate"
        self._mkdir_exact(candidate_root, parent=transaction)
        candidate_path = candidate_root / final
        self._mkdir_exact(candidate_path, parent=candidate_root)
        intent = self._intent_value(
            build_id=build_id,
            token=token,
            kind=kind,
            requested_name=requested,
            final_name=final,
            phase=LifecyclePhase.BUILDING,
            manifest_digest=None,
        )
        self._atomic_write_json(transaction / "intent.json", intent)
        self._sync_directory(transaction)
        return BuildWorkspace(
            build_id,
            token,
            kind,
            requested,
            final,
            transaction,
            candidate_path,
        )

    def _validate_workspace(self, workspace: BuildWorkspace) -> Dict[str, Any]:
        if type(workspace) is not BuildWorkspace:
            raise LifecycleIndeterminateError("Exact BuildWorkspace is required")
        expected = self._transaction_path(self.staging_root, workspace.build_id)
        if workspace.transaction_path != expected:
            raise LifecycleIndeterminateError("Workspace path is not authoritative")
        self._require_plain_directory(expected)
        intent = self._load_intent(expected)
        if (
            intent["build_id"] != workspace.build_id
            or intent["token"] != workspace.token
            or intent["kind"] != workspace.kind.value
            or intent["requested_name"] != workspace.requested_name
            or intent["final_name"] != workspace.final_name
            or workspace.candidate_path != expected / "candidate" / workspace.final_name
        ):
            raise LifecycleIndeterminateError(
                "Workspace identity does not match intent"
            )
        return intent

    @classmethod
    def _story_first_resume_value(
        cls,
        workspace: BuildWorkspace,
        *,
        stage: str,
        failure_class: str,
        issues: Iterable[Mapping[str, str]],
        retries_remaining: int = 1,
    ) -> Dict[str, Any]:
        if (
            not isinstance(stage, str)
            or not stage
            or len(stage) > 64
            or not re.fullmatch(r"[a-z0-9_:-]+", stage)
        ):
            raise ValueError("Story-first failure stage is invalid")
        if failure_class not in _STORY_FIRST_FAILURE_CLASSES:
            raise ValueError("Story-first failure class is invalid")
        if retries_remaining not in {0, 1}:
            raise ValueError("Story-first retry allowance is invalid")
        safe_issues = []
        for issue in list(issues):
            if len(safe_issues) >= 24:
                raise ValueError("Story-first diagnostic issue limit exceeded")
            if (
                not isinstance(issue, Mapping)
                or set(issue) != _STORY_FIRST_DIAGNOSTIC_FIELDS
            ):
                raise ValueError("Story-first diagnostic issue shape is invalid")
            safe_issue = {}
            for field in sorted(_STORY_FIRST_DIAGNOSTIC_FIELDS):
                value = issue[field]
                if not isinstance(value, str) or not value or len(value) > 240:
                    raise ValueError("Story-first diagnostic issue text is invalid")
                try:
                    value.encode("ascii")
                except UnicodeEncodeError as exc:
                    raise ValueError(
                        "Story-first diagnostic issue must be ASCII"
                    ) from exc
                if _CREDENTIAL_SHAPED_TEXT.search(value):
                    raise ValueError(
                        "Credential-shaped story-first diagnostic is forbidden"
                    )
                safe_issue[field] = value
            safe_issues.append(safe_issue)
        return {
            "schema_version": SCHEMA_VERSION,
            "build_id": workspace.build_id,
            "token": workspace.token,
            "kind": workspace.kind.value,
            "requested_name": workspace.requested_name,
            "final_name": workspace.final_name,
            "stage": stage,
            "failure_class": failure_class,
            "issues": safe_issues,
            "retries_remaining": retries_remaining,
        }

    @classmethod
    def _load_story_first_resume(
        cls, transaction: Path, intent: Mapping[str, Any]
    ) -> Dict[str, Any]:
        value = _strict_json_load(transaction / _STORY_FIRST_RESUME_FILE)
        required = {
            "schema_version",
            "build_id",
            "token",
            "kind",
            "requested_name",
            "final_name",
            "stage",
            "failure_class",
            "issues",
            "retries_remaining",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise LifecycleIndeterminateError(
                "Story-first resume evidence shape is invalid"
            )
        workspace = BuildWorkspace(
            intent["build_id"],
            intent["token"],
            LifecycleKind(intent["kind"]),
            intent["requested_name"],
            intent["final_name"],
            transaction,
            transaction / "candidate" / intent["final_name"],
        )
        try:
            expected = cls._story_first_resume_value(
                workspace,
                stage=value["stage"],
                failure_class=value["failure_class"],
                issues=value["issues"],
                retries_remaining=value["retries_remaining"],
            )
        except (TypeError, ValueError) as exc:
            raise LifecycleIndeterminateError(
                "Story-first resume evidence is invalid"
            ) from exc
        if value != expected:
            raise LifecycleIndeterminateError(
                "Story-first resume identity differs from lifecycle intent"
            )
        return value

    def stage_story_first_resume(
        self,
        workspace: BuildWorkspace,
        *,
        stage: str,
        failure_class: str,
        issues: Iterable[Mapping[str, str]] = (),
        retries_remaining: int = 1,
    ) -> None:
        """Attach one bounded, sanitized retry marker before normal retirement."""
        assert_module_refresh_owned()
        intent = self._validate_workspace(workspace)
        if LifecyclePhase(intent["phase"]) is not LifecyclePhase.BUILDING:
            raise LifecycleIndeterminateError(
                "Only a building candidate can become story-first resumable"
            )
        candidate = workspace.candidate_path
        self._require_plain_directory(candidate)
        story_workspace = candidate / ".story_first"
        self._require_plain_directory(story_workspace)
        if not (story_workspace / "pipeline_state.json").is_file():
            raise LifecycleIndeterminateError(
                "Story-first resume requires pipeline state"
            )
        value = self._story_first_resume_value(
            workspace,
            stage=stage,
            failure_class=failure_class,
            issues=issues,
            retries_remaining=retries_remaining,
        )
        self._atomic_write_json(
            workspace.transaction_path / _STORY_FIRST_RESUME_FILE, value
        )
        self._sync_directory(workspace.transaction_path)

    def claim_story_first_resume(
        self, requested_name: str, kind: LifecycleKind
    ) -> Optional[BuildWorkspace]:
        """Reclaim the exact retired UUID candidate for its one bounded retry."""
        requested = validate_module_name(requested_name)
        if not isinstance(kind, LifecycleKind):
            raise ValueError("Lifecycle kind must be explicit")
        assert_module_refresh_owned()
        self.ensure_layout()
        matches = []
        for transaction in self._transaction_directories(self.resolved_root):
            marker = transaction / _STORY_FIRST_RESUME_FILE
            if not marker.exists():
                continue
            intent = self._load_intent(transaction)
            evidence = self._load_story_first_resume(transaction, intent)
            if (
                evidence["requested_name"] == requested
                and evidence["kind"] == kind.value
                and evidence["retries_remaining"] == 1
            ):
                matches.append((transaction, intent, evidence))
        if len(matches) > 1:
            raise LifecycleIndeterminateError(
                "Multiple resumable story-first candidates match"
            )
        if not matches:
            return None
        transaction, intent, evidence = matches[0]
        outcome = self._load_outcome(transaction)
        if (
            LifecyclePhase(intent["phase"]) is not LifecyclePhase.NOT_PUBLISHED
            or outcome.status is not LifecycleStatus.NOT_PUBLISHED
            or outcome.reason_code != "BUILD_FAILED"
        ):
            raise LifecycleIndeterminateError(
                "Resumable story-first outcome is not a failed hidden build"
            )
        candidate = transaction / "candidate" / intent["final_name"]
        self._require_plain_directory(candidate)
        self._require_plain_directory(candidate / ".story_first")
        staging = self._transaction_path(self.staging_root, intent["build_id"])
        if self._entry_stat(staging) is not None:
            raise LifecycleIndeterminateError(
                "Story-first resume staging identity is occupied"
            )
        self._replace_entry(transaction, staging)
        self._sync_directory(self.resolved_root)
        self._sync_directory(self.staging_root)
        resumed_intent = self._load_intent(staging)
        self._write_intent(
            staging,
            resumed_intent,
            phase=LifecyclePhase.BUILDING,
            manifest_digest=None,
        )
        (staging / "outcome.json").unlink()
        resumed_workspace = BuildWorkspace(
            intent["build_id"],
            intent["token"],
            kind,
            intent["requested_name"],
            intent["final_name"],
            staging,
            staging / "candidate" / intent["final_name"],
        )
        self._atomic_write_json(
            staging / _STORY_FIRST_RESUME_FILE,
            self._story_first_resume_value(
                resumed_workspace,
                stage=evidence["stage"],
                failure_class=evidence["failure_class"],
                issues=evidence["issues"],
                retries_remaining=0,
            ),
        )
        self._sync_directory(staging)
        return resumed_workspace

    def finish_story_first_resume(self, workspace: BuildWorkspace) -> None:
        """Consume a claimed marker before candidate preparation/activation."""
        assert_module_refresh_owned()
        self._validate_workspace(workspace)
        marker = workspace.transaction_path / _STORY_FIRST_RESUME_FILE
        if marker.exists():
            marker.unlink()
            self._sync_directory(workspace.transaction_path)

    @staticmethod
    def _validate_registry_snapshot(payload: bytes) -> Dict[str, Any]:
        value = _strict_json_bytes(payload)
        if not isinstance(value, dict):
            raise ValueError("Registry snapshot must be a JSON object")
        if not isinstance(value.get("modules"), dict):
            raise ValueError("Registry snapshot modules must be an object")
        if not isinstance(value.get("areas"), dict):
            raise ValueError("Registry snapshot areas must be an object")
        return value

    def stage_registry_preparation(
        self,
        workspace: BuildWorkspace,
        preparation: RegistryPreparation,
    ) -> Tuple[str, str]:
        """Durably bind exact prior/candidate registry bytes before activation."""
        assert_module_refresh_owned()
        intent = self._validate_workspace(workspace)
        if LifecyclePhase(intent["phase"]) is not LifecyclePhase.BUILDING:
            raise LifecycleIndeterminateError(
                "Registry bytes can be prepared only while BUILDING"
            )
        if type(preparation) is not RegistryPreparation:
            raise ValueError("Exact RegistryPreparation is required")
        prior = preparation.prior_registry_bytes
        candidate = preparation.candidate_registry_bytes
        self._validate_registry_snapshot(prior)
        self._validate_registry_snapshot(candidate)
        prior_digest = hashlib.sha256(prior).hexdigest()
        candidate_digest = hashlib.sha256(candidate).hexdigest()
        self._atomic_write_bytes(
            workspace.transaction_path / "prior_registry.bin", prior
        )
        self._atomic_write_bytes(
            workspace.transaction_path / "candidate_registry.bin", candidate
        )
        updated = dict(intent)
        updated["prior_registry_digest"] = prior_digest
        updated["candidate_registry_digest"] = candidate_digest
        self._atomic_write_json(workspace.transaction_path / "intent.json", updated)
        self._sync_directory(workspace.transaction_path)
        return prior_digest, candidate_digest

    def read_registry_preparation(
        self, active: ActiveCandidate
    ) -> Optional[RegistryPreparation]:
        """Return verified exact bytes attached to an immutable READY handle."""
        intent = self._validate_active(active)
        prior_digest = intent["prior_registry_digest"]
        candidate_digest = intent["candidate_registry_digest"]
        if prior_digest is None and candidate_digest is None:
            return None
        prior = (active.transaction_path / "prior_registry.bin").read_bytes()
        candidate = (active.transaction_path / "candidate_registry.bin").read_bytes()
        self._validate_registry_snapshot(prior)
        self._validate_registry_snapshot(candidate)
        if (
            hashlib.sha256(prior).hexdigest() != prior_digest
            or hashlib.sha256(candidate).hexdigest() != candidate_digest
        ):
            raise LifecycleIndeterminateError("Prepared registry bytes differ")
        return RegistryPreparation(prior, candidate)

    @staticmethod
    def _validate_receipt_fields(
        message_id: str,
        message_digest: str,
        idempotency_key: str,
    ) -> None:
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("message_id must be opaque non-empty text")
        if not isinstance(message_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", message_digest
        ):
            raise ValueError("message_digest must be SHA-256 hex")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ValueError("idempotency_key must be opaque non-empty text")

    def _load_publication_receipt_metadata(
        self,
        transaction: Path,
        intent: Mapping[str, Any],
    ) -> PublicationReceiptMetadata:
        try:
            value = _strict_json_load(transaction / "publication_receipt.json")
        except (OSError, UnicodeError, ValueError) as exc:
            raise LifecycleIndeterminateError(
                "Publication receipt metadata is unavailable"
            ) from exc
        required = {
            "schema_version",
            "build_id",
            "token",
            "kind",
            "module_name",
            "manifest_digest",
            "message_id",
            "message_digest",
            "idempotency_key",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise LifecycleIndeterminateError(
                "Publication receipt metadata shape is invalid"
            )
        if value["schema_version"] != SCHEMA_VERSION:
            raise LifecycleIndeterminateError(
                "Publication receipt metadata version is unsupported"
            )
        try:
            self._validate_receipt_fields(
                value["message_id"],
                value["message_digest"],
                value["idempotency_key"],
            )
        except ValueError as exc:
            raise LifecycleIndeterminateError(
                "Publication receipt metadata is invalid"
            ) from exc
        if (
            value["build_id"] != intent["build_id"]
            or value["token"] != intent["token"]
            or value["kind"] != LifecycleKind.ACTION.value
            or value["kind"] != intent["kind"]
            or value["module_name"] != intent["final_name"]
            or value["manifest_digest"] != intent["manifest_digest"]
        ):
            raise LifecycleIndeterminateError(
                "Publication receipt metadata identity differs"
            )
        return PublicationReceiptMetadata(
            value["build_id"],
            value["token"],
            value["module_name"],
            value["manifest_digest"],
            value["message_id"],
            value["message_digest"],
            value["idempotency_key"],
        )

    def stage_publication_receipt(
        self,
        active: ActiveCandidate,
        *,
        message_id: str,
        message_digest: str,
        idempotency_key: str,
    ) -> PublicationReceiptMetadata:
        """Durably bind delivery identity before an ACTION becomes public."""
        assert_module_refresh_owned()
        intent = self._validate_active(active)
        if active.kind is not LifecycleKind.ACTION:
            raise LifecycleIndeterminateError(
                "Only ACTION publication stages receipt metadata"
            )
        if LifecyclePhase(intent["phase"]) is not LifecyclePhase.READY:
            raise LifecycleIndeterminateError(
                "Receipt metadata can be staged only while READY"
            )
        self._validate_receipt_fields(
            message_id,
            message_digest,
            idempotency_key,
        )
        if not os.path.lexists(active.candidate_path) or os.path.lexists(
            active.final_path
        ):
            raise LifecycleIndeterminateError(
                "Receipt metadata must be staged before promotion"
            )
        path = active.transaction_path / "publication_receipt.json"
        value = {
            "schema_version": SCHEMA_VERSION,
            "build_id": active.build_id,
            "token": active.token,
            "kind": active.kind.value,
            "module_name": active.final_name,
            "manifest_digest": active.manifest_digest,
            "message_id": message_id,
            "message_digest": message_digest,
            "idempotency_key": idempotency_key,
        }
        if os.path.lexists(path):
            existing = self._load_publication_receipt_metadata(
                active.transaction_path,
                intent,
            )
            expected = PublicationReceiptMetadata(
                active.build_id,
                active.token,
                active.final_name,
                active.manifest_digest,
                message_id,
                message_digest,
                idempotency_key,
            )
            if existing != expected:
                raise LifecycleIndeterminateError(
                    "Publication receipt metadata is already bound differently"
                )
            return existing
        self._atomic_write_json(path, value)
        self._sync_directory(active.transaction_path)
        return self._load_publication_receipt_metadata(
            active.transaction_path,
            intent,
        )

    def read_publication_receipt(
        self,
        active: ActiveCandidate,
    ) -> PublicationReceiptMetadata:
        """Read and verify the pre-promotion receipt identity for an ACTION."""
        intent = self._validate_active(active)
        return self._load_publication_receipt_metadata(
            active.transaction_path,
            intent,
        )

    def activate_ready(self, workspace: BuildWorkspace) -> ActiveCandidate:
        assert_module_refresh_owned()
        intent = self._validate_workspace(workspace)
        if LifecyclePhase(intent["phase"]) is not LifecyclePhase.BUILDING:
            raise LifecycleIndeterminateError("Only a BUILDING workspace can activate")
        self._sync_tree(workspace.candidate_path)
        manifest = self.create_manifest(workspace.candidate_path)
        digest = self.manifest_digest(manifest)
        self._atomic_write_json(
            workspace.transaction_path / "candidate_manifest.json", manifest
        )
        prior_digest = intent["prior_registry_digest"]
        candidate_digest = intent["candidate_registry_digest"]
        if workspace.kind in {LifecycleKind.ACTION, LifecycleKind.DISCOVERY}:
            if prior_digest is None or candidate_digest is None:
                raise LifecycleIndeterminateError(
                    "Action/discovery activation requires exact registry preparation"
                )
        elif prior_digest is not None or candidate_digest is not None:
            raise LifecycleIndeterminateError(
                "Toolkit activation cannot carry publication registry authority"
            )
        if prior_digest is not None:
            prior = (workspace.transaction_path / "prior_registry.bin").read_bytes()
            candidate = (
                workspace.transaction_path / "candidate_registry.bin"
            ).read_bytes()
            self._validate_registry_snapshot(prior)
            self._validate_registry_snapshot(candidate)
            if (
                hashlib.sha256(prior).hexdigest() != prior_digest
                or hashlib.sha256(candidate).hexdigest() != candidate_digest
            ):
                raise LifecycleIndeterminateError(
                    "Prepared registry evidence changed before activation"
                )
        intent = self._write_intent(
            workspace.transaction_path,
            intent,
            phase=LifecyclePhase.READY,
            manifest_digest=digest,
        )
        self._sync_directory(workspace.transaction_path)

        active_path = self._transaction_path(self.active_root, workspace.build_id)
        if self._entry_stat(active_path) is not None:
            raise LifecycleIndeterminateError("Active transaction identity is occupied")
        self._replace_entry(workspace.transaction_path, active_path)
        self._sync_directory(self.staging_root)
        self._sync_directory(self.active_root)
        return ActiveCandidate(
            workspace.build_id,
            workspace.token,
            workspace.kind,
            workspace.requested_name,
            workspace.final_name,
            active_path,
            active_path / "candidate" / workspace.final_name,
            self.modules_dir / workspace.final_name,
            manifest,
            digest,
            prior_digest,
            candidate_digest,
        )

    def activation_retry_safe(self, workspace: BuildWorkspace) -> bool:
        """Return whether activation has not crossed its durable READY boundary."""
        assert_module_refresh_owned()
        intent = self._validate_workspace(workspace)
        return LifecyclePhase(intent["phase"]) is LifecyclePhase.BUILDING

    def _validate_active(self, active: ActiveCandidate) -> Dict[str, Any]:
        if type(active) is not ActiveCandidate:
            raise LifecycleIndeterminateError("Exact ActiveCandidate is required")
        expected = self._transaction_path(self.active_root, active.build_id)
        if active.transaction_path != expected:
            raise LifecycleIndeterminateError("Active path is not authoritative")
        self._require_plain_directory(expected)
        intent = self._load_intent(expected)
        manifest = self._load_manifest(expected)
        digest = self.manifest_digest(manifest)
        if (
            intent["build_id"] != active.build_id
            or intent["token"] != active.token
            or intent["kind"] != active.kind.value
            or intent["requested_name"] != active.requested_name
            or intent["final_name"] != active.final_name
            or intent["manifest_digest"] != active.manifest_digest
            or intent["prior_registry_digest"] != active.prior_registry_digest
            or intent["candidate_registry_digest"] != active.candidate_registry_digest
            or digest != active.manifest_digest
            or dict(active.manifest) != manifest
            or active.candidate_path != expected / "candidate" / active.final_name
            or active.final_path != self.modules_dir / active.final_name
        ):
            raise LifecycleIndeterminateError("Active identity does not match intent")
        return intent

    def _retire(self, transaction: Path, build_id: str) -> Path:
        resolved = self._transaction_path(self.resolved_root, build_id)
        if self._entry_stat(resolved) is not None:
            raise LifecycleIndeterminateError(
                "Resolved transaction identity is occupied"
            )
        source_parent = transaction.parent
        self._replace_entry(transaction, resolved)
        self._sync_directory(source_parent)
        self._sync_directory(self.resolved_root)
        return resolved

    def abort_build(
        self,
        workspace: BuildWorkspace,
        *,
        reason_code: str = "BUILD_FAILED",
    ) -> LifecycleOutcome:
        assert_module_refresh_owned()
        intent = self._validate_workspace(workspace)
        outcome = self._write_outcome(
            workspace.transaction_path,
            intent,
            LifecycleStatus.NOT_PUBLISHED,
            manifest_digest=None,
            reason_code=reason_code,
        )
        self._write_intent(
            workspace.transaction_path,
            intent,
            phase=LifecyclePhase.NOT_PUBLISHED,
            manifest_digest=None,
        )
        self._retire(workspace.transaction_path, workspace.build_id)
        return outcome

    def promote_generated(self, active: ActiveCandidate) -> GeneratedModule:
        assert_module_refresh_owned()
        intent = self._validate_active(active)
        if active.kind is not LifecycleKind.TOOLKIT:
            raise LifecycleIndeterminateError(
                "Only TOOLKIT candidates may use GENERATED promotion"
            )
        phase = LifecyclePhase(intent["phase"])
        if phase is not LifecyclePhase.READY:
            raise LifecycleIndeterminateError("Only a READY candidate can promote")
        current = self.create_manifest(active.candidate_path)
        if self.manifest_digest(current) != active.manifest_digest:
            raise LifecycleIndeterminateError("Candidate changed after activation")
        if os.path.lexists(active.final_path):
            raise LifecycleIndeterminateError("Final module path is occupied")
        if any(
            entry.name.casefold() == active.final_name.casefold()
            for entry in os.scandir(self.modules_dir)
        ):
            raise LifecycleIndeterminateError("A final-name alias is occupied")

        self._replace_entry(active.candidate_path, active.final_path)
        self._sync_directory(active.candidate_path.parent)
        self._sync_directory(self.modules_dir)
        final_manifest = self.create_manifest(active.final_path)
        if (
            final_manifest != dict(active.manifest)
            or self.manifest_digest(final_manifest) != active.manifest_digest
        ):
            raise LifecycleIndeterminateError("Promoted module manifest differs")

        outcome = self._write_outcome(
            active.transaction_path,
            intent,
            LifecycleStatus.GENERATED,
            manifest_digest=active.manifest_digest,
            reason_code="EXACT_PROMOTION",
        )
        self._write_intent(
            active.transaction_path,
            intent,
            phase=LifecyclePhase.GENERATED,
            manifest_digest=active.manifest_digest,
        )
        self._retire(active.transaction_path, active.build_id)
        return GeneratedModule(
            outcome.build_id,
            outcome.token,
            outcome.kind,
            outcome.module_name,
            active.final_path,
            active.manifest_digest,
        )

    def promote_for_publication(self, active: ActiveCandidate) -> ActiveCandidate:
        """Promote an exact ACTION candidate but retain active WAL authority.

        Registry replacement and receipt persistence intentionally remain
        separate operations owned by publication.  A crash after this rename
        is therefore left active for the stitcher's exact registry matrix.
        """
        assert_module_refresh_owned()
        intent = self._validate_active(active)
        if active.kind is not LifecycleKind.ACTION:
            raise LifecycleIndeterminateError(
                "Only ACTION candidates use publication promotion"
            )
        if LifecyclePhase(intent["phase"]) is not LifecyclePhase.READY:
            raise LifecycleIndeterminateError("Publication candidate is not READY")
        if (
            active.prior_registry_digest is None
            or active.candidate_registry_digest is None
        ):
            raise LifecycleIndeterminateError(
                "Publication registry proof is unavailable"
            )
        # Delivery identity is part of the write-ahead evidence.  It must be
        # durable before either the module rename or registry replacement.
        self.read_publication_receipt(active)
        if self.create_manifest(active.candidate_path) != dict(active.manifest):
            raise LifecycleIndeterminateError("Publication candidate manifest differs")
        if os.path.lexists(active.final_path) or any(
            entry.name.casefold() == active.final_name.casefold()
            for entry in os.scandir(self.modules_dir)
        ):
            raise LifecycleIndeterminateError("Publication final path is occupied")
        self._replace_entry(active.candidate_path, active.final_path)
        self._sync_directory(active.candidate_path.parent)
        self._sync_directory(self.modules_dir)
        if self.create_manifest(active.final_path) != dict(active.manifest):
            raise LifecycleIndeterminateError("Publication promotion manifest differs")
        return active

    def record_published_receipt(
        self,
        active: ActiveCandidate,
        *,
        message_id: str,
        message_digest: str,
        idempotency_key: str,
    ) -> PendingReceipt:
        """Retire an exact committed ACTION with a durable pending receipt."""
        assert_module_refresh_owned()
        intent = self._validate_active(active)
        if active.kind is not LifecycleKind.ACTION:
            raise LifecycleIndeterminateError("Only ACTION publication has a receipt")
        self._validate_receipt_fields(
            message_id,
            message_digest,
            idempotency_key,
        )
        staged = self.read_publication_receipt(active)
        if (
            staged.message_id != message_id
            or staged.message_digest != message_digest
            or staged.idempotency_key != idempotency_key
        ):
            raise LifecycleIndeterminateError(
                "Published receipt differs from pre-promotion metadata"
            )
        if os.path.lexists(active.candidate_path):
            raise LifecycleIndeterminateError("Publication candidate is not promoted")
        final_manifest = self.create_manifest(active.final_path)
        if final_manifest != dict(active.manifest):
            raise LifecycleIndeterminateError("Published module manifest differs")
        prepared = self.read_registry_preparation(active)
        if prepared is None:
            raise LifecycleIndeterminateError("Published registry proof is unavailable")
        live_registry = (self.modules_dir / "world_registry.json").read_bytes()
        if live_registry != prepared.candidate_registry_bytes:
            raise LifecycleIndeterminateError("Live registry is not exact candidate")

        outcome = self._write_outcome(
            active.transaction_path,
            intent,
            LifecycleStatus.PUBLISHED,
            manifest_digest=active.manifest_digest,
            reason_code="EXACT_PUBLICATION",
            acknowledged=False,
            message_id=message_id,
            message_digest=message_digest,
            idempotency_key=idempotency_key,
        )
        self._write_intent(
            active.transaction_path,
            intent,
            phase=LifecyclePhase.PUBLISHED,
            manifest_digest=active.manifest_digest,
        )
        self._retire(active.transaction_path, active.build_id)
        return PendingReceipt(
            outcome.build_id,
            outcome.module_name,
            outcome.status,
            active.manifest_digest,
            message_id,
            message_digest,
            idempotency_key,
        )

    def _load_delivery_plan(
        self,
        transaction: Path,
        outcome: LifecycleOutcome,
    ) -> ReceiptDeliveryPlan:
        value = _strict_json_load(transaction / "delivery_plan.json")
        required = {
            "schema_version",
            "build_id",
            "message_ids",
            "suffix_digest",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise LifecycleIndeterminateError("Receipt delivery plan shape is invalid")
        message_ids = value["message_ids"]
        suffix_digest = value["suffix_digest"]
        if (
            value["schema_version"] != SCHEMA_VERSION
            or value["build_id"] != outcome.build_id
            or not isinstance(message_ids, list)
            or not message_ids
            or any(not isinstance(item, str) or not item for item in message_ids)
            or len(set(message_ids)) != len(message_ids)
            or not isinstance(suffix_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", suffix_digest)
        ):
            raise LifecycleIndeterminateError("Receipt delivery plan is invalid")
        return ReceiptDeliveryPlan(
            outcome.build_id,
            tuple(message_ids),
            suffix_digest,
        )

    def plan_receipt_delivery(
        self,
        *,
        build_id: str,
        message_ids: Iterable[str],
        suffix_digest: str,
    ) -> ReceiptDeliveryPlan:
        """Persist an exact successful follow-up suffix before history save."""
        assert_module_refresh_owned()
        transaction = self._transaction_path(
            self.resolved_root,
            _validate_uuid(build_id),
        )
        self._require_plain_directory(transaction)
        outcome = self._load_outcome(transaction)
        if outcome.status is not LifecycleStatus.PUBLISHED:
            raise LifecycleIndeterminateError(
                "Delivery plan has no publication receipt"
            )
        normalized_ids = tuple(message_ids)
        if (
            not normalized_ids
            or any(not isinstance(item, str) or not item for item in normalized_ids)
            or len(set(normalized_ids)) != len(normalized_ids)
            or not isinstance(suffix_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", suffix_digest)
        ):
            raise ValueError("Delivery plan proof is invalid")
        path = transaction / "delivery_plan.json"
        expected = ReceiptDeliveryPlan(
            outcome.build_id,
            normalized_ids,
            suffix_digest,
        )
        if path.exists():
            existing = self._load_delivery_plan(transaction, outcome)
            if existing != expected:
                raise LifecycleIndeterminateError(
                    "Receipt delivery plan is already bound differently"
                )
            return existing
        self._atomic_write_json(
            path,
            {
                "schema_version": SCHEMA_VERSION,
                "build_id": outcome.build_id,
                "message_ids": list(normalized_ids),
                "suffix_digest": suffix_digest,
            },
        )
        self._sync_directory(transaction)
        return self._load_delivery_plan(transaction, outcome)

    def read_receipt_delivery_plan(
        self,
        *,
        build_id: str,
    ) -> Optional[ReceiptDeliveryPlan]:
        transaction = self._transaction_path(
            self.resolved_root,
            _validate_uuid(build_id),
        )
        self._require_plain_directory(transaction)
        outcome = self._load_outcome(transaction)
        path = transaction / "delivery_plan.json"
        if not path.exists():
            return None
        return self._load_delivery_plan(transaction, outcome)

    def acknowledge_receipt(
        self,
        *,
        build_id: str,
        message_id: str,
        message_digest: str,
        planned_message_ids: Optional[Iterable[str]] = None,
        planned_suffix_digest: Optional[str] = None,
    ) -> LifecycleOutcome:
        """Mark one exact resolved receipt acknowledged after history proof."""
        assert_module_refresh_owned()
        transaction = self._transaction_path(
            self.resolved_root,
            _validate_uuid(build_id),
        )
        self._require_plain_directory(transaction)
        intent = self._load_intent(transaction)
        outcome = self._load_outcome(transaction)
        if (
            outcome.status is not LifecycleStatus.PUBLISHED
            or outcome.message_id != message_id
            or outcome.message_digest != message_digest
            or not outcome.idempotency_key
        ):
            raise LifecycleIndeterminateError("Receipt acknowledgment proof differs")
        if outcome.acknowledged:
            return outcome
        delivery_path = transaction / "delivery_plan.json"
        if delivery_path.exists():
            delivery = self._load_delivery_plan(transaction, outcome)
            if planned_message_ids is not None or planned_suffix_digest is not None:
                if (
                    tuple(planned_message_ids or ()) != delivery.message_ids
                    or planned_suffix_digest != delivery.suffix_digest
                ):
                    raise LifecycleIndeterminateError(
                        "Receipt delivery acknowledgment differs from its plan"
                    )
            elif (
                message_id != outcome.message_id
                or message_digest != outcome.message_digest
            ):
                raise LifecycleIndeterminateError(
                    "Planned delivery requires exact suffix proof"
                )
        value = self._outcome_value(
            intent,
            LifecycleStatus.PUBLISHED,
            manifest_digest=outcome.manifest_digest,
            reason_code=outcome.reason_code,
            acknowledged=True,
            message_id=outcome.message_id,
            message_digest=outcome.message_digest,
            idempotency_key=outcome.idempotency_key,
        )
        self._atomic_write_json(transaction / "outcome.json", value)
        return self._load_outcome(transaction)

    def invalidate_pending_publication_receipts_for_reset(
        self,
    ) -> Tuple[LifecycleOutcome, ...]:
        """Retire pre-reset delivery authority without claiming delivery.

        A confirmed campaign reset starts a new player timeline.  Publication
        receipts from the old timeline must remain as durable evidence, but
        they must never be delivered into the fresh conversation history.
        Callers must recover the lifecycle first so only RESOLVED evidence is
        rewritten.
        """
        assert_module_refresh_owned()
        self._require_layout()
        if self._transaction_directories(
            self.staging_root
        ) or self._transaction_directories(self.active_root):
            raise LifecycleIndeterminateError(
                "Campaign reset requires a fully recovered module lifecycle"
            )

        invalidated: List[LifecycleOutcome] = []
        for transaction in self._transaction_directories(self.resolved_root):
            intent = self._load_intent(transaction)
            outcome = self._load_outcome(transaction)
            if outcome.status is not LifecycleStatus.PUBLISHED or outcome.acknowledged:
                continue
            if (
                outcome.kind is not LifecycleKind.ACTION
                or not outcome.manifest_digest
                or not outcome.message_id
                or not outcome.message_digest
                or not outcome.idempotency_key
            ):
                raise LifecycleIndeterminateError(
                    "Pending publication receipt is incomplete"
                )
            value = self._outcome_value(
                intent,
                LifecycleStatus.PUBLISHED,
                manifest_digest=outcome.manifest_digest,
                reason_code="INVALIDATED_BY_CAMPAIGN_RESET",
                acknowledged=True,
                message_id=outcome.message_id,
                message_digest=outcome.message_digest,
                idempotency_key=outcome.idempotency_key,
            )
            self._atomic_write_json(transaction / "outcome.json", value)
            invalidated.append(self._load_outcome(transaction))
        return tuple(invalidated)

    # ------------------------------------------------------------------
    # Recovery and durable lookup
    # ------------------------------------------------------------------
    def _transaction_directories(self, root: Path) -> List[Path]:
        self._require_plain_directory(root)
        result = []
        for entry in sorted(os.scandir(root), key=lambda item: item.name):
            try:
                _validate_uuid(entry.name)
            except ValueError as exc:
                raise LifecycleIndeterminateError(
                    f"Unknown lifecycle entry under {root.name}"
                ) from exc
            path = root / entry.name
            self._require_plain_directory(path)
            result.append(path)
        return result

    def _resolve_hidden_transaction(
        self,
        transaction: Path,
        intent: Mapping[str, Any],
        *,
        reason_code: str,
    ) -> LifecycleOutcome:
        digest = intent.get("manifest_digest")
        outcome_path = transaction / "outcome.json"
        if outcome_path.exists():
            outcome = self._load_outcome(transaction)
        else:
            outcome = self._write_outcome(
                transaction,
                intent,
                LifecycleStatus.NOT_PUBLISHED,
                manifest_digest=digest,
                reason_code=reason_code,
            )
        self._write_intent(
            transaction,
            intent,
            phase=LifecyclePhase.NOT_PUBLISHED,
            manifest_digest=digest,
        )
        self._retire(transaction, intent["build_id"])
        return outcome

    def _recover_active(
        self, transaction: Path, intent: Mapping[str, Any]
    ) -> LifecycleOutcome:
        manifest = self._load_manifest(transaction)
        digest = self.manifest_digest(manifest)
        if digest != intent["manifest_digest"]:
            raise LifecycleIndeterminateError("Active manifest digest differs")
        candidate = transaction / "candidate" / intent["final_name"]
        final = self.modules_dir / intent["final_name"]
        candidate_exists = os.path.lexists(candidate)
        final_exists = os.path.lexists(final)
        if candidate_exists and final_exists:
            raise LifecycleIndeterminateError("Both hidden and public candidates exist")
        if not candidate_exists and not final_exists:
            raise LifecycleIndeterminateError("Active candidate evidence is missing")

        kind = LifecycleKind(intent["kind"])
        if kind is not LifecycleKind.TOOLKIT:
            prior_path = transaction / "prior_registry.bin"
            candidate_registry_path = transaction / "candidate_registry.bin"
            prior_bytes = prior_path.read_bytes()
            candidate_registry_bytes = candidate_registry_path.read_bytes()
            if (
                hashlib.sha256(prior_bytes).hexdigest()
                != intent["prior_registry_digest"]
                or hashlib.sha256(candidate_registry_bytes).hexdigest()
                != intent["candidate_registry_digest"]
            ):
                raise LifecycleIndeterminateError(
                    "Publication registry evidence differs"
                )
            self._validate_registry_snapshot(prior_bytes)
            self._validate_registry_snapshot(candidate_registry_bytes)
            live_registry = (self.modules_dir / "world_registry.json").read_bytes()
            if candidate_exists:
                candidate_manifest = self.create_manifest(candidate)
                if candidate_manifest != manifest:
                    raise LifecycleIndeterminateError(
                        "Hidden publication candidate manifest differs"
                    )
                if live_registry != prior_bytes:
                    raise LifecycleIndeterminateError(
                        "Hidden publication has non-prior live registry state"
                    )
                return self._resolve_hidden_transaction(
                    transaction,
                    intent,
                    reason_code="INTERRUPTED_BEFORE_PUBLICATION",
                )

            final_manifest = self.create_manifest(final)
            if final_manifest != manifest:
                raise LifecycleIndeterminateError(
                    "Promoted publication candidate manifest differs"
                )
            if kind is not LifecycleKind.ACTION:
                raise LifecycleIndeterminateError(
                    "Promoted discovery candidate requires publication recovery"
                )

            if live_registry == prior_bytes:
                # The public rename happened but registry publication did not.
                # Move only the exact token-owned tree back under its empty
                # authoritative candidate parent, verify it, then retire as
                # NOT_PUBLISHED.  No path-derived recursive deletion occurs.
                candidate_parent = candidate.parent
                self._require_plain_directory(candidate_parent)
                if os.path.lexists(candidate):
                    raise LifecycleIndeterminateError(
                        "Publication rollback target is occupied"
                    )
                self._replace_entry(final, candidate)
                self._sync_directory(self.modules_dir)
                self._sync_directory(candidate_parent)
                if (
                    os.path.lexists(final)
                    or self.create_manifest(candidate) != manifest
                ):
                    raise LifecycleIndeterminateError(
                        "Publication rollback could not be proven"
                    )
                return self._resolve_hidden_transaction(
                    transaction,
                    intent,
                    reason_code="RECOVERED_BEFORE_REGISTRY_COMMIT",
                )

            if live_registry == candidate_registry_bytes:
                staged = self._load_publication_receipt_metadata(
                    transaction,
                    intent,
                )
                outcome = self._write_outcome(
                    transaction,
                    intent,
                    LifecycleStatus.PUBLISHED,
                    manifest_digest=digest,
                    reason_code="RECOVERED_EXACT_PUBLICATION",
                    acknowledged=False,
                    message_id=staged.message_id,
                    message_digest=staged.message_digest,
                    idempotency_key=staged.idempotency_key,
                )
                self._write_intent(
                    transaction,
                    intent,
                    phase=LifecyclePhase.PUBLISHED,
                    manifest_digest=digest,
                )
                self._retire(transaction, intent["build_id"])
                return outcome

            raise LifecycleIndeterminateError(
                "Promoted publication has an unknown live registry state"
            )

        if candidate_exists:
            candidate_manifest = self.create_manifest(candidate)
            if candidate_manifest != manifest:
                raise LifecycleIndeterminateError("Hidden candidate manifest differs")
            return self._resolve_hidden_transaction(
                transaction,
                intent,
                reason_code="INTERRUPTED_BEFORE_PROMOTION",
            )

        final_manifest = self.create_manifest(final)
        if final_manifest != manifest:
            raise LifecycleIndeterminateError("Promoted candidate manifest differs")
        outcome_path = transaction / "outcome.json"
        if outcome_path.exists():
            outcome = self._load_outcome(transaction)
            if outcome.status not in {
                LifecycleStatus.GENERATED,
                LifecycleStatus.PUBLISHED,
            }:
                raise LifecycleIndeterminateError("Promoted outcome is inconsistent")
        else:
            outcome = self._write_outcome(
                transaction,
                intent,
                LifecycleStatus.GENERATED,
                manifest_digest=digest,
                reason_code="RECOVERED_EXACT_PROMOTION",
            )
        target_phase = (
            LifecyclePhase.PUBLISHED
            if outcome.status is LifecycleStatus.PUBLISHED
            else LifecyclePhase.GENERATED
        )
        self._write_intent(
            transaction,
            intent,
            phase=target_phase,
            manifest_digest=digest,
        )
        self._retire(transaction, intent["build_id"])
        return outcome

    def _recover_once(self) -> RecoveryReport:
        """Perform one complete recovery classification pass."""
        self.ensure_layout()
        # Resolved records are retained evidence and must remain parseable.
        for transaction in self._transaction_directories(self.resolved_root):
            intent = self._load_intent(transaction)
            outcome = self._load_outcome(transaction)
            if (
                intent["build_id"] != transaction.name
                or outcome.build_id != transaction.name
                or intent["token"] != outcome.token
                or intent["final_name"] != outcome.module_name
            ):
                raise LifecycleIndeterminateError(
                    "Resolved intent/outcome identity differs"
                )

        active = self._transaction_directories(self.active_root)
        if len(active) > 1:
            raise LifecycleIndeterminateError(
                "Multiple active lifecycle authorities exist"
            )

        outcomes: List[LifecycleOutcome] = []
        for transaction in self._transaction_directories(self.staging_root):
            intent = self._load_intent(transaction)
            if intent["build_id"] != transaction.name:
                raise LifecycleIndeterminateError("Staging identity differs")
            phase = LifecyclePhase(intent["phase"])
            if phase not in {
                LifecyclePhase.BUILDING,
                LifecyclePhase.READY,
                LifecyclePhase.NOT_PUBLISHED,
            }:
                raise LifecycleIndeterminateError("Staging phase is impossible")
            outcomes.append(
                self._resolve_hidden_transaction(
                    transaction,
                    intent,
                    reason_code="INTERRUPTED_HIDDEN_BUILD",
                )
            )

        if active:
            transaction = active[0]
            intent = self._load_intent(transaction)
            if intent["build_id"] != transaction.name:
                raise LifecycleIndeterminateError("Active identity differs")
            outcomes.append(self._recover_active(transaction, intent))

        return RecoveryReport(
            RecoveryStatus.RECOVERED if outcomes else RecoveryStatus.STABLE,
            tuple(outcomes),
        )

    def recover(self) -> RecoveryReport:
        """Classify exact crash states after a bounded fresh-scan retry."""
        assert_module_refresh_owned()
        for attempt in range(1, _MANIFEST_MAX_ATTEMPTS + 1):
            try:
                return self._recover_once()
            except OSError as exc:
                if not is_transient_filesystem_error(
                    exc,
                    allow_missing=True,
                ):
                    return RecoveryReport(
                        RecoveryStatus.INDETERMINATE,
                        (),
                        str(exc),
                    )
                if attempt < _MANIFEST_MAX_ATTEMPTS:
                    time.sleep(_MANIFEST_RETRY_BACKOFF_SECONDS * attempt)
                    continue
                return RecoveryReport(
                    RecoveryStatus.INDETERMINATE,
                    (),
                    f"{exc} after {attempt} recovery attempts",
                )
            except (ValueError, LifecycleIndeterminateError) as exc:
                return RecoveryReport(
                    RecoveryStatus.INDETERMINATE,
                    (),
                    str(exc),
                )
        raise AssertionError("unreachable recovery retry state")

    def find_ready_candidate(
        self,
        *,
        build_id: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> Optional[ActiveCandidate]:
        self._require_layout()
        if build_id is not None:
            _validate_uuid(build_id)
        if module_name is not None:
            validate_module_name(module_name)
        matches: List[ActiveCandidate] = []
        for transaction in self._transaction_directories(self.active_root):
            intent = self._load_intent(transaction)
            if LifecyclePhase(intent["phase"]) is not LifecyclePhase.READY:
                continue
            if build_id is not None and intent["build_id"] != build_id:
                continue
            if module_name is not None and intent["final_name"] != module_name:
                continue
            manifest = self._load_manifest(transaction)
            digest = self.manifest_digest(manifest)
            candidate = transaction / "candidate" / intent["final_name"]
            if (
                digest != intent["manifest_digest"]
                or self.create_manifest(candidate) != manifest
            ):
                raise LifecycleIndeterminateError("READY candidate evidence differs")
            matches.append(
                ActiveCandidate(
                    intent["build_id"],
                    intent["token"],
                    LifecycleKind(intent["kind"]),
                    intent["requested_name"],
                    intent["final_name"],
                    transaction,
                    candidate,
                    self.modules_dir / intent["final_name"],
                    manifest,
                    digest,
                    intent["prior_registry_digest"],
                    intent["candidate_registry_digest"],
                )
            )
        if len(matches) > 1:
            raise LifecycleIndeterminateError("READY candidate lookup is ambiguous")
        return matches[0] if matches else None

    def find_generated_module(
        self,
        *,
        build_id: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> Optional[GeneratedModule]:
        self._require_layout()
        if build_id is not None:
            _validate_uuid(build_id)
        if module_name is not None:
            validate_module_name(module_name)
        matches: List[GeneratedModule] = []
        for transaction in self._transaction_directories(self.resolved_root):
            outcome = self._load_outcome(transaction)
            if outcome.status not in {
                LifecycleStatus.GENERATED,
                LifecycleStatus.PUBLISHED,
            }:
                continue
            if build_id is not None and outcome.build_id != build_id:
                continue
            if module_name is not None and outcome.module_name != module_name:
                continue
            if outcome.manifest_digest is None:
                raise LifecycleIndeterminateError("Generated outcome has no manifest")
            final = self.modules_dir / outcome.module_name
            manifest = self.create_manifest(final)
            if self.manifest_digest(manifest) != outcome.manifest_digest:
                raise LifecycleIndeterminateError("Generated module manifest differs")
            matches.append(
                GeneratedModule(
                    outcome.build_id,
                    outcome.token,
                    outcome.kind,
                    outcome.module_name,
                    final,
                    outcome.manifest_digest,
                    outcome.status,
                )
            )
        if len(matches) > 1:
            raise LifecycleIndeterminateError("Generated lookup is ambiguous")
        return matches[0] if matches else None

    def list_publication_receipts(self) -> Tuple[PendingReceipt, ...]:
        """Enumerate exact committed ACTION receipts, including acknowledged."""
        self._require_layout()
        matches: List[PendingReceipt] = []
        seen = set()
        for root in (self.active_root, self.resolved_root):
            for transaction in self._transaction_directories(root):
                outcome_path = transaction / "outcome.json"
                if not outcome_path.exists():
                    continue
                outcome = self._load_outcome(transaction)
                if outcome.status is not LifecycleStatus.PUBLISHED:
                    continue
                if not (
                    outcome.manifest_digest
                    and outcome.message_id
                    and outcome.message_digest
                    and outcome.idempotency_key
                ):
                    raise LifecycleIndeterminateError(
                        "Publication receipt is incomplete"
                    )
                identity = (outcome.build_id, outcome.idempotency_key)
                if identity in seen:
                    raise LifecycleIndeterminateError(
                        "Publication receipt is duplicated"
                    )
                seen.add(identity)
                matches.append(
                    PendingReceipt(
                        outcome.build_id,
                        outcome.module_name,
                        outcome.status,
                        outcome.manifest_digest,
                        outcome.message_id,
                        outcome.message_digest,
                        outcome.idempotency_key,
                        outcome.acknowledged,
                    )
                )
        return tuple(matches)

    def find_publication_receipt(
        self,
        *,
        build_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> Optional[PendingReceipt]:
        """Return one exact committed publication receipt, if present."""
        self._require_layout()
        if build_id is not None:
            _validate_uuid(build_id)
        if module_name is not None:
            validate_module_name(module_name)
        matches = [
            receipt
            for receipt in self.list_publication_receipts()
            if (build_id is None or receipt.build_id == build_id)
            and (idempotency_key is None or receipt.idempotency_key == idempotency_key)
            and (module_name is None or receipt.module_name == module_name)
        ]
        if len(matches) > 1:
            raise LifecycleIndeterminateError("Publication receipt lookup is ambiguous")
        return matches[0] if matches else None

    def find_pending_receipt(
        self,
        *,
        build_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> Optional[PendingReceipt]:
        """Return one exact unacknowledged publication receipt, if present."""
        matches = [
            receipt
            for receipt in self.list_publication_receipts()
            if not receipt.acknowledged
            and (build_id is None or receipt.build_id == build_id)
            and (idempotency_key is None or receipt.idempotency_key == idempotency_key)
            and (module_name is None or receipt.module_name == module_name)
        ]
        if len(matches) > 1:
            raise LifecycleIndeterminateError("Pending receipt lookup is ambiguous")
        return matches[0] if matches else None
