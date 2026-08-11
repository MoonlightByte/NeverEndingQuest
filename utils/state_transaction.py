# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Crash-recoverable coordination for multi-file JSON state changes.

Models and validators prepare complete before/after images outside this module.
This module owns only deterministic mechanics: canonical lock ordering, stale
snapshot rejection, durable intent journaling, atomic participant writes, and
compare-and-swap recovery.  Recovery never invokes a model and never guesses
when a participant has diverged from both journaled states.
"""

from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
import re
import threading
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)
from uuid import uuid4

from utils.path_transaction_lock import path_transaction_lock


JOURNAL_SCHEMA_VERSION = 1
DEFAULT_JOURNAL_ROOT = os.path.join("modules", "transactions")
MAX_JOURNAL_BYTES = 128 * 1024 * 1024
MAX_PARTICIPANTS = 64
_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_TRANSACTION_ID = re.compile(r"^[0-9a-f]{64}$")


class TransactionError(RuntimeError):
    """Base class for deterministic state-transaction failures."""


class TransactionBusyError(TransactionError):
    """The ordered participant leases could not be acquired in time."""


class TransactionStalePlanError(TransactionError):
    """A prepared participant changed before its commit boundary."""


class TransactionBlockedError(TransactionError):
    """An unresolved journal already owns one or more participants."""


class TransactionRecoveryRequiredError(TransactionError):
    """The coordinator cannot safely choose a state without recovery."""

    def __init__(self, transaction_id: str, failure_code: str):
        super().__init__(failure_code)
        self.transaction_id = transaction_id
        self.failure_code = failure_code


class TransactionAbortedError(TransactionError):
    """A prepared transaction was restored to its exact pre-images."""

    def __init__(self, transaction_id: str, failure_code: str):
        super().__init__(failure_code)
        self.transaction_id = transaction_id
        self.failure_code = failure_code


class TransactionJournalError(TransactionRecoveryRequiredError):
    """A journal is malformed, unsafe, or inconsistent with its identity."""


class LockOrderError(TransactionError):
    """A caller attempted to acquire a lease in reverse global order."""


class ParticipantKind(str, Enum):
    ENCOUNTER = "encounter"
    CHARACTER = "character"
    STORAGE = "storage"
    VALIDATION_CACHE = "validation_cache"


class JournalPhase(str, Enum):
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


_KIND_ORDER = {
    ParticipantKind.ENCOUNTER: 10,
    ParticipantKind.CHARACTER: 20,
    ParticipantKind.STORAGE: 30,
    ParticipantKind.VALIDATION_CACHE: 40,
}

_LOCK_SUFFIX = {
    ParticipantKind.ENCOUNTER: ".combat.lock",
    ParticipantKind.CHARACTER: ".effects.lock",
    ParticipantKind.STORAGE: ".storage.lock",
    ParticipantKind.VALIDATION_CACHE: ".validation-cache.lock",
}

_LOCK_STATE = threading.local()


@dataclass(frozen=True, init=False)
class JsonSnapshot:
    """One exact semantic JSON state, including the missing-file state."""

    exists: bool
    _encoded: Optional[str]
    _digest: str

    def __init__(self, exists: bool, value: Any = None) -> None:
        if type(exists) is not bool:
            raise TypeError("snapshot exists flag must be boolean")
        if not exists and value is not None:
            raise ValueError("a missing snapshot cannot carry a JSON value")
        encoded = None
        if exists:
            encoded = _canonical_json_bytes(value).decode("utf-8")
        object.__setattr__(self, "exists", exists)
        object.__setattr__(self, "_encoded", encoded)
        payload = b"MISSING\0" if not exists else b"JSON\0" + encoded.encode("utf-8")
        object.__setattr__(self, "_digest", hashlib.sha256(payload).hexdigest())

    @property
    def value(self) -> Any:
        if not self.exists:
            return None
        return json.loads(
            self._encoded,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_json_constant,
        )

    @property
    def digest(self) -> str:
        return self._digest


@dataclass(frozen=True)
class ParticipantPlan:
    """A fully prepared participant mutation with no remaining model work."""

    canonical_path: str
    kind: ParticipantKind
    before: JsonSnapshot
    after: JsonSnapshot

    @property
    def pre_hash(self) -> str:
        return self.before.digest

    @property
    def post_hash(self) -> str:
        return self.after.digest

    @property
    def lock_suffix(self) -> str:
        return _LOCK_SUFFIX[self.kind]


@dataclass(frozen=True)
class TransactionPlan:
    transaction_id: str
    transaction_key: str
    operation: str
    rollback_failure_code: str
    commit_recovery_code: str
    participants: Tuple[ParticipantPlan, ...]


@dataclass(frozen=True)
class TransactionResult:
    transaction_id: str
    phase: JournalPhase
    replayed: bool = False


@dataclass(frozen=True)
class RecoveryResult:
    transaction_id: str
    phase: JournalPhase
    failure_code: Optional[str] = None
    blocked_all: bool = False


@dataclass(frozen=True)
class PendingReceipt:
    transaction_id: str
    failure_code: str


def _reject_json_constant(value: str) -> None:
    raise ValueError("non-finite JSON number: %s" % value)


def _reject_duplicate_pairs(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    value: Dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _snapshot_digest(snapshot: JsonSnapshot) -> str:
    return snapshot.digest


def _journal_checksum(journal: Mapping[str, Any]) -> str:
    payload = dict(journal)
    payload.pop("journal_checksum", None)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _safe_code(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_CODE.fullmatch(value):
        raise ValueError("invalid %s" % label)
    return value


def _durable_sync_directory(path: str) -> None:
    """Persist a directory entry where the platform exposes directory fsync."""
    if os.name == "nt" or not hasattr(os, "O_DIRECTORY"):
        return
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            unsupported = {
                errno.EBADF,
                errno.EINVAL,
                errno.EPERM,
                getattr(errno, "ENOTSUP", errno.EINVAL),
            }
            if exc.errno not in unsupported:
                raise
    finally:
        os.close(descriptor)


def _durable_write_json(path: str, value: Any) -> None:
    canonical = os.path.abspath(os.path.normpath(path))
    parent = os.path.dirname(canonical)
    os.makedirs(parent, exist_ok=True)
    temporary = os.path.join(
        parent,
        ".%s.%s.%s.%s.tmp"
        % (
            os.path.basename(canonical),
            os.getpid(),
            threading.get_ident(),
            uuid4().hex,
        ),
    )
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, canonical)
        _durable_sync_directory(parent)
    finally:
        try:
            os.remove(temporary)
        except FileNotFoundError:
            pass


def _durable_remove(path: str) -> None:
    canonical = os.path.abspath(os.path.normpath(path))
    try:
        os.remove(canonical)
    except FileNotFoundError:
        return
    _durable_sync_directory(os.path.dirname(canonical))


def _durable_move(source: str, destination: str) -> None:
    source = os.path.abspath(os.path.normpath(source))
    destination = os.path.abspath(os.path.normpath(destination))
    destination_parent = os.path.dirname(destination)
    os.makedirs(destination_parent, exist_ok=True)
    os.replace(source, destination)
    _durable_sync_directory(os.path.dirname(source))
    if destination_parent != os.path.dirname(source):
        _durable_sync_directory(destination_parent)


def _load_json_strict(path: str, *, max_bytes: Optional[int] = None) -> Any:
    if max_bytes is not None and os.path.getsize(path) > max_bytes:
        raise ValueError("JSON file exceeds the safe size limit")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_json_constant,
        )


class StateTransactionCoordinator:
    """Coordinate prepared JSON mutations under one durable recovery authority."""

    def __init__(
        self,
        workspace_root: str = ".",
        journal_root: str = DEFAULT_JOURNAL_ROOT,
        default_timeout_seconds: float = 5.0,
    ) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        root = journal_root
        if not os.path.isabs(root):
            root = os.path.join(self.workspace_root, root)
        self.journal_root = self._canonical_inside_workspace(root)
        self.active_root = os.path.join(self.journal_root, "active")
        self.resolved_root = os.path.join(self.journal_root, "resolved")
        self.registry_target = os.path.join(self.journal_root, ".registry")
        self.default_timeout_seconds = max(0.0, float(default_timeout_seconds))

    def _canonical_inside_workspace(self, path: str) -> str:
        canonical = os.path.realpath(os.path.abspath(os.path.normpath(os.fspath(path))))
        try:
            inside = (
                os.path.commonpath((self.workspace_root, canonical))
                == self.workspace_root
            )
        except ValueError as exc:
            raise ValueError("transaction path is outside the workspace") from exc
        if not inside:
            raise ValueError("transaction path is outside the workspace")
        return canonical

    def snapshot(self, value: Any = None, *, exists: bool = True) -> JsonSnapshot:
        return JsonSnapshot(exists=exists, value=value if exists else None)

    def read_snapshot(self, path: str) -> JsonSnapshot:
        canonical = self._canonical_inside_workspace(path)
        try:
            return JsonSnapshot(True, _load_json_strict(canonical))
        except FileNotFoundError:
            return JsonSnapshot(False)

    def participant(
        self,
        path: str,
        kind: ParticipantKind,
        before: JsonSnapshot,
        after: JsonSnapshot,
    ) -> ParticipantPlan:
        if not isinstance(kind, ParticipantKind):
            kind = ParticipantKind(kind)
        if not isinstance(before, JsonSnapshot) or not isinstance(after, JsonSnapshot):
            raise TypeError("participant states must be JsonSnapshot values")
        canonical = self._canonical_inside_workspace(path)
        if canonical == self.journal_root or canonical.startswith(
            self.journal_root + os.sep
        ):
            raise ValueError("transaction journals cannot be participants")
        if before.digest == after.digest:
            raise ValueError("transaction participant has no state change")
        return ParticipantPlan(canonical, kind, before, after)

    def build_plan(
        self,
        *,
        transaction_key: str,
        operation: str,
        participants: Iterable[ParticipantPlan],
        rollback_failure_code: str = "transaction_rolled_back",
        commit_recovery_code: str = "recovery_completed_delayed",
    ) -> TransactionPlan:
        transaction_key = _safe_code(transaction_key, "transaction key")
        operation = _safe_code(operation, "operation")
        rollback_failure_code = _safe_code(
            rollback_failure_code, "rollback failure code"
        )
        commit_recovery_code = _safe_code(commit_recovery_code, "commit recovery code")
        ordered = self._ordered_participants(tuple(participants))
        if not ordered:
            raise ValueError("a transaction requires at least one participant")
        material = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "transaction_key": transaction_key,
            "operation": operation,
            "participants": [
                {
                    "kind": item.kind.value,
                    "path": item.canonical_path,
                    "pre_hash": item.pre_hash,
                    "post_hash": item.post_hash,
                }
                for item in ordered
            ],
        }
        transaction_id = hashlib.sha256(_canonical_json_bytes(material)).hexdigest()
        return TransactionPlan(
            transaction_id=transaction_id,
            transaction_key=transaction_key,
            operation=operation,
            rollback_failure_code=rollback_failure_code,
            commit_recovery_code=commit_recovery_code,
            participants=ordered,
        )

    def _validate_plan(self, plan: TransactionPlan) -> None:
        _safe_code(plan.transaction_key, "transaction key")
        _safe_code(plan.operation, "operation")
        _safe_code(plan.rollback_failure_code, "rollback failure code")
        _safe_code(plan.commit_recovery_code, "commit recovery code")
        ordered = self._ordered_participants(plan.participants)
        if ordered != plan.participants:
            raise ValueError("transaction plan participants are not ordered")
        material = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "transaction_key": plan.transaction_key,
            "operation": plan.operation,
            "participants": [
                {
                    "kind": item.kind.value,
                    "path": item.canonical_path,
                    "pre_hash": item.pre_hash,
                    "post_hash": item.post_hash,
                }
                for item in ordered
            ],
        }
        expected = hashlib.sha256(_canonical_json_bytes(material)).hexdigest()
        if plan.transaction_id != expected:
            raise ValueError("transaction plan identity mismatch")

    def _participant_order_key(
        self, participant: ParticipantPlan
    ) -> Tuple[int, str, str]:
        normalized = participant.canonical_path.replace("\\", "/")
        return (_KIND_ORDER[participant.kind], normalized.casefold(), normalized)

    def _ordered_participants(
        self, participants: Sequence[ParticipantPlan]
    ) -> Tuple[ParticipantPlan, ...]:
        if len(participants) > MAX_PARTICIPANTS:
            raise ValueError("transaction has too many participants")
        seen_paths: Dict[str, str] = {}
        checked: List[ParticipantPlan] = []
        for participant in participants:
            if not isinstance(participant, ParticipantPlan):
                raise TypeError("participants must be ParticipantPlan values")
            canonical = self._canonical_inside_workspace(participant.canonical_path)
            if canonical != participant.canonical_path:
                raise ValueError("participant path is not canonical")
            identity = canonical.replace("\\", "/").casefold()
            if identity in seen_paths:
                raise ValueError("duplicate or case-ambiguous participant path")
            seen_paths[identity] = canonical
            checked.append(participant)
        return tuple(sorted(checked, key=self._participant_order_key))

    @contextmanager
    def ordered_leases(
        self,
        participants: Iterable[ParticipantPlan],
        *,
        timeout_seconds: Optional[float] = None,
    ) -> Iterator[Tuple[str, ...]]:
        ordered = self._ordered_participants(tuple(participants))
        if timeout_seconds is None:
            timeout_seconds = self.default_timeout_seconds
        timeout_seconds = max(0.0, float(timeout_seconds))
        deadline = time.monotonic() + timeout_seconds
        keys = tuple(self._participant_order_key(item) for item in ordered)
        active = getattr(_LOCK_STATE, "keys", ())
        if active and keys and keys[0] < active[-1]:
            raise LockOrderError("reverse transaction lease acquisition")
        with ExitStack() as stack:
            acquired_paths: List[str] = []
            previous = active
            try:
                for participant, key in zip(ordered, keys):
                    remaining = max(0.0, deadline - time.monotonic())
                    acquired = stack.enter_context(
                        path_transaction_lock(
                            participant.canonical_path,
                            suffix=participant.lock_suffix,
                            timeout_seconds=remaining,
                        )
                    )
                    if acquired is None:
                        raise TransactionBusyError(
                            "timed out acquiring participant leases"
                        )
                    acquired_paths.append(acquired)
                    _LOCK_STATE.keys = previous + keys[: len(acquired_paths)]
                yield tuple(acquired_paths)
            finally:
                _LOCK_STATE.keys = previous

    @contextmanager
    def _registry_lease(self, timeout_seconds: float) -> Iterator[None]:
        if getattr(_LOCK_STATE, "keys", ()):
            raise LockOrderError(
                "recovery registry must be acquired before participants"
            )
        with path_transaction_lock(
            self.registry_target,
            suffix=".recovery.lock",
            timeout_seconds=timeout_seconds,
        ) as acquired:
            if acquired is None:
                raise TransactionBusyError("timed out acquiring recovery registry")
            yield

    def _active_path(self, transaction_id: str) -> str:
        if not _TRANSACTION_ID.fullmatch(transaction_id):
            raise ValueError("invalid transaction id")
        return os.path.join(self.active_root, "%s.json" % transaction_id)

    def _resolved_path(self, transaction_id: str) -> str:
        if not _TRANSACTION_ID.fullmatch(transaction_id):
            raise ValueError("invalid transaction id")
        return os.path.join(self.resolved_root, "%s.json" % transaction_id)

    def _journal_for_plan(self, plan: TransactionPlan) -> Dict[str, Any]:
        now = time.time()
        return {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "transaction_id": plan.transaction_id,
            "transaction_key": plan.transaction_key,
            "operation": plan.operation,
            "phase": JournalPhase.PREPARED.value,
            "recovery_action": "ROLLBACK",
            "rollback_failure_code": plan.rollback_failure_code,
            "commit_recovery_code": plan.commit_recovery_code,
            "completion_acknowledged": False,
            "pending_receipt": None,
            "created_at_epoch": now,
            "updated_at_epoch": now,
            "participants": [
                {
                    "path": item.canonical_path,
                    "kind": item.kind.value,
                    "lock_suffix": item.lock_suffix,
                    "pre_exists": item.before.exists,
                    "pre_image": copy.deepcopy(item.before.value),
                    "pre_hash": item.pre_hash,
                    "post_exists": item.after.exists,
                    "post_image": copy.deepcopy(item.after.value),
                    "post_hash": item.post_hash,
                }
                for item in plan.participants
            ],
        }

    def _write_journal(self, path: str, journal: Mapping[str, Any]) -> None:
        payload = dict(journal)
        payload["journal_checksum"] = _journal_checksum(payload)
        if len(_canonical_json_bytes(payload)) > MAX_JOURNAL_BYTES:
            raise TransactionJournalError(
                str(payload.get("transaction_id") or "unknown"),
                "transaction_journal_too_large",
            )
        if isinstance(journal, dict):
            journal["journal_checksum"] = payload["journal_checksum"]
        _durable_write_json(path, payload)

    def _load_journal(
        self, path: str
    ) -> Tuple[Dict[str, Any], Tuple[ParticipantPlan, ...]]:
        try:
            journal = _load_json_strict(path, max_bytes=MAX_JOURNAL_BYTES)
        except Exception as exc:
            transaction_id = os.path.basename(path).split(".", 1)[0]
            raise TransactionJournalError(
                transaction_id, "transaction_journal_corrupt"
            ) from exc
        if not isinstance(journal, dict):
            raise TransactionJournalError("unknown", "transaction_journal_corrupt")
        transaction_id = journal.get("transaction_id")
        if not isinstance(transaction_id, str) or not _TRANSACTION_ID.fullmatch(
            transaction_id
        ):
            raise TransactionJournalError("unknown", "transaction_journal_corrupt")
        if os.path.basename(path) != "%s.json" % transaction_id:
            raise TransactionJournalError(
                transaction_id, "transaction_journal_identity_mismatch"
            )
        try:
            checksum = journal.get("journal_checksum")
            if (
                not isinstance(checksum, str)
                or not _TRANSACTION_ID.fullmatch(checksum)
                or checksum != _journal_checksum(journal)
            ):
                raise ValueError("journal checksum mismatch")
            if journal.get("schema_version") != JOURNAL_SCHEMA_VERSION:
                raise ValueError("unsupported journal schema")
            JournalPhase(journal.get("phase"))
            _safe_code(journal.get("transaction_key"), "transaction key")
            _safe_code(journal.get("operation"), "operation")
            _safe_code(journal.get("rollback_failure_code"), "rollback failure code")
            _safe_code(journal.get("commit_recovery_code"), "commit recovery code")
            raw_participants = journal.get("participants")
            if not isinstance(raw_participants, list) or not raw_participants:
                raise ValueError("journal has no participants")
            if len(raw_participants) > MAX_PARTICIPANTS:
                raise ValueError("journal has too many participants")
            participants: List[ParticipantPlan] = []
            for raw in raw_participants:
                if not isinstance(raw, dict):
                    raise ValueError("invalid participant")
                kind = ParticipantKind(raw.get("kind"))
                if raw.get("lock_suffix") != _LOCK_SUFFIX[kind]:
                    raise ValueError("participant lock identity mismatch")
                before = JsonSnapshot(raw.get("pre_exists"), raw.get("pre_image"))
                after = JsonSnapshot(raw.get("post_exists"), raw.get("post_image"))
                if (
                    raw.get("pre_hash") != before.digest
                    or raw.get("post_hash") != after.digest
                ):
                    raise ValueError("participant image hash mismatch")
                canonical = self._canonical_inside_workspace(raw.get("path"))
                if canonical != raw.get("path"):
                    raise ValueError("participant path is not canonical")
                participants.append(ParticipantPlan(canonical, kind, before, after))
            ordered = self._ordered_participants(tuple(participants))
            if tuple(participants) != ordered:
                raise ValueError("participants are not in canonical order")
            if type(journal.get("completion_acknowledged")) is not bool:
                raise ValueError("invalid completion acknowledgement")
            pending_receipt = journal.get("pending_receipt")
            if pending_receipt is not None:
                _safe_code(pending_receipt, "pending receipt")
            if journal.get("recovery_action") not in {"ROLLBACK", "COMMIT"}:
                raise ValueError("invalid recovery action")
            identity_material = {
                "schema_version": JOURNAL_SCHEMA_VERSION,
                "transaction_key": journal["transaction_key"],
                "operation": journal["operation"],
                "participants": [
                    {
                        "kind": item.kind.value,
                        "path": item.canonical_path,
                        "pre_hash": item.pre_hash,
                        "post_hash": item.post_hash,
                    }
                    for item in ordered
                ],
            }
            expected_id = hashlib.sha256(
                _canonical_json_bytes(identity_material)
            ).hexdigest()
            if expected_id != transaction_id:
                raise ValueError("transaction identity mismatch")
        except TransactionJournalError:
            raise
        except Exception as exc:
            raise TransactionJournalError(
                transaction_id, "transaction_journal_corrupt"
            ) from exc
        return journal, ordered

    def _active_journal_paths(self) -> Tuple[str, ...]:
        if not os.path.isdir(self.active_root):
            return ()
        return tuple(
            os.path.join(self.active_root, name)
            for name in sorted(os.listdir(self.active_root))
            if name.endswith(".json")
        )

    def _assert_no_unresolved_overlap(
        self, participants: Sequence[ParticipantPlan]
    ) -> None:
        wanted = {item.canonical_path for item in participants}
        for path in self._active_journal_paths():
            _journal, active = self._load_journal(path)
            if wanted.intersection(item.canonical_path for item in active):
                raise TransactionBlockedError(
                    "participant has an unresolved transaction"
                )

    def _current_digest(self, participant: ParticipantPlan) -> str:
        return self.read_snapshot(participant.canonical_path).digest

    def _verify_preconditions(self, participants: Sequence[ParticipantPlan]) -> None:
        for participant in participants:
            if self._current_digest(participant) != participant.pre_hash:
                raise TransactionStalePlanError("prepared participant changed")

    def _apply_snapshot(self, path: str, snapshot: JsonSnapshot) -> None:
        if snapshot.exists:
            _durable_write_json(path, snapshot.value)
        else:
            _durable_remove(path)

    def _boundary(
        self, name: str, journal: Mapping[str, Any], index: Optional[int] = None
    ) -> None:
        """No-op crash seam used by the local deterministic fault battery."""

    def _move_resolved(self, journal: Dict[str, Any], active_path: str) -> str:
        destination = self._resolved_path(journal["transaction_id"])
        if os.path.exists(destination):
            raise TransactionJournalError(
                journal["transaction_id"], "transaction_journal_duplicate"
            )
        _durable_move(active_path, destination)
        return destination

    def _resolved_replay(self, plan: TransactionPlan) -> Optional[TransactionResult]:
        path = self._resolved_path(plan.transaction_id)
        if not os.path.isfile(path):
            return None
        if os.path.exists(self._active_path(plan.transaction_id)):
            raise TransactionJournalError(
                plan.transaction_id, "transaction_journal_duplicate"
            )
        journal, participants = self._load_journal(path)
        if participants != plan.participants:
            raise TransactionJournalError(
                plan.transaction_id, "transaction_journal_identity_mismatch"
            )
        phase = JournalPhase(journal["phase"])
        if phase is JournalPhase.COMMITTED:
            return TransactionResult(plan.transaction_id, phase, replayed=True)
        if phase is JournalPhase.ABORTED:
            raise TransactionAbortedError(
                plan.transaction_id, journal["rollback_failure_code"]
            )
        raise TransactionJournalError(
            plan.transaction_id, "transaction_journal_invalid_resolved_state"
        )

    def execute(
        self,
        plan: TransactionPlan,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> TransactionResult:
        """Commit one prepared plan, or leave a deterministic recovery record."""
        if not isinstance(plan, TransactionPlan):
            raise TypeError("plan must be a TransactionPlan")
        self._validate_plan(plan)
        replay = self._resolved_replay(plan)
        if replay is not None:
            return replay
        if timeout_seconds is None:
            timeout_seconds = self.default_timeout_seconds
        timeout_seconds = max(0.0, float(timeout_seconds))
        started = time.monotonic()
        participant_context = None
        participant_entered = False
        journal: Optional[Dict[str, Any]] = None
        active_path = self._active_path(plan.transaction_id)
        phase: Optional[JournalPhase] = None
        try:
            with self._registry_lease(timeout_seconds):
                replay = self._resolved_replay(plan)
                if replay is not None:
                    return replay
                self._assert_no_unresolved_overlap(plan.participants)
                remaining = max(0.0, timeout_seconds - (time.monotonic() - started))
                participant_context = self.ordered_leases(
                    plan.participants, timeout_seconds=remaining
                )
                participant_context.__enter__()
                participant_entered = True
                try:
                    self._verify_preconditions(plan.participants)
                    journal = self._journal_for_plan(plan)
                    try:
                        self._write_journal(active_path, journal)
                    except Exception:
                        # A replace can become visible before a later
                        # directory-sync failure is reported.  If the exact
                        # durable PREPARED record exists, keep its recovery
                        # authority instead of claiming preparation never
                        # happened.
                        if os.path.isfile(active_path):
                            loaded, loaded_participants = self._load_journal(
                                active_path
                            )
                            if loaded_participants != plan.participants:
                                raise TransactionJournalError(
                                    plan.transaction_id,
                                    "transaction_journal_identity_mismatch",
                                )
                            journal = loaded
                            phase = JournalPhase(loaded["phase"])
                        raise
                    phase = JournalPhase.PREPARED
                    self._boundary("after_prepared", journal)
                except BaseException:
                    participant_context.__exit__(*__import__("sys").exc_info())
                    participant_context = None
                    participant_entered = False
                    raise

            assert journal is not None
            for index, participant in enumerate(plan.participants):
                self._apply_snapshot(participant.canonical_path, participant.after)
                self._boundary("after_participant_write", journal, index)
            journal["phase"] = JournalPhase.COMMITTED.value
            journal["recovery_action"] = "COMMIT"
            journal["updated_at_epoch"] = time.time()
            self._write_journal(active_path, journal)
            phase = JournalPhase.COMMITTED
            self._boundary("after_committed", journal)
            self._move_resolved(journal, active_path)
            self._boundary("after_resolved", journal)
            return TransactionResult(plan.transaction_id, JournalPhase.COMMITTED)
        except (
            TransactionBusyError,
            TransactionStalePlanError,
            TransactionBlockedError,
            TransactionJournalError,
        ):
            raise
        except BaseException as exc:
            if not isinstance(exc, Exception):
                raise
            if journal is None or phase is None:
                raise TransactionError("transaction failed before preparation") from exc
            if phase is JournalPhase.PREPARED:
                try:
                    recovered = self._recover_loaded_locked(
                        journal,
                        plan.participants,
                        active_path,
                        recovered_after_crash=False,
                    )
                except BaseException as recovery_exc:
                    if not isinstance(recovery_exc, Exception):
                        raise
                    raise TransactionRecoveryRequiredError(
                        plan.transaction_id, "transaction_recovery_required"
                    ) from recovery_exc
                if recovered.phase is JournalPhase.ABORTED:
                    raise TransactionAbortedError(
                        plan.transaction_id, plan.rollback_failure_code
                    ) from exc
                raise TransactionRecoveryRequiredError(
                    plan.transaction_id,
                    recovered.failure_code or "transaction_recovery_required",
                ) from exc
            raise TransactionRecoveryRequiredError(
                plan.transaction_id, plan.commit_recovery_code
            ) from exc
        finally:
            if participant_context is not None and participant_entered:
                participant_context.__exit__(None, None, None)

    def _recover_loaded_locked(
        self,
        journal: Dict[str, Any],
        participants: Sequence[ParticipantPlan],
        active_path: str,
        *,
        recovered_after_crash: bool,
    ) -> RecoveryResult:
        transaction_id = journal["transaction_id"]
        phase = JournalPhase(journal["phase"])
        action = journal.get("recovery_action")
        if phase is JournalPhase.PREPARED:
            action = "ROLLBACK"
        elif phase is JournalPhase.COMMITTED:
            action = "COMMIT"
        elif phase is JournalPhase.RECOVERY_REQUIRED and action not in {
            "ROLLBACK",
            "COMMIT",
        }:
            action = "ROLLBACK"
        elif phase is JournalPhase.ABORTED:
            self._move_resolved(journal, active_path)
            return RecoveryResult(transaction_id, JournalPhase.ABORTED)

        target_is_pre = action == "ROLLBACK"
        for participant in participants:
            current = self._current_digest(participant)
            if current not in {participant.pre_hash, participant.post_hash}:
                journal["phase"] = JournalPhase.RECOVERY_REQUIRED.value
                journal["recovery_action"] = action
                journal["pending_receipt"] = "transaction_state_diverged"
                journal["updated_at_epoch"] = time.time()
                self._write_journal(active_path, journal)
                return RecoveryResult(
                    transaction_id,
                    JournalPhase.RECOVERY_REQUIRED,
                    "transaction_state_diverged",
                )

        target_phase = JournalPhase.ABORTED if target_is_pre else JournalPhase.COMMITTED
        for index, participant in enumerate(participants):
            target = participant.before if target_is_pre else participant.after
            if self._current_digest(participant) != target.digest:
                self._apply_snapshot(participant.canonical_path, target)
            self._boundary("recovery_after_participant", journal, index)

        journal["phase"] = target_phase.value
        journal["recovery_action"] = action
        if recovered_after_crash:
            journal["pending_receipt"] = (
                journal["rollback_failure_code"]
                if target_is_pre
                else journal["commit_recovery_code"]
            )
        journal["updated_at_epoch"] = time.time()
        self._write_journal(active_path, journal)
        self._boundary("recovery_after_phase", journal)
        self._move_resolved(journal, active_path)
        return RecoveryResult(
            transaction_id,
            target_phase,
            journal.get("pending_receipt"),
        )

    def recover_all(
        self, *, timeout_seconds: Optional[float] = None
    ) -> Tuple[RecoveryResult, ...]:
        """Drain active journals in deterministic order before new mutations."""
        if timeout_seconds is None:
            timeout_seconds = self.default_timeout_seconds
        timeout_seconds = max(0.0, float(timeout_seconds))
        started = time.monotonic()
        results: List[RecoveryResult] = []
        with self._registry_lease(timeout_seconds):
            for path in self._active_journal_paths():
                try:
                    journal, participants = self._load_journal(path)
                except TransactionJournalError as exc:
                    results.append(
                        RecoveryResult(
                            exc.transaction_id,
                            JournalPhase.RECOVERY_REQUIRED,
                            exc.failure_code,
                            blocked_all=True,
                        )
                    )
                    continue
                if os.path.exists(self._resolved_path(journal["transaction_id"])):
                    results.append(
                        RecoveryResult(
                            journal["transaction_id"],
                            JournalPhase.RECOVERY_REQUIRED,
                            "transaction_journal_duplicate",
                        )
                    )
                    continue
                remaining = max(0.0, timeout_seconds - (time.monotonic() - started))
                try:
                    with self.ordered_leases(participants, timeout_seconds=remaining):
                        # The worker that created PREPARED releases the
                        # registry lease while retaining participant leases so
                        # disjoint transactions can proceed.  It may commit
                        # and move this journal while recovery waits.  Reload
                        # only after participant ownership proves the phase is
                        # no longer changing.
                        if not os.path.exists(path):
                            resolved_path = self._resolved_path(
                                journal["transaction_id"]
                            )
                            if os.path.isfile(resolved_path):
                                resolved, resolved_participants = self._load_journal(
                                    resolved_path
                                )
                                if resolved_participants != participants:
                                    raise TransactionJournalError(
                                        journal["transaction_id"],
                                        "transaction_journal_identity_mismatch",
                                    )
                                results.append(
                                    RecoveryResult(
                                        journal["transaction_id"],
                                        JournalPhase(resolved["phase"]),
                                    )
                                )
                            else:
                                results.append(
                                    RecoveryResult(
                                        journal["transaction_id"],
                                        JournalPhase.RECOVERY_REQUIRED,
                                        "transaction_journal_missing",
                                    )
                                )
                            continue
                        current_journal, current_participants = self._load_journal(path)
                        if current_participants != participants:
                            raise TransactionJournalError(
                                journal["transaction_id"],
                                "transaction_journal_identity_mismatch",
                            )
                        if os.path.exists(
                            self._resolved_path(current_journal["transaction_id"])
                        ):
                            results.append(
                                RecoveryResult(
                                    current_journal["transaction_id"],
                                    JournalPhase.RECOVERY_REQUIRED,
                                    "transaction_journal_duplicate",
                                )
                            )
                            continue
                        results.append(
                            self._recover_loaded_locked(
                                current_journal,
                                current_participants,
                                path,
                                recovered_after_crash=True,
                            )
                        )
                except TransactionBusyError:
                    results.append(
                        RecoveryResult(
                            journal["transaction_id"],
                            JournalPhase.RECOVERY_REQUIRED,
                            "transaction_recovery_busy",
                        )
                    )
                except TransactionJournalError as exc:
                    results.append(
                        RecoveryResult(
                            exc.transaction_id,
                            JournalPhase.RECOVERY_REQUIRED,
                            exc.failure_code,
                        )
                    )
        return tuple(results)

    def has_unresolved(self) -> bool:
        return bool(self._active_journal_paths())

    def assert_no_unresolved_for(self, paths: Iterable[str]) -> None:
        wanted = {self._canonical_inside_workspace(path) for path in paths}
        with self._registry_lease(self.default_timeout_seconds):
            for journal_path in self._active_journal_paths():
                try:
                    _journal, participants = self._load_journal(journal_path)
                except TransactionJournalError as exc:
                    raise TransactionBlockedError(exc.failure_code) from exc
                if wanted.intersection(item.canonical_path for item in participants):
                    raise TransactionBlockedError(
                        "participant has an unresolved transaction"
                    )

    def pending_receipts(self) -> Tuple[PendingReceipt, ...]:
        receipts: List[PendingReceipt] = []
        if not os.path.isdir(self.resolved_root):
            return ()
        with self._registry_lease(self.default_timeout_seconds):
            for name in sorted(os.listdir(self.resolved_root)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(self.resolved_root, name)
                journal, _participants = self._load_journal(path)
                code = journal.get("pending_receipt")
                if code and not journal.get("completion_acknowledged"):
                    receipts.append(
                        PendingReceipt(
                            journal["transaction_id"], _safe_code(code, "receipt")
                        )
                    )
        return tuple(receipts)

    def acknowledge_receipt(self, transaction_id: str) -> bool:
        path = self._resolved_path(transaction_id)
        with self._registry_lease(self.default_timeout_seconds):
            if not os.path.isfile(path):
                return False
            journal, _participants = self._load_journal(path)
            if journal.get("completion_acknowledged"):
                return False
            journal["completion_acknowledged"] = True
            journal["pending_receipt"] = None
            journal["updated_at_epoch"] = time.time()
            self._write_journal(path, journal)
            return True

    def prune_resolved(self, max_records: int = 256) -> int:
        """Bound old diagnostics without deleting an undelivered receipt."""
        if type(max_records) is not int or max_records < 1:
            raise ValueError("resolved journal retention must be positive")
        if not os.path.isdir(self.resolved_root):
            return 0
        removed = 0
        with self._registry_lease(self.default_timeout_seconds):
            records: List[Tuple[float, str, Dict[str, Any]]] = []
            for name in sorted(os.listdir(self.resolved_root)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(self.resolved_root, name)
                try:
                    journal, _participants = self._load_journal(path)
                except TransactionJournalError:
                    continue
                updated = journal.get("updated_at_epoch")
                if not isinstance(updated, (int, float)) or isinstance(updated, bool):
                    updated = 0.0
                records.append((float(updated), path, journal))
            records.sort(key=lambda item: (item[0], item[1]), reverse=True)
            retained = 0
            for _updated, path, journal in records:
                pending = bool(
                    journal.get("pending_receipt")
                    and not journal.get("completion_acknowledged")
                )
                if pending:
                    continue
                if retained < max_records:
                    retained += 1
                    continue
                _durable_remove(path)
                removed += 1
        return removed
