"""Transactional persistence helpers for bestiary-style JSON stores.

The normal ``safe_write_json`` helper makes an individual write atomic, but a
read/modify/write sequence can still lose another worker's update.  This module
holds one path-scoped thread lock and the existing inter-process file lock for
the complete transaction.
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from utils.file_operations import atomic_writer, safe_write_json


MONSTER_COMPENDIUM_PATH = "data/bestiary/monster_compendium.json"
NPC_COMPENDIUM_PATH = "data/bestiary/npc_compendium.json"


class CompendiumStoreError(RuntimeError):
    """Raised when a compendium transaction cannot be completed safely."""


@dataclass(frozen=True)
class MergeResult:
    """Outcome of one transactional entry merge."""

    added: Tuple[str, ...]
    updated: Tuple[str, ...]
    skipped: Tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated)


_locks_guard = threading.Lock()
_path_locks: Dict[str, threading.RLock] = {}


def _path_lock(filepath: str) -> threading.RLock:
    canonical = os.path.abspath(os.path.normpath(str(filepath)))
    with _locks_guard:
        return _path_locks.setdefault(canonical, threading.RLock())


def _load_document_locked(filepath: str, default_document: Mapping) -> dict:
    if not os.path.exists(filepath):
        return copy.deepcopy(dict(default_document))

    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompendiumStoreError(
            f"Cannot safely read JSON store {filepath}: {exc}"
        ) from exc

    if not isinstance(document, dict):
        raise CompendiumStoreError(
            f"JSON store {filepath} must contain a top-level object"
        )
    return document


def _validate_entry(entry_id: str, entry: Mapping) -> dict:
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise ValueError("Compendium entry IDs must be non-empty strings")
    if not isinstance(entry, Mapping):
        raise ValueError(f"Compendium entry {entry_id!r} must be an object")

    clean_entry = copy.deepcopy(dict(entry))
    for field in ("name", "description"):
        value = clean_entry.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Compendium entry {entry_id!r} has no usable {field}"
            )
        clean_entry[field] = value.strip()
    return clean_entry


def _merge_clean_entries(
    document: dict,
    clean_entries: Mapping[str, Mapping],
    *,
    collection_key: Optional[str],
    overwrite: bool,
    total_field: Optional[str],
) -> MergeResult:
    if collection_key is None:
        collection = document
    else:
        collection = document.setdefault(collection_key, {})
        if not isinstance(collection, dict):
            raise CompendiumStoreError(
                f"JSON field {collection_key!r} must be an object"
            )

    added = []
    updated = []
    skipped = []
    for entry_id, entry in clean_entries.items():
        if entry_id not in collection:
            collection[entry_id] = copy.deepcopy(dict(entry))
            added.append(entry_id)
        elif overwrite and collection[entry_id] != entry:
            collection[entry_id] = copy.deepcopy(dict(entry))
            updated.append(entry_id)
        else:
            skipped.append(entry_id)

    result = MergeResult(tuple(added), tuple(updated), tuple(skipped))
    if result.changed:
        if total_field is not None:
            document[total_field] = len(collection)
        if collection_key is not None:
            document["last_updated"] = datetime.now().isoformat()
    return result


def _transactional_merge(
    filepath: str,
    entries: Mapping[str, Mapping],
    *,
    collection_key: Optional[str],
    overwrite: bool,
    total_field: Optional[str],
    default_document: Mapping,
) -> MergeResult:
    if not isinstance(entries, Mapping):
        raise ValueError("Entries must be a mapping")
    clean_entries = {
        entry_id: _validate_entry(entry_id, entry)
        for entry_id, entry in entries.items()
    }

    filepath = os.path.abspath(os.path.normpath(str(filepath)))
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with _path_lock(filepath):
        lock_acquired = False
        try:
            atomic_writer.acquire_lock(filepath)
            lock_acquired = True
            document = _load_document_locked(filepath, default_document)

            result = _merge_clean_entries(
                document,
                clean_entries,
                collection_key=collection_key,
                overwrite=overwrite,
                total_field=total_field,
            )
            if not result.changed:
                return result

            if not safe_write_json(
                filepath,
                document,
                create_backup=True,
                acquire_lock=False,
            ):
                raise CompendiumStoreError(f"Failed to write JSON store {filepath}")
            return result
        finally:
            if lock_acquired:
                atomic_writer.release_lock(filepath)


def merge_compendium_entries(
    filepath: str,
    collection_key: str,
    entries: Mapping[str, Mapping],
    *,
    overwrite: bool = False,
) -> MergeResult:
    """Merge entries while holding the complete read/modify/write transaction."""
    total_fields = {"monsters": "total_monsters", "npcs": "total_npcs"}
    if collection_key not in total_fields:
        raise ValueError(f"Unsupported compendium collection: {collection_key}")
    return _transactional_merge(
        filepath,
        entries,
        collection_key=collection_key,
        overwrite=overwrite,
        total_field=total_fields[collection_key],
        default_document={
            "version": "1.0.0",
            "created": datetime.now().strftime("%Y-%m-%d"),
            total_fields[collection_key]: 0,
            collection_key: {},
        },
    )


def merge_npc_description_pair(
    compendium_path: str,
    legacy_path: str,
    compendium_entries: Mapping[str, Mapping],
    legacy_entries: Mapping[str, Mapping],
) -> Tuple[MergeResult, MergeResult]:
    """Serialize the primary and compatibility-cache updates as one unit.

    Both path locks and both inter-process locks remain held until the two
    atomic writes finish. If the second write fails, the first document is
    restored while those locks are still held.
    """
    clean_compendium = {
        entry_id: _validate_entry(entry_id, entry)
        for entry_id, entry in compendium_entries.items()
    }
    clean_legacy = {
        entry_id: _validate_entry(entry_id, entry)
        for entry_id, entry in legacy_entries.items()
    }
    if set(clean_compendium) != set(clean_legacy):
        raise ValueError("Primary and legacy NPC entry IDs must match")

    canonical_compendium = os.path.abspath(os.path.normpath(str(compendium_path)))
    canonical_legacy = os.path.abspath(os.path.normpath(str(legacy_path)))
    if canonical_compendium == canonical_legacy:
        raise ValueError("Primary and legacy NPC stores must use different paths")
    paths = sorted((canonical_compendium, canonical_legacy))
    for filepath in paths:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    acquired_file_locks = []
    originals = {}
    existed = {filepath: os.path.exists(filepath) for filepath in paths}
    written = []
    with ExitStack() as stack:
        for filepath in paths:
            stack.enter_context(_path_lock(filepath))
        try:
            for filepath in paths:
                atomic_writer.acquire_lock(filepath)
                acquired_file_locks.append(filepath)

            originals[canonical_compendium] = _load_document_locked(
                canonical_compendium,
                {
                    "version": "1.0.0",
                    "created": datetime.now().strftime("%Y-%m-%d"),
                    "total_npcs": 0,
                    "npcs": {},
                },
            )
            originals[canonical_legacy] = _load_document_locked(
                canonical_legacy, {}
            )
            compendium_document = copy.deepcopy(originals[canonical_compendium])
            legacy_document = copy.deepcopy(originals[canonical_legacy])
            compendium_result = _merge_clean_entries(
                compendium_document,
                clean_compendium,
                collection_key="npcs",
                overwrite=True,
                total_field="total_npcs",
            )
            legacy_result = _merge_clean_entries(
                legacy_document,
                clean_legacy,
                collection_key=None,
                overwrite=True,
                total_field=None,
            )

            documents = {
                canonical_compendium: (compendium_document, compendium_result),
                canonical_legacy: (legacy_document, legacy_result),
            }
            for filepath in paths:
                document, result = documents[filepath]
                if not result.changed:
                    continue
                if not safe_write_json(
                    filepath,
                    document,
                    create_backup=True,
                    acquire_lock=False,
                ):
                    raise CompendiumStoreError(
                        f"Failed to write paired JSON store {filepath}"
                    )
                written.append(filepath)
            return compendium_result, legacy_result
        except Exception as exc:
            rollback_errors = []
            for filepath in reversed(written):
                if existed[filepath]:
                    restored = safe_write_json(
                        filepath,
                        originals[filepath],
                        create_backup=False,
                        acquire_lock=False,
                    )
                    if not restored:
                        rollback_errors.append(filepath)
                else:
                    try:
                        if os.path.exists(filepath):
                            os.unlink(filepath)
                    except OSError:
                        rollback_errors.append(filepath)
            if rollback_errors:
                raise CompendiumStoreError(
                    "Paired NPC store update failed and rollback failed for: "
                    + ", ".join(rollback_errors)
                ) from exc
            if isinstance(exc, CompendiumStoreError):
                raise
            raise CompendiumStoreError(
                f"Paired NPC store update failed: {exc}"
            ) from exc
        finally:
            for filepath in reversed(acquired_file_locks):
                atomic_writer.release_lock(filepath)


def compendium_entry_exists(filepath: str, collection_key: str, entry_id: str) -> bool:
    """Read an entry under the same lock used by write transactions."""
    filepath = os.path.abspath(os.path.normpath(str(filepath)))
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with _path_lock(filepath):
        lock_acquired = False
        try:
            atomic_writer.acquire_lock(filepath)
            lock_acquired = True
            document = _load_document_locked(filepath, {collection_key: {}})
            collection = document.get(collection_key, {})
            if not isinstance(collection, dict):
                raise CompendiumStoreError(
                    f"JSON store {filepath} field {collection_key!r} must be an object"
                )
            return entry_id in collection
        finally:
            if lock_acquired:
                atomic_writer.release_lock(filepath)


def validate_generated_prose(text: str, *, minimum_words: int = 20) -> str:
    """Return usable prose or reject empty/structured/placeholder-like output."""
    if not isinstance(text, str):
        raise ValueError("Generated description must be text")
    prose = text.strip()
    if not prose:
        raise ValueError("Generated description is empty")
    if prose.startswith("```") or prose.endswith("```"):
        raise ValueError("Generated description returned a code block, not prose")
    try:
        structured_value = json.loads(prose)
    except (TypeError, json.JSONDecodeError):
        structured_value = None
    if isinstance(structured_value, (dict, list)):
        raise ValueError("Generated description returned structured data, not prose")
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", prose)
    if len(words) < minimum_words:
        raise ValueError(
            f"Generated description is too short ({len(words)} words; "
            f"minimum {minimum_words})"
        )
    return prose
