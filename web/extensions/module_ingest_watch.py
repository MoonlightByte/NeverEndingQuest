# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Module Ingest Watch Worker
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Watches modules/ingest for new markdown/text files and auto-ingests them
into NEQ modules. Processed source files are moved into modules/ingest/archive.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 2. Third-party imports

# 3. Internal module imports (grouped by layer)
from utils.enhanced_logger import debug, error, info, warning
from utils.file_operations import safe_write_json


# Worker state (module-level, thread-safe)
_worker_thread: Optional[threading.Thread] = None
_stop_event: threading.Event = threading.Event()
_state_lock: threading.Lock = threading.Lock()

# Stability cache: file path -> (size, mtime_ns)
_file_stability_cache: Dict[str, Tuple[int, int]] = {}

_worker_stats: Dict[str, Any] = {
    "start_time": None,
    "last_scan_time": None,
    "files_seen": 0,
    "files_ingested": 0,
    "files_quarantined": 0,
    "files_failed": 0,
    "last_file": None,
}


def _normalize_extensions(allowed_extensions: Optional[List[str]]) -> List[str]:
    """Normalize allowed extension list to lowercase dot-prefixed format."""
    if not allowed_extensions:
        return [".md", ".markdown", ".txt"]

    normalized: List[str] = []
    for ext in allowed_extensions:
        clean = ext.strip().lower()
        if not clean:
            continue
        if not clean.startswith("."):
            clean = f".{clean}"
        normalized.append(clean)

    return normalized or [".md", ".markdown", ".txt"]


def _list_candidate_files(watch_dir: Path, archive_dir: Path, allowed_extensions: List[str]) -> List[Path]:
    """List candidate source files in watch dir, excluding archive subtree."""
    candidates: List[Path] = []

    if not watch_dir.exists():
        return candidates

    for entry in watch_dir.iterdir():
        if not entry.is_file():
            continue

        # Skip dotfiles and temporary editor swap files.
        if entry.name.startswith(".") or entry.name.endswith(".tmp"):
            continue

        # Defensive: skip files that are somehow in archive path.
        try:
            if archive_dir in entry.parents:
                continue
        except Exception:
            pass

        if entry.suffix.lower() not in allowed_extensions:
            continue

        candidates.append(entry)

    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates


def _is_file_stable(file_path: Path) -> bool:
    """Require one unchanged scan cycle before ingestion."""
    try:
        stat_result = file_path.stat()
        signature = (stat_result.st_size, stat_result.st_mtime_ns)
    except Exception:
        return False

    cache_key = str(file_path)
    previous = _file_stability_cache.get(cache_key)
    _file_stability_cache[cache_key] = signature

    return previous is not None and previous == signature


def _clear_deleted_from_stability_cache(candidate_paths: List[Path]) -> None:
    """Remove stale entries from stability cache."""
    candidate_set = {str(path) for path in candidate_paths}
    stale_keys = [key for key in _file_stability_cache.keys() if key not in candidate_set]
    for key in stale_keys:
        _file_stability_cache.pop(key, None)


def _archive_processed_file(source_path: Path, archive_dir: Path, status: str) -> Path:
    """Move processed source file into archive with timestamped name."""
    archive_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived_name = f"{timestamp}_{status}_{source_path.name}"
    archived_path = archive_dir / archived_name

    collision_index = 1
    while archived_path.exists():
        archived_name = f"{timestamp}_{status}_{collision_index}_{source_path.name}"
        archived_path = archive_dir / archived_name
        collision_index += 1

    shutil.move(str(source_path), str(archived_path))
    return archived_path


def _write_result_sidecar(archived_path: Path, result: Dict[str, Any]) -> None:
    """Write ingestion result sidecar next to archived source file."""
    sidecar_path = archived_path.with_suffix(f"{archived_path.suffix}.result.json")

    sidecar_payload = {
        "source": archived_path.name,
        "processed_at": datetime.now().isoformat(),
        "result": result,
    }
    safe_write_json(str(sidecar_path), sidecar_payload)


def _process_source_file(source_path: Path, strict_validation: bool) -> Dict[str, Any]:
    """Run importer against one source file and return structured result."""
    # TABLETOP MODE: Lazy import keeps web startup resilient if importer dependencies
    # are unavailable; failures are handled per-file and archived with error status.
    from core.importers.homebrewery_importer import import_homebrewery_adventure_to_module

    # TABLETOP MODE: Force deterministic ingest for watched markdown/text files.
    # The watch-folder path must never invoke AI builder; deterministic parse only.
    return import_homebrewery_adventure_to_module(
        source_path=str(source_path),
        strict=strict_validation,
        use_deterministic=True,
    )


def _watch_worker_loop(
    watch_dir: str,
    archive_dir: str,
    poll_interval_seconds: float,
    strict_validation: bool,
    allowed_extensions: Optional[List[str]],
) -> None:
    """Worker polling loop for ingest folder."""
    normalized_extensions = _normalize_extensions(allowed_extensions)
    watch_path = Path(watch_dir)
    archive_path = Path(archive_dir)

    watch_path.mkdir(parents=True, exist_ok=True)
    archive_path.mkdir(parents=True, exist_ok=True)

    info(
        f"MODULE_INGEST: Watch loop started dir={watch_path} archive={archive_path}",
        category="module_ingest",
    )

    while not _stop_event.is_set():
        try:
            candidates = _list_candidate_files(watch_path, archive_path, normalized_extensions)
            _clear_deleted_from_stability_cache(candidates)

            with _state_lock:
                _worker_stats["last_scan_time"] = datetime.now().isoformat()
                _worker_stats["files_seen"] += len(candidates)

            for source_file in candidates:
                if _stop_event.is_set():
                    break

                # Require one stable poll interval before ingestion.
                if not _is_file_stable(source_file):
                    debug(
                        f"MODULE_INGEST: Waiting for file stability source={source_file.name}",
                        category="module_ingest",
                    )
                    continue

                info(
                    f"MODULE_INGEST: Processing source={source_file.name}",
                    category="module_ingest",
                )

                try:
                    result = _process_source_file(source_file, strict_validation)
                except Exception as process_error:
                    error(
                        f"MODULE_INGEST: Processing exception source={source_file.name}",
                        exception=process_error,
                        category="module_ingest",
                    )
                    result = {
                        "status": "error",
                        "module_slug": None,
                        "artifacts": [],
                        "validation": {
                            "passed": False,
                            "errors": [str(process_error)],
                        },
                        "quarantine_reason": "worker_process_exception",
                    }

                status = result.get("status", "error")
                archived_path = _archive_processed_file(source_file, archive_path, status)
                _write_result_sidecar(archived_path, result)

                with _state_lock:
                    _worker_stats["last_file"] = source_file.name
                    if status == "success":
                        _worker_stats["files_ingested"] += 1
                    elif status == "quarantined":
                        _worker_stats["files_quarantined"] += 1
                    else:
                        _worker_stats["files_failed"] += 1

                info(
                    f"MODULE_INGEST: Archived source={archived_path.name} status={status}",
                    category="module_ingest",
                )

        except Exception as loop_error:
            error(
                "MODULE_INGEST: Watch loop exception",
                exception=loop_error,
                category="module_ingest",
            )

        _stop_event.wait(timeout=poll_interval_seconds)

    info("MODULE_INGEST: Watch loop stopped", category="module_ingest")


def start_module_ingest_watch_worker(
    watch_dir: str = "modules/ingest",
    archive_dir: str = "modules/ingest/archive",
    poll_interval_seconds: float = 5.0,
    strict_validation: bool = True,
    allowed_extensions: Optional[List[str]] = None,
) -> bool:
    """Start module ingest watch worker.

    Idempotent startup, safe to call multiple times.
    """
    global _worker_thread

    with _state_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            debug("MODULE_INGEST: Worker already running", category="module_ingest")
            return True

        _stop_event.clear()
        _worker_stats["start_time"] = datetime.now().isoformat()

        _worker_thread = threading.Thread(
            target=_watch_worker_loop,
            args=(
                watch_dir,
                archive_dir,
                poll_interval_seconds,
                strict_validation,
                allowed_extensions,
            ),
            name="ModuleIngestWatchWorker",
            daemon=True,
        )
        _worker_thread.start()

    info(
        f"MODULE_INGEST: Worker started poll={poll_interval_seconds}s strict={strict_validation}",
        category="module_ingest",
    )
    return True


def stop_module_ingest_watch_worker(timeout: float = 5.0) -> bool:
    """Stop module ingest watch worker gracefully."""
    global _worker_thread

    with _state_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            return True
        _stop_event.set()
        worker_ref = _worker_thread

    worker_ref.join(timeout=timeout)

    with _state_lock:
        still_alive = _worker_thread.is_alive() if _worker_thread else False
        if not still_alive:
            _worker_thread = None
            info("MODULE_INGEST: Worker stopped", category="module_ingest")
            return True

    warning(
        f"MODULE_INGEST: Worker stop timeout after {timeout}s",
        category="module_ingest",
    )
    return False


def get_module_ingest_watch_stats() -> Dict[str, Any]:
    """Get snapshot of ingest watcher runtime stats."""
    with _state_lock:
        return dict(_worker_stats)
