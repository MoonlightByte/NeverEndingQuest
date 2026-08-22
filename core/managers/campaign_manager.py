# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Campaign Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# CAMPAIGN_MANAGER.PY - LOCATION-BASED HUB-AND-SPOKE CAMPAIGN ORCHESTRATION
# ============================================================================
# 
# ARCHITECTURE ROLE: Campaign Layer - Location-Based Module Continuity
# 
# This module implements a revolutionary location-based hub-and-spoke campaign
# system where module boundaries are geographic rather than narrative. Players
# seamlessly transition between modules based on location, with automatic
# context preservation and summary generation.
# 
# CORE DESIGN PHILOSOPHY - LOCATION-BASED MODULES:
# - Each geographic area network = one module (Shadowmere_Valley, Crystal_Peaks, etc.)
# - Module context automatically loads based on current location ID
# - Cross-module travel triggers automatic summarization of previous module
# - Multiple visits to same module accumulate summaries for rich context
# - No player prompts needed - transitions are organic and AI-driven
# 
# HUB-AND-SPOKE MODEL:
# - Central hub locations (Thornwick Village) accessible from multiple modules
# - Players can return to any visited module through natural travel
# - Each module retains its state and continues to evolve with new visits
# - Adventure summaries accumulate, creating living world history
# 
# KEY RESPONSIBILITIES:
# - Detect cross-module transitions via location IDs
# - Auto-generate module summaries when leaving module areas
# - Accumulate and inject relevant module summaries as conversation context
# - Maintain module visit history and state continuity
# - Support unlimited module revisiting with full context preservation
# 
# LOCATION-TO-MODULE MAPPING EXAMPLE:
# - TV001, TV002, TV003 → Thornwick_Village module (hub)
# - SM001, SM002, SM003 → Shadowmere_Valley module  
# - CP001, CP002, CP003 → Crystal_Peaks module
# - Module detection via location ID prefixes or area mappings
# 
# SUMMARY ACCUMULATION STRATEGY:
# Visit 1: Shadowmere_Valley → [Chronicle of the Cursed Marshlands]
# Visit 2: Crystal_Peaks → [Tale of the Frozen Spires] 
# Visit 3: Return to Shadowmere_Valley → [Previous chronicles + new events]
# Visit 4: Back to Crystal_Peaks → [All accumulated chronicles + latest adventure]
# 
# ARCHITECTURAL INTEGRATION:
# - Enhanced transitionLocation detection for cross-module movement
# - Automatic conversation context injection with accumulated summaries
# - Seamless integration with existing ModulePathManager architecture
# - Maintains backward compatibility with single-module adventures
# 
# This system creates a living, interconnected world where every adventure
# builds upon previous experiences while maintaining the modular architecture.
# ============================================================================

import copy
import hashlib
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional, Tuple
from uuid import uuid4
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T038", "core/managers/campaign_manager.py", 3192)
register_callsite("T039", "core/managers/campaign_manager.py", 3245)
import config
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.file_operations import safe_write_json
from utils.module_path_manager import ModulePathManager
from utils.module_refresh_lock import module_refresh_lock
from utils.path_transaction_lock import path_transaction_lock
from utils.enhanced_logger import debug, info, warning, error, game_event, set_script_name

# Set script name for logging
set_script_name(__name__)


def _is_valid_campaign_export_data(exported_data: Any) -> bool:
    """Check the structural contract consumed by campaign-state importers."""
    if not isinstance(exported_data, dict):
        return False

    required_types = {
        "relationships": dict,
        "artifacts": dict,
        "hubs": dict,
        "worldState": dict,
        "unlockedModules": list,
    }
    if set(exported_data) != set(required_types):
        return False
    for field, expected_type in required_types.items():
        if field not in exported_data or not isinstance(
            exported_data[field], expected_type
        ):
            return False

    if not all(
        isinstance(key, str) and key.strip()
        for field in ("relationships", "artifacts", "hubs", "worldState")
        for key in exported_data[field]
    ):
        return False

    return all(
        isinstance(module_name, str) and module_name.strip()
        for module_name in exported_data["unlockedModules"]
    )


_MODULE_COMPLETION_FLIGHTS = {}
_MODULE_COMPLETION_FLIGHTS_GUARD = threading.Lock()
_CAMPAIGN_COMPLETION_TRANSACTION_VERSION = 1
_LIFECYCLE_EPOCH_UNSET = object()


class _ModuleCompletionCheckpointError(OSError):
    """A local durability failure that must not become an AI fallback."""


def _reset_module_completion_flights_after_fork() -> None:
    """Discard Futures/locks that cannot be completed in a forked child."""
    global _MODULE_COMPLETION_FLIGHTS, _MODULE_COMPLETION_FLIGHTS_GUARD
    _MODULE_COMPLETION_FLIGHTS = {}
    _MODULE_COMPLETION_FLIGHTS_GUARD = threading.Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_module_completion_flights_after_fork)


def _normalize_module_name(module_name: str) -> str:
    """Validate one module identity before interpolating it into a path."""
    if not isinstance(module_name, str) or not module_name.strip():
        raise ValueError("module_name must be a non-empty string")
    normalized = module_name.strip()
    if (
        normalized in {".", ".."}
        or "\0" in normalized
        or "/" in normalized
        or "\\" in normalized
        or ":" in normalized
    ):
        raise ValueError("module_name may not contain path separators")
    return normalized


def _campaign_completion_metadata_dir(campaign_file: str) -> str:
    canonical_campaign = os.path.abspath(os.path.normpath(campaign_file))
    return os.path.join(
        os.path.dirname(canonical_campaign),
        f".{os.path.basename(canonical_campaign)}.completion",
    )


def _campaign_lifecycle_epoch_path(campaign_file: str) -> str:
    canonical = os.path.abspath(os.path.normpath(campaign_file))
    return os.path.join(
        os.path.dirname(canonical),
        f".{os.path.basename(canonical)}.completion-epoch.json",
    )


def _load_campaign_lifecycle_epoch(campaign_file: str) -> Optional[str]:
    path = _campaign_lifecycle_epoch_path(campaign_file)
    payload = _load_json_dict(path)
    if payload is None:
        if os.path.exists(path):
            raise OSError(f"Unreadable campaign lifecycle epoch {path}")
        return None
    epoch = payload.get("epoch")
    if (
        payload.get("version") != _CAMPAIGN_COMPLETION_TRANSACTION_VERSION
        or not isinstance(epoch, str)
        or not epoch
    ):
        raise OSError(f"Invalid campaign lifecycle epoch {path}")
    return epoch


def _bump_campaign_lifecycle_epoch(campaign_file: str) -> str:
    epoch = uuid4().hex
    _durable_write_json(
        _campaign_lifecycle_epoch_path(campaign_file),
        {
            "version": _CAMPAIGN_COMPLETION_TRANSACTION_VERSION,
            "epoch": epoch,
            "updated_at": datetime.now().isoformat(),
        },
    )
    return epoch


def _assert_no_active_campaign_completion(campaign_file: str) -> None:
    metadata_dir = _campaign_completion_metadata_dir(campaign_file)
    pending = os.path.join(metadata_dir, "pending.json")
    if os.path.exists(pending):
        raise OSError("Campaign completion recovery is active; retry restore")
    if os.path.isdir(metadata_dir):
        active_work = [
            name
            for name in os.listdir(metadata_dir)
            if name.endswith(".work.json")
        ]
        if active_work:
            raise OSError("Campaign completion work is active; retry restore")
        intents_dir = os.path.join(metadata_dir, "intents")
        if os.path.isdir(intents_dir) and any(
            name.endswith(".json") for name in os.listdir(intents_dir)
        ):
            raise OSError(
                "Campaign transition completion is queued; retry restore"
            )


def _campaign_transaction_lock(campaign_file: str):
    """Serialize campaign read/merge/write transactions across workers."""
    # Keep the lifecycle lock outside the metadata directory. Restore/reset
    # intentionally replace that directory and must not invalidate a lock
    # another worker is currently holding.
    lock_target = os.path.abspath(os.path.normpath(campaign_file))
    return path_transaction_lock(
        lock_target,
        suffix=".completion.transaction.lock",
    )


def _party_module_transition_lock(party_tracker_file: str = "party_tracker.json"):
    """Serialize fresh-check + party module publication across workers."""
    return path_transaction_lock(
        party_tracker_file,
        suffix=".module-transition.lock",
    )


def _module_completion_key(
    campaign_file: str,
    module_name: str,
    completion_id: Optional[str] = None,
):
    return (
        os.path.abspath(os.path.normpath(campaign_file)),
        _normalize_module_name(module_name),
        _normalize_completion_id(completion_id) or "__legacy_module_flight__",
    )


def _module_completion_paths(
    campaign_file: str,
    summaries_dir: str,
    module_name: str,
) -> Dict[str, str]:
    """Return stable transaction paths for one campaign/module identity."""
    module_name = _normalize_module_name(module_name)
    canonical_campaign = os.path.abspath(os.path.normpath(campaign_file))
    canonical_summaries = os.path.abspath(os.path.normpath(summaries_dir))
    canonical_summary = os.path.abspath(
        os.path.normpath(
            os.path.join(
                canonical_summaries,
                f"{module_name}_summary_001.json",
            )
        )
    )
    try:
        if os.path.commonpath(
            (canonical_summary, canonical_summaries)
        ) != canonical_summaries:
            raise ValueError("module summary escapes summaries directory")
    except ValueError as exc:
        raise ValueError("Invalid module summary path") from exc
    identity = f"{canonical_campaign}\0{module_name}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    metadata_dir = _campaign_completion_metadata_dir(canonical_campaign)
    base = os.path.join(metadata_dir, digest)
    locks_dir = os.path.join(
        os.path.dirname(canonical_campaign),
        f".{os.path.basename(canonical_campaign)}.completion-locks",
    )
    return {
        # Coordination files must live outside replaceable metadata. A
        # restore/reset may atomically replace metadata while another process
        # is waiting, but it must never split the advisory-lock inode.
        "lock_target": os.path.join(locks_dir, digest),
        "work": f"{base}.work.json",
        "receipts_dir": f"{base}.receipts",
        "intents_dir": os.path.join(metadata_dir, "intents"),
        "summary": canonical_summary,
        "campaign_pending": os.path.join(metadata_dir, "pending.json"),
    }


def _normalize_completion_id(completion_id: Optional[str]) -> Optional[str]:
    if completion_id is None:
        return None
    if not isinstance(completion_id, str) or not completion_id.strip():
        raise ValueError("completion_id must be a non-empty string")
    return completion_id.strip()


def _completion_receipt_path(
    paths: Dict[str, str],
    completion_id: Optional[str],
) -> Optional[str]:
    normalized = _normalize_completion_id(completion_id)
    if normalized is None:
        return None
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return os.path.join(paths["receipts_dir"], f"{digest}.json")


def _completion_intent_path(
    paths: Dict[str, str],
    module_name: str,
    completion_id: str,
) -> str:
    module_name = _normalize_module_name(module_name)
    normalized = _normalize_completion_id(completion_id)
    if normalized is None:
        raise ValueError("completion intents require a completion_id")
    identity = f"{module_name}\0{normalized}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return os.path.join(paths["intents_dir"], f"{digest}.json")


_COMPLETION_INTENT_TEMP_PATTERN = re.compile(
    r"[0-9a-f]{64}\.json\.[0-9]+\.[0-9a-f]{32}\.tmp"
)


def _completion_intent_sequence_path(campaign_file: str) -> str:
    return os.path.join(
        _campaign_completion_metadata_dir(campaign_file),
        "intent-sequence.json",
    )


def _next_completion_intent_sequence_locked(campaign_file: str) -> int:
    """Allocate one durable total order while the campaign lock is held."""
    sequence_path = _completion_intent_sequence_path(campaign_file)
    existed = os.path.exists(sequence_path)
    record = _load_json_dict(sequence_path) if existed else None
    if existed and record is None:
        raise OSError("Unreadable module-completion intent sequence")
    if record is None:
        last_sequence = 0
    else:
        last_sequence = record.get("last_sequence")
        if (
            record.get("version")
            != _CAMPAIGN_COMPLETION_TRANSACTION_VERSION
            or not isinstance(last_sequence, int)
            or isinstance(last_sequence, bool)
            or last_sequence < 0
        ):
            raise OSError("Invalid module-completion intent sequence")
    next_sequence = last_sequence + 1
    _durable_write_json(
        sequence_path,
        {
            "version": _CAMPAIGN_COMPLETION_TRANSACTION_VERSION,
            "last_sequence": next_sequence,
        },
    )
    return next_sequence


def _load_completion_receipt(
    paths: Dict[str, str],
    module_name: str,
    completion_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    module_name = _normalize_module_name(module_name)
    completion_id = _normalize_completion_id(completion_id)
    receipt_path = _completion_receipt_path(paths, completion_id)
    if receipt_path is None:
        return None
    receipt = _load_json_dict(receipt_path)
    if receipt is None:
        if os.path.exists(receipt_path):
            raise OSError(f"Unreadable module-completion receipt {receipt_path}")
        return None
    transaction_id = receipt.get("transaction_id")
    summary_fingerprint = receipt.get("summary_fingerprint")
    result = receipt.get("result")
    if (
        receipt.get("version") != _CAMPAIGN_COMPLETION_TRANSACTION_VERSION
        or receipt.get("operation") != "completion"
        or receipt.get("module_name") != module_name
        or receipt.get("completion_id") != completion_id
        or not isinstance(transaction_id, str)
        or not transaction_id
        or not isinstance(summary_fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{64}", summary_fingerprint)
        or not isinstance(result, dict)
        or _json_fingerprint(result) != summary_fingerprint
    ):
        raise OSError(f"Invalid module-completion receipt {receipt_path}")
    return receipt


def _validate_receipt_committed_projection(
    paths: Dict[str, str],
    module_name: str,
    campaign_file: str,
    receipt: Dict[str, Any],
) -> None:
    """Tie a receipt to the living committed campaign without rejecting history."""
    module_name = _normalize_module_name(module_name)
    summary = _load_json_dict(paths["summary"])
    campaign = _load_json_dict(campaign_file)
    if (
        not isinstance(summary, dict)
        or not isinstance(campaign, dict)
        or summary.get("moduleName") != module_name
        or receipt["result"].get("moduleName") != module_name
        or summary.get("sequenceNumber") != 1
        or receipt["result"].get("sequenceNumber") != 1
        or not isinstance(campaign.get("completedModules"), list)
        or module_name not in campaign.get("completedModules", [])
    ):
        raise OSError("Completion receipt has no committed campaign projection")
    receipt_result = receipt["result"]
    receipt_visit = receipt_result.get("visitCount")
    current_visit = summary.get("visitCount")
    if (
        not isinstance(receipt_visit, int)
        or receipt_visit < 1
        or not isinstance(current_visit, int)
        or current_visit < receipt_visit
    ):
        raise OSError("Completion receipt visit is not committed")
    # Earlier receipts remain replayable after later legitimate visits replace
    # _summary_001. The receipt for the current visit must match byte-for-byte.
    if current_visit == receipt_visit and summary != receipt_result:
        repaired_same_visit = (
            bool(
                receipt_result.get("summary_failed")
                or receipt_result.get("export_failed")
            )
            and not summary.get("summary_failed")
            and not summary.get("export_failed")
            and summary.get("firstVisitDate")
            == receipt_result.get("firstVisitDate")
            and summary.get("lastVisitDate")
            == receipt_result.get("lastVisitDate")
            and summary.get("regeneratedFromFingerprint")
            == receipt.get("summary_fingerprint")
        )
        if not repaired_same_visit:
            raise OSError("Completion receipt conflicts with current summary")


def _durable_write_json(path: str, payload: Dict[str, Any]) -> None:
    """Write transaction metadata durably without a stale sentinel lock."""
    canonical = os.path.abspath(os.path.normpath(path))
    parent = os.path.dirname(canonical)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temp_path = f"{canonical}.{os.getpid()}.{uuid4().hex}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, canonical)
        if parent and hasattr(os, "O_DIRECTORY"):
            try:
                directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass


def _durable_remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    parent = os.path.dirname(os.path.abspath(path))
    if parent and hasattr(os, "O_DIRECTORY"):
        try:
            directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass


def _json_fingerprint(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_module_archive_path(
    archive_path: str,
    archives_dir: str,
    module_name: str,
) -> str:
    """Require an archive to be an exact file for this module/root."""
    module_name = _normalize_module_name(module_name)
    if not isinstance(archive_path, str) or not archive_path:
        raise OSError("Module completion has no archive path")
    canonical_archive = os.path.abspath(os.path.normpath(archive_path))
    canonical_directory = os.path.abspath(os.path.normpath(archives_dir))
    if os.path.dirname(canonical_archive) != canonical_directory:
        raise OSError("Module completion archive escapes archive directory")
    pattern = rf"{re.escape(module_name)}_conversation_[0-9]+\.json"
    if not re.fullmatch(pattern, os.path.basename(canonical_archive)):
        raise OSError("Module completion archive has invalid identity")
    return canonical_archive


def _validate_module_archive(
    archive_path: str,
    archives_dir: str,
    module_name: str,
    archive_fingerprint: str,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    canonical_archive = _validate_module_archive_path(
        archive_path,
        archives_dir,
        module_name,
    )
    if not isinstance(archive_fingerprint, str) or not re.fullmatch(
        r"[0-9a-f]{64}", archive_fingerprint
    ):
        raise OSError("Module completion archive has invalid fingerprint")
    archive = _load_json_dict(canonical_archive)
    if (
        not isinstance(archive, dict)
        or archive.get("moduleName") != _normalize_module_name(module_name)
        or not isinstance(archive.get("conversationHistory"), list)
        or _json_fingerprint(archive) != archive_fingerprint
        or (
            transaction_id is not None
            and archive.get("completionTransactionId") != transaction_id
        )
    ):
        raise OSError("Module completion archive is missing or changed")
    return archive


def _load_json_dict(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _completion_snapshot(
    paths: Dict[str, str],
    module_name: str,
):
    """Fingerprint persisted state plus in-flight transaction identities."""
    summary = _load_json_dict(paths["summary"])
    summary_fingerprint = _json_fingerprint(summary) if summary else None
    summary_visit_count = None
    if isinstance(summary, dict):
        candidate = summary.get("visitCount")
        if isinstance(candidate, int) and candidate >= 0:
            summary_visit_count = candidate
    pending = _load_json_dict(paths["campaign_pending"])
    pending_transaction = None
    if isinstance(pending, dict) and pending.get("module_name") == module_name:
        candidate = pending.get("transaction_id")
        if isinstance(candidate, str) and candidate:
            pending_transaction = candidate
    work = _load_json_dict(paths["work"])
    work_transaction = None
    work_status = None
    work_summary_fingerprint = None
    if isinstance(work, dict) and work.get("module_name") == module_name:
        candidate = work.get("transaction_id")
        if isinstance(candidate, str) and candidate:
            work_transaction = candidate
        candidate = work.get("status")
        if candidate in {"generating", "committed"}:
            work_status = candidate
        candidate = work.get("summary_fingerprint")
        if isinstance(candidate, str):
            work_summary_fingerprint = candidate
    return (
        summary_fingerprint,
        pending_transaction,
        work_transaction,
        work_status,
        work_summary_fingerprint,
        summary_visit_count,
    )


def _write_completion_target(path: str, payload: Dict[str, Any]) -> None:
    # Callers already hold the path/campaign OS lock.  A unique same-directory
    # temporary file avoids stale PID sentinels and PID-reuse/TOCTOU hazards.
    _durable_write_json(path, payload)


def _restore_completion_target(
    path: str,
    existed: bool,
    payload: Any,
) -> None:
    if existed:
        if not isinstance(payload, dict):
            raise OSError(f"Invalid rollback snapshot for {path}")
        if _load_json_dict(path) == payload:
            return
        _write_completion_target(path, payload)
    else:
        if not os.path.exists(path):
            return
        _durable_remove(path)


def _validate_completion_pending_record(
    pending: Dict[str, Any],
    campaign_file: str,
    summaries_dir: str,
    archives_dir: str,
) -> None:
    if pending.get("version") != _CAMPAIGN_COMPLETION_TRANSACTION_VERSION:
        raise OSError("Unsupported campaign-completion recovery marker version")
    if pending.get("status") not in {"staged", "rollback_required"}:
        raise OSError("Invalid campaign-completion recovery marker status")
    if pending.get("operation", "completion") not in {
        "completion",
        "regeneration",
    }:
        raise OSError("Invalid campaign-completion operation")
    transaction_id = pending.get("transaction_id")
    module_name = pending.get("module_name")
    if not isinstance(transaction_id, str) or not transaction_id:
        raise OSError("Campaign-completion marker has no transaction id")
    try:
        module_name = _normalize_module_name(module_name)
    except ValueError as exc:
        raise OSError("Campaign-completion marker has invalid module name") from exc

    expected_campaign = os.path.abspath(os.path.normpath(campaign_file))
    if pending.get("campaign_path") != expected_campaign:
        raise OSError("Campaign-completion marker targets another campaign")
    expected_paths = _module_completion_paths(
        expected_campaign,
        summaries_dir,
        module_name,
    )
    if pending.get("summary_path") != expected_paths["summary"]:
        raise OSError("Campaign-completion marker targets another summary")
    expected_archives = os.path.abspath(os.path.normpath(archives_dir))
    if pending.get("archives_dir") != expected_archives:
        raise OSError("Campaign-completion marker targets another archive root")

    work_path = pending.get("work_path")
    if work_path is not None and work_path != expected_paths["work"]:
        raise OSError("Campaign-completion marker has invalid work_path")

    completion_id = pending.get("completion_id")
    receipt_path = pending.get("receipt_path")
    expected_receipt = _completion_receipt_path(expected_paths, completion_id)
    if receipt_path != expected_receipt:
        raise OSError("Campaign-completion marker has invalid receipt_path")
    if expected_receipt is not None and pending.get("operation") != "completion":
        raise OSError("Only completions may publish completion receipts")

    archive_path = pending.get("archive_path")
    archive_fingerprint = pending.get("archive_fingerprint")
    if pending.get("operation") == "completion":
        canonical_archive = _validate_module_archive_path(
            archive_path,
            expected_archives,
            module_name,
        )
        if pending.get("status") == "rollback_required" and not os.path.exists(
            canonical_archive
        ):
            if not isinstance(archive_fingerprint, str) or not re.fullmatch(
                r"[0-9a-f]{64}", archive_fingerprint
            ):
                raise OSError(
                    "Campaign-completion marker has invalid archive proof"
                )
        else:
            _validate_module_archive(
                canonical_archive,
                expected_archives,
                module_name,
                archive_fingerprint,
                transaction_id,
            )
    elif archive_path is not None or archive_fingerprint is not None:
        raise OSError("Regeneration marker may not publish an archive")

    for field in ("summary_after", "campaign_after"):
        if not isinstance(pending.get(field), dict):
            raise OSError(
                f"Campaign-completion marker has invalid {field}"
            )
    prefixes = ["summary", "campaign"]
    if expected_receipt is not None:
        receipt_after = pending.get("receipt_after")
        if not isinstance(receipt_after, dict):
            raise OSError("Campaign-completion marker has invalid receipt_after")
        if (
            receipt_after.get("version")
            != _CAMPAIGN_COMPLETION_TRANSACTION_VERSION
            or receipt_after.get("operation") != "completion"
            or receipt_after.get("transaction_id") != transaction_id
            or receipt_after.get("module_name") != module_name
            or receipt_after.get("completion_id") != completion_id
            or receipt_after.get("result") != pending.get("summary_after")
            or receipt_after.get("summary_fingerprint")
            != _json_fingerprint(pending["summary_after"])
        ):
            raise OSError(
                "Campaign-completion marker receipt does not match summary"
            )
        prefixes.append("receipt")
    for prefix in prefixes:
        if not isinstance(pending.get(f"{prefix}_existed"), bool):
            raise OSError(
                f"Campaign-completion marker has invalid {prefix} snapshot"
            )
        if pending[f"{prefix}_existed"] and not isinstance(
            pending.get(f"{prefix}_before"), dict
        ):
            raise OSError(
                f"Campaign-completion marker has invalid {prefix} rollback"
            )


def _completion_target_specs(
    pending: Dict[str, Any],
) -> List[Tuple[str, str]]:
    specs = [
        ("summary", "summary_path"),
        ("campaign", "campaign_path"),
    ]
    if pending.get("receipt_path") is not None:
        specs.append(("receipt", "receipt_path"))
    return specs


def _completion_target_matches(
    path: str,
    existed: bool,
    payload: Any,
) -> bool:
    if os.path.exists(path) != existed:
        return False
    if not existed:
        return True
    return isinstance(payload, dict) and _load_json_dict(path) == payload


def _completion_targets_are_known(pending: Dict[str, Any]) -> bool:
    """Reject recovery if another writer produced an unjournaled third state."""
    for prefix, path_field in _completion_target_specs(pending):
        path = pending[path_field]
        matches_before = _completion_target_matches(
            path,
            pending[f"{prefix}_existed"],
            pending.get(f"{prefix}_before"),
        )
        matches_after = _completion_target_matches(
            path,
            True,
            pending[f"{prefix}_after"],
        )
        if not (matches_before or matches_after):
            return False
    return True


def _completion_targets_match(pending: Dict[str, Any], after: bool) -> bool:
    suffix = "after" if after else "before"
    for prefix, path_field in _completion_target_specs(pending):
        path = pending[path_field]
        expected_exists = True if after else pending[f"{prefix}_existed"]
        expected = pending[f"{prefix}_{suffix}"]
        if not _completion_target_matches(path, expected_exists, expected):
            return False
    return True


def _finish_completion_marker_cleanup(pending: Dict[str, Any]) -> None:
    work_path = pending.get("work_path")
    if isinstance(work_path, str) and work_path:
        _durable_remove(work_path)


def _mark_completion_work_committed(pending: Dict[str, Any]) -> None:
    """Publish a durable outcome before removing transaction markers."""
    work_path = pending.get("work_path")
    if not isinstance(work_path, str) or not work_path:
        return
    work = _load_json_dict(work_path)
    if work is None:
        if os.path.exists(work_path):
            raise OSError(f"Unreadable module-completion work marker {work_path}")
        return
    if (
        work.get("version") != _CAMPAIGN_COMPLETION_TRANSACTION_VERSION
        or work.get("operation") != "completion"
        or work.get("transaction_id") != pending.get("transaction_id")
        or work.get("module_name") != pending.get("module_name")
        or work.get("completion_id") != pending.get("completion_id")
    ):
        raise OSError("Module-completion work marker conflicts with commit")
    work["status"] = "committed"
    work["summary_fingerprint"] = _json_fingerprint(
        pending["summary_after"]
    )
    work["committed_at"] = datetime.now().isoformat()
    _durable_write_json(work_path, work)


def _recover_campaign_completion_transaction_locked(
    campaign_file: str,
    summaries_dir: str,
    archives_dir: str,
) -> Optional[Dict[str, Any]]:
    """Resolve a worker crash while summary and campaign were committed."""
    canonical_campaign = os.path.abspath(os.path.normpath(campaign_file))
    metadata_dir = _campaign_completion_metadata_dir(canonical_campaign)
    pending_path = os.path.join(metadata_dir, "pending.json")
    if not os.path.exists(pending_path):
        return None
    pending = _load_json_dict(pending_path)
    if pending is None:
        raise OSError(
            f"Unreadable campaign-completion recovery marker {pending_path}"
        )
    _validate_completion_pending_record(
        pending,
        canonical_campaign,
        summaries_dir,
        archives_dir,
    )
    if not _completion_targets_are_known(pending):
        raise OSError(
            "Campaign-completion recovery found an unjournaled target state"
        )

    if pending["status"] == "staged":
        for prefix, path_field in _completion_target_specs(pending):
            _write_completion_target(
                pending[path_field],
                pending[f"{prefix}_after"],
            )
        if not _completion_targets_match(pending, after=True):
            raise OSError("Campaign-completion roll-forward verification failed")
        _mark_completion_work_committed(pending)
        recovered_status = "rolled_forward"
    else:
        for prefix, path_field in _completion_target_specs(pending):
            _restore_completion_target(
                pending[path_field],
                pending[f"{prefix}_existed"],
                pending.get(f"{prefix}_before"),
            )
        if not _completion_targets_match(pending, after=False):
            raise OSError("Campaign-completion rollback verification failed")
        archive_path = pending.get("archive_path")
        _remove_scoped_archive(
            archive_path,
            pending["archives_dir"],
            pending["module_name"],
            pending["transaction_id"],
        )
        recovered_status = "rolled_back"

    if recovered_status == "rolled_back":
        # Rollback proof must outlive all transaction-owned cleanup.  If the
        # process dies after deleting the archive but before deleting work,
        # the retained pending marker makes the absent archive an explicitly
        # recoverable state instead of an unprovable orphan.
        _finish_completion_marker_cleanup(pending)
        _durable_remove(pending_path)
    else:
        # A rolled-forward committed work marker is independently verifiable,
        # so the legacy pending-then-work cleanup window is safe here.
        _durable_remove(pending_path)
        _finish_completion_marker_cleanup(pending)
    return {
        "status": recovered_status,
        "operation": pending.get("operation"),
        "module_name": pending.get("module_name"),
        "transaction_id": pending.get("transaction_id"),
        "completion_id": pending.get("completion_id"),
    }


def _load_committed_module_completion(
    paths: Dict[str, str],
    module_name: str,
    campaign_file: str,
) -> Optional[Dict[str, Any]]:
    summary = _load_json_dict(paths["summary"])
    campaign = _load_json_dict(campaign_file)
    if not summary or not campaign:
        return None
    completed_modules = campaign.get("completedModules")
    if not isinstance(completed_modules, list) or module_name not in completed_modules:
        return None
    return summary


def _remove_scoped_archive(
    archive_path: Any,
    archives_dir: str,
    module_name: str,
    transaction_id: Optional[str] = None,
) -> None:
    if not isinstance(archive_path, str) or not archive_path:
        return
    canonical_archive = _validate_module_archive_path(
        archive_path,
        archives_dir,
        module_name,
    )
    if os.path.exists(canonical_archive) and transaction_id is not None:
        archive = _load_json_dict(canonical_archive)
        if (
            not isinstance(archive, dict)
            or archive.get("completionTransactionId") != transaction_id
        ):
            raise OSError("Refusing to remove archive owned by another transaction")
    _durable_remove(canonical_archive)


def _recover_module_work_locked(
    paths: Dict[str, str],
    module_name: str,
    archives_dir: str,
    campaign_file: str,
    resume_completion_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Remove an orphan archive, or finish cleanup for a committed worker."""
    work = _load_json_dict(paths["work"])
    if work is None:
        if os.path.exists(paths["work"]):
            raise OSError(
                f"Unreadable module-completion work marker {paths['work']}"
            )
        return None
    if work.get("version") != _CAMPAIGN_COMPLETION_TRANSACTION_VERSION:
        raise OSError("Unsupported module-completion work marker version")
    module_name = _normalize_module_name(module_name)
    if work.get("module_name") != module_name:
        raise OSError("Module-completion work marker identity mismatch")
    if work.get("operation") != "completion":
        raise OSError("Module-completion work marker has invalid operation")
    if work.get("status") not in {"generating", "committed"}:
        raise OSError("Module-completion work marker has invalid status")
    transaction_id = work.get("transaction_id")
    if not isinstance(transaction_id, str) or not transaction_id:
        raise OSError("Module-completion work marker has no transaction id")

    completion_id = work.get("completion_id")
    try:
        completion_id = _normalize_completion_id(completion_id)
    except ValueError as exc:
        raise OSError(
            "Module-completion work marker has invalid completion_id"
        ) from exc
    archive_path = work.get("archive_path")
    archive_fingerprint = work.get("archive_fingerprint")
    if archive_path is not None:
        _validate_module_archive_path(
            archive_path,
            archives_dir,
            module_name,
        )
        if archive_fingerprint is not None:
            _validate_module_archive(
                archive_path,
                archives_dir,
                module_name,
                archive_fingerprint,
                transaction_id,
            )
        elif os.path.exists(archive_path):
            unproven_archive = _load_json_dict(archive_path)
            if (
                not isinstance(unproven_archive, dict)
                or unproven_archive.get("completionTransactionId")
                != transaction_id
            ):
                raise OSError(
                    "Module-completion work does not own unproven archive"
                )
    elif archive_fingerprint is not None:
        raise OSError("Module-completion work marker has orphan fingerprint")
    if work.get("status") == "committed" and archive_fingerprint is None:
        raise OSError("Committed module-completion work has no archive proof")

    summary = _load_json_dict(paths["summary"])
    expected_fingerprint = work.get("summary_fingerprint")
    if expected_fingerprint is not None and (
        not isinstance(expected_fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint)
    ):
        raise OSError("Module-completion work marker has invalid fingerprint")
    generated_summary = work.get("generated_summary")
    generated_fingerprint = work.get("generated_summary_fingerprint")
    if (generated_summary is None) != (generated_fingerprint is None):
        raise OSError("Module-completion work has partial generated output")
    if generated_summary is not None and (
        not isinstance(generated_summary, dict)
        or not isinstance(generated_fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{64}", generated_fingerprint)
        or _json_fingerprint(generated_summary) != generated_fingerprint
    ):
        raise OSError("Module-completion generated output is invalid")
    t038_summary_text = work.get("t038_summary_text")
    t038_summary_fingerprint = work.get("t038_summary_fingerprint")
    if (t038_summary_text is None) != (t038_summary_fingerprint is None):
        raise OSError("Module-completion work has partial T038 output")
    if t038_summary_text is not None and (
        not isinstance(t038_summary_text, str)
        or not t038_summary_text.strip()
        or t038_summary_text != t038_summary_text.strip()
        or not isinstance(t038_summary_fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{64}", t038_summary_fingerprint)
        or _json_fingerprint(t038_summary_text) != t038_summary_fingerprint
    ):
        raise OSError("Module-completion T038 output is invalid")
    if (
        generated_summary is not None
        and t038_summary_text is not None
        and generated_summary.get("summary") != t038_summary_text
    ):
        raise OSError("Module-completion generated output conflicts with T038")
    summary_matches = (
        isinstance(expected_fingerprint, str)
        and isinstance(summary, dict)
        and _json_fingerprint(summary) == expected_fingerprint
        and _load_committed_module_completion(
            paths,
            module_name,
            campaign_file,
        )
        is not None
    )
    receipt = None
    if completion_id is not None:
        receipt = _load_completion_receipt(
            paths,
            module_name,
            completion_id,
        )
    receipt_matches = (
        receipt is not None
        and receipt.get("transaction_id") == transaction_id
        and receipt.get("summary_fingerprint") == expected_fingerprint
    )
    if receipt is not None and not (summary_matches and receipt_matches):
        raise OSError(
            "Module-completion work marker conflicts with committed receipt"
        )
    committed = summary_matches and (
        receipt_matches
        if completion_id is not None
        else work.get("status") == "committed"
    )
    if not committed:
        if work.get("status") == "committed":
            raise OSError(
                "Committed module-completion work marker conflicts with state"
            )
        normalized_resume_id = _normalize_completion_id(resume_completion_id)
        if (
            normalized_resume_id is not None
            and completion_id == normalized_resume_id
            and (
                generated_summary is not None
                or t038_summary_text is not None
            )
            and archive_path is not None
            and archive_fingerprint is not None
        ):
            return {
                "status": "resumable",
                "transaction_id": transaction_id,
                "completion_id": completion_id,
                "work": copy.deepcopy(work),
            }
        _remove_scoped_archive(
            archive_path,
            archives_dir,
            module_name,
        )
    _durable_remove(paths["work"])
    return {
        "status": "committed_cleanup" if committed else "orphan_cleanup",
        "transaction_id": transaction_id,
        "completion_id": completion_id,
        "summary_fingerprint": expected_fingerprint,
    }


def _campaign_state_directories(
    campaign_file: str,
    summaries_dir: Optional[str] = None,
    archives_dir: Optional[str] = None,
) -> Tuple[str, str]:
    campaign_parent = os.path.dirname(
        os.path.abspath(os.path.normpath(campaign_file))
    )
    resolved_summaries = summaries_dir or os.path.join(
        campaign_parent,
        "campaign_summaries",
    )
    resolved_archives = archives_dir or os.path.join(
        campaign_parent,
        "campaign_archives",
    )
    return (
        os.path.abspath(os.path.normpath(resolved_summaries)),
        os.path.abspath(os.path.normpath(resolved_archives)),
    )


def mutate_campaign_state(
    campaign_file: str,
    mutator: Callable[[Dict[str, Any]], bool],
    *,
    summaries_dir: Optional[str] = None,
    archives_dir: Optional[str] = None,
    fallback: Optional[Dict[str, Any]] = None,
    write_if_missing: bool = False,
) -> Tuple[Dict[str, Any], bool]:
    """Recover, fresh-load, mutate, and atomically persist campaign state."""
    canonical_campaign = os.path.abspath(os.path.normpath(campaign_file))
    resolved_summaries, resolved_archives = _campaign_state_directories(
        canonical_campaign,
        summaries_dir,
        archives_dir,
    )
    with _campaign_transaction_lock(canonical_campaign):
        _recover_campaign_completion_transaction_locked(
            canonical_campaign,
            resolved_summaries,
            resolved_archives,
        )
        existed = os.path.exists(canonical_campaign)
        persisted = _load_json_dict(canonical_campaign) if existed else None
        if existed and persisted is None:
            raise OSError(f"Could not load campaign file {canonical_campaign}")
        if persisted is None:
            persisted = copy.deepcopy(fallback) if isinstance(fallback, dict) else {}
        updated = copy.deepcopy(persisted)
        changed = bool(mutator(updated))
        if changed or (write_if_missing and not existed):
            _write_completion_target(canonical_campaign, updated)
        return updated, changed


def _default_campaign_data() -> Dict[str, Any]:
    """Return a new campaign timeline without borrowing manager cache state."""
    return {
        "campaignName": "Fantasy Adventure Campaign",
        "currentModule": None,
        "hubModule": None,
        "completedModules": [],
        "availableModules": [],
        "hubs": {},
        "relationships": {},
        "artifacts": {},
        "worldState": {
            "keepOwnership": False,
            "majorDecisions": [],
            "crossModuleRelationships": {},
            "unlockedAreas": [],
            "hubEstablished": False,
        },
        "lastUpdated": datetime.now().isoformat(),
        "version": "1.0.0",
    }


def _validate_completion_intent(
    intent: Dict[str, Any],
    intent_path: str,
    campaign_file: str,
    summaries_dir: str,
) -> None:
    """Fail closed on malformed or mis-scoped transition intent metadata."""
    if not isinstance(intent, dict):
        raise OSError("Invalid module-completion intent")
    try:
        module_name = _normalize_module_name(intent.get("module_name"))
        to_module = _normalize_module_name(intent.get("to_module"))
        completion_id = _normalize_completion_id(intent.get("completion_id"))
    except ValueError as exc:
        raise OSError("Invalid module-completion intent identity") from exc
    if completion_id is None:
        raise OSError("Module-completion intent has no completion_id")
    transition_sequence = intent.get("transition_sequence")
    if (
        not isinstance(transition_sequence, int)
        or isinstance(transition_sequence, bool)
        or transition_sequence < 1
    ):
        raise OSError("Module-completion intent has invalid transition sequence")
    canonical_campaign = os.path.abspath(os.path.normpath(campaign_file))
    paths = _module_completion_paths(
        canonical_campaign,
        summaries_dir,
        module_name,
    )
    expected_path = _completion_intent_path(
        paths,
        module_name,
        completion_id,
    )
    if (
        intent.get("version") != _CAMPAIGN_COMPLETION_TRANSACTION_VERSION
        or intent.get("operation") != "module_transition_completion"
        or intent.get("status") not in {"prepared", "ready"}
        or intent.get("campaign_path") != canonical_campaign
        or os.path.abspath(os.path.normpath(intent_path)) != expected_path
        or module_name == to_module
        or intent.get("publication_kind") not in {"party", "location"}
        or not isinstance(intent.get("party_tracker_data"), dict)
        or not isinstance(intent.get("conversation_history"), list)
    ):
        raise OSError("Invalid module-completion intent metadata")


def _load_completion_intent(
    intent_path: str,
    campaign_file: str,
    summaries_dir: str,
) -> Optional[Dict[str, Any]]:
    intent = _load_json_dict(intent_path)
    if intent is None:
        if os.path.exists(intent_path):
            raise OSError(f"Unreadable module-completion intent {intent_path}")
        return None
    _validate_completion_intent(
        intent,
        intent_path,
        campaign_file,
        summaries_dir,
    )
    return intent


def _ordered_completion_intents(
    campaign_file: str,
    summaries_dir: str,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Load the transition queue in its durable publication order."""
    intents_dir = os.path.join(
        _campaign_completion_metadata_dir(campaign_file),
        "intents",
    )
    if not os.path.isdir(intents_dir):
        return []
    ordered = []
    for filename in os.listdir(intents_dir):
        if _COMPLETION_INTENT_TEMP_PATTERN.fullmatch(filename):
            continue
        intent_path = os.path.join(intents_dir, filename)
        if not filename.endswith(".json"):
            raise OSError("invalid intent filename")
        intent = _load_completion_intent(
            intent_path,
            campaign_file,
            summaries_dir,
        )
        if intent is not None:
            ordered.append((intent_path, intent))
    ordered.sort(
        key=lambda item: (
            item[1]["transition_sequence"],
            item[0],
        )
    )
    sequences = [item[1]["transition_sequence"] for item in ordered]
    if len(sequences) != len(set(sequences)):
        raise OSError("Duplicate module-completion transition sequence")
    return ordered


class CampaignManager:
    """Manages campaign state and inter-module continuity"""
    
    def __init__(self):
        """Initialize campaign manager"""
        self.campaign_file = "modules/campaign.json"
        self.summaries_dir = "modules/campaign_summaries"
        # No raw OpenAI client: all API calls route through api_client.create_completion()
        # per the multi-provider migration. A direct OpenAI(api_key=...) here crashed at
        # construction for Gemini/LM Studio users with no OPENAI_API_KEY (it was never used).

        # Ensure directories exist
        os.makedirs(self.summaries_dir, exist_ok=True)
        self.archives_dir = "modules/campaign_archives"
        os.makedirs(self.archives_dir, exist_ok=True)
        
        # Load or create campaign state
        self.campaign_data = self._load_campaign_data()

        # Callers may opt in to module refresh; construction only loads state
        # and resolves an interrupted campaign-completion journal when present.
        self.party_tracker_data = None
    
    def _load_campaign_data(self) -> Dict[str, Any]:
        """Recover an interrupted completion, then load or initialize state."""
        campaign, _changed = mutate_campaign_state(
            self.campaign_file,
            lambda _campaign: False,
            summaries_dir=self.summaries_dir,
            archives_dir=self.archives_dir,
            fallback=_default_campaign_data(),
            write_if_missing=True,
        )
        return campaign
    
    # P2c: refresh_modules / refresh_modules_async removed -- both were dead
    # (zero callers) and were the last consumers of the deleted transactional
    # lifecycle store. scan_and_integrate_new_modules() is the live scan path.

    def get_campaign_context(self) -> str:
        """Get campaign context for AI conversations"""
        context_parts = []
        
        # Campaign overview
        context_parts.append(f"CAMPAIGN: {self.campaign_data['campaignName']}")
        context_parts.append(f"Current Module: {self.campaign_data['currentModule']}")
        
        # Hubs
        if self.campaign_data['hubs']:
            context_parts.append("\nESTABLISHED HUBS:")
            for hub_name, hub_data in self.campaign_data['hubs'].items():
                context_parts.append(f"- {hub_name}: {hub_data}")
        
        # Completed modules summary
        if self.campaign_data['completedModules']:
            context_parts.append("\nPREVIOUS ADVENTURES:")
            for module in self.campaign_data['completedModules']:
                summary = self._load_module_summary(module)
                if summary:
                    context_parts.append(f"\n{module}: {summary.get('summary', 'No summary available')}")
        
        # Relationships
        if self.campaign_data['relationships']:
            context_parts.append("\nKEY RELATIONSHIPS:")
            for name, status in self.campaign_data['relationships'].items():
                context_parts.append(f"- {name}: {status}")
        
        # Artifacts
        if self.campaign_data['artifacts']:
            context_parts.append("\nIMPORTANT ARTIFACTS:")
            for artifact, data in self.campaign_data['artifacts'].items():
                context_parts.append(f"- {artifact}: {data}")
        
        # World State
        if self.campaign_data['worldState']:
            context_parts.append("\nWORLD STATE:")
            for key, value in self.campaign_data['worldState'].items():
                context_parts.append(f"- {key}: {value}")
        
        # Build context string
        context = "\n".join(context_parts)
        return context
    
    def _load_module_summaries(self, module_name: str) -> List[Dict[str, Any]]:
        """Load ALL module summaries for a given module (supports multiple visits)"""
        import glob
        
        summaries = []
        pattern = os.path.join(self.summaries_dir, f"{module_name}_summary_*.json")
        summary_files = glob.glob(pattern)
        
        # Sort by sequence number
        summary_files.sort(key=lambda x: self._extract_sequence_number(x))
        
        for summary_file in summary_files:
            try:
                summary = safe_json_load(summary_file)
                if summary:
                    summaries.append(summary)
            except Exception as e:
                warning(f"FILE_OP: Failed to load summary {summary_file}: {e}", category="file_operations")
        
        return summaries
    
    def _extract_sequence_number(self, file_path: str) -> int:
        """Extract sequence number from filename"""
        import re
        filename = os.path.basename(file_path)
        match = re.search(r'_(\d+)\.json$', filename)
        return int(match.group(1)) if match else 0
    
    def check_module_completion(self, module_name: str) -> bool:
        """Check if module is complete based on module_plot.json"""
        try:
            # Get module plot file
            path_manager = ModulePathManager(module_name)
            plot_file = os.path.join(path_manager.module_dir, "module_plot.json")
            
            if not os.path.exists(plot_file):
                debug(f"FILE_OP: No module_plot.json found for {module_name}", category="file_operations")
                return False
            
            plot_data = safe_json_load(plot_file)
            plot_points = plot_data.get('plotPoints', [])
            
            if not plot_points:
                return False
            
            # Find the final plot point (one with empty nextPoints)
            final_plot_point = None
            for point in plot_points:
                if not point.get('nextPoints', []):
                    final_plot_point = point
                    break
            
            if final_plot_point:
                return final_plot_point.get('status') == 'completed'
            
            # Fallback: Check if all plot points are completed
            return all(point.get('status') == 'completed' for point in plot_points)
            
        except Exception as e:
            error(f"FAILURE: Error checking module completion for {module_name}", exception=e, category="module_loading")
            return False
    
    def sync_party_tracker_with_plot(self, module_name: str) -> bool:
        """Sync party_tracker.json quest statuses with module_plot.json
        
        DEPRECATED: This method is no longer needed as module_plot.json is now the single 
        source of truth for quest data. The method is preserved for backward compatibility
        but returns immediately without performing any sync operations.
        """
        # Early return - activeQuests syncing is deprecated
        debug(f"DEPRECATED: sync_party_tracker_with_plot called for {module_name} - no action taken", category="plot_updates")
        return False
        
        try:
            # Load module plot data
            path_manager = ModulePathManager(module_name)
            plot_file = os.path.join(path_manager.module_dir, "module_plot.json")
            party_file = "party_tracker.json"
            
            if not os.path.exists(plot_file):
                debug(f"FILE_OP: No module_plot.json found for {module_name}", category="file_operations")
                return False
            
            plot_data = safe_json_load(plot_file)
            party_data = safe_json_load(party_file)
            
            # Create a mapping of quest IDs to their plot statuses
            quest_statuses = {}
            
            # Get statuses from main plot points
            for point in plot_data.get('plotPoints', []):
                quest_id = point.get('id')
                status = point.get('status')
                if quest_id and status:
                    quest_statuses[quest_id] = status
                
                # Also get side quest statuses
                for side_quest in point.get('sideQuests', []):
                    sq_id = side_quest.get('id')
                    sq_status = side_quest.get('status')
                    if sq_id and sq_status:
                        quest_statuses[sq_id] = sq_status
            
            # Update party tracker quests
            updated = False
            for quest in party_data.get('activeQuests', []):
                quest_id = quest.get('id')
                if quest_id in quest_statuses:
                    new_status = quest_statuses[quest_id]
                    if quest.get('status') != new_status:
                        debug(f"STATE_CHANGE: Syncing quest {quest_id}: {quest.get('status')} -> {new_status}", category="plot_updates")
                        quest['status'] = new_status
                        updated = True
            
            # Save updated party tracker if changes were made
            if updated:
                safe_json_dump(party_data, party_file)
                info(f"SUCCESS: Party tracker synced with module plot for {module_name}", category="plot_updates")
            
            return updated
            
        except Exception as e:
            error(f"FAILURE: Error syncing party tracker with plot for {module_name}", exception=e, category="plot_updates")
            return False
    
    @staticmethod
    def _apply_party_tracker_updates(
        party_tracker_data: Dict[str, Any],
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = copy.deepcopy(party_tracker_data)
        for key, value in updates.items():
            if key in {
                "currentLocationId",
                "currentLocation",
                "currentAreaId",
                "currentArea",
            }:
                world = updated.setdefault("worldConditions", {})
                if not isinstance(world, dict):
                    raise OSError("party_tracker worldConditions is invalid")
                world[key] = copy.deepcopy(value)
            else:
                updated[key] = copy.deepcopy(value)
        return updated

    def publish_party_module_transition(
        self,
        module_name: str,
        to_module: str,
        updates: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        completion_id: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Atomically order intent preparation before a fresh party switch."""
        module_name = _normalize_module_name(module_name)
        to_module = _normalize_module_name(to_module)
        completion_id = _normalize_completion_id(completion_id)
        if completion_id is None:
            raise ValueError("completion transitions require a completion_id")
        with _party_module_transition_lock():
            persisted = safe_json_load("party_tracker.json")
            if not isinstance(persisted, dict):
                raise OSError("Cannot load party tracker for module transition")
            persisted_module = persisted.get("module")
            if persisted_module != module_name:
                if persisted_module == to_module:
                    paths = _module_completion_paths(
                        self.campaign_file,
                        self.summaries_dir,
                        module_name,
                    )
                    intent_path = _completion_intent_path(
                        paths,
                        module_name,
                        completion_id,
                    )
                    with path_transaction_lock(
                        paths["lock_target"],
                        suffix=".completion.lock",
                    ), _campaign_transaction_lock(self.campaign_file):
                        intent = _load_completion_intent(
                            intent_path,
                            self.campaign_file,
                            self.summaries_dir,
                        )
                        receipt = _load_completion_receipt(
                            paths,
                            module_name,
                            completion_id,
                        )
                        if receipt is not None:
                            _validate_receipt_committed_projection(
                                paths,
                                module_name,
                                self.campaign_file,
                                receipt,
                            )
                    if intent is not None or receipt is not None:
                        original = (
                            copy.deepcopy(intent["party_tracker_data"])
                            if intent is not None
                            else copy.deepcopy(persisted)
                        )
                        return original, copy.deepcopy(persisted)
                raise OSError(
                    "Party module changed before transition publication"
                )
            original = copy.deepcopy(persisted)
            self.stage_module_completion_intent(
                module_name,
                to_module,
                original,
                conversation_history,
                completion_id,
            )
            updated = self._apply_party_tracker_updates(persisted, updates)
            if updated.get("module") != to_module:
                raise OSError("Party transition update has wrong destination")
            safe_json_dump(updated, "party_tracker.json")
            self.mark_module_completion_intent_ready(
                module_name,
                completion_id,
                conversation_history=conversation_history,
            )
            return original, updated

    def publish_location_module_transition(
        self,
        module_name: str,
        to_module: str,
        conversation_history: List[Dict[str, Any]],
        completion_id: str,
        transition_callable: Callable[[], Any],
    ) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """Run the location write between prepared and ready intent states."""
        module_name = _normalize_module_name(module_name)
        to_module = _normalize_module_name(to_module)
        completion_id = _normalize_completion_id(completion_id)
        if completion_id is None:
            raise ValueError("completion transitions require a completion_id")
        with _party_module_transition_lock():
            persisted = safe_json_load("party_tracker.json")
            if (
                not isinstance(persisted, dict)
                or persisted.get("module") != module_name
            ):
                raise OSError(
                    "Party module changed before location transition"
                )
            self.stage_module_completion_intent(
                module_name,
                to_module,
                persisted,
                conversation_history,
                completion_id,
                publication_kind="location",
            )
            try:
                transition_result = transition_callable()
            except BaseException as transition_exc:
                current = safe_json_load("party_tracker.json")
                if current == persisted:
                    self._cancel_prepared_module_completion_intent(
                        module_name,
                        completion_id,
                    )
                    raise
                raise OSError(
                    "Location transition failed after partially changing party state"
                ) from transition_exc
            if not transition_result:
                current = safe_json_load("party_tracker.json")
                if current != persisted:
                    raise OSError(
                        "Location transition returned false after changing party state"
                    )
                self._cancel_prepared_module_completion_intent(
                    module_name,
                    completion_id,
                )
                return transition_result, None
            updated = safe_json_load("party_tracker.json")
            if (
                not isinstance(updated, dict)
                or updated.get("module") != module_name
            ):
                raise OSError(
                    "Location transition produced an unexpected party module"
                )
            prior_location = persisted.get("worldConditions", {}).get(
                "currentLocationId"
            )
            updated_location = updated.get("worldConditions", {}).get(
                "currentLocationId"
            )
            if (
                not isinstance(updated_location, str)
                or not updated_location
                or updated_location == prior_location
            ):
                if updated == persisted:
                    self._cancel_prepared_module_completion_intent(
                        module_name,
                        completion_id,
                    )
                raise OSError(
                    "Location transition reported success without changing location"
                )
            resolved_destination = self.get_module_from_location(
                updated_location
            )
            if resolved_destination != to_module:
                raise OSError(
                    "Location transition did not persist a destination-module location"
                )
            updated["module"] = to_module
            safe_json_dump(updated, "party_tracker.json")
            self.mark_module_completion_intent_ready(
                module_name,
                completion_id,
                conversation_history=conversation_history,
            )
            return transition_result, updated

    def _cancel_prepared_module_completion_intent(
        self,
        module_name: str,
        completion_id: str,
    ) -> None:
        """Cancel only a proven no-op transition before party publication."""
        module_name = _normalize_module_name(module_name)
        completion_id = _normalize_completion_id(completion_id)
        paths = _module_completion_paths(
            self.campaign_file,
            self.summaries_dir,
            module_name,
        )
        intent_path = _completion_intent_path(
            paths,
            module_name,
            completion_id,
        )
        with path_transaction_lock(
            paths["lock_target"], suffix=".completion.lock"
        ), _campaign_transaction_lock(self.campaign_file):
            intent = _load_completion_intent(
                intent_path,
                self.campaign_file,
                self.summaries_dir,
            )
            if intent is None:
                return
            if intent.get("status") != "prepared":
                raise OSError("Refusing to cancel a ready completion intent")
            if _load_completion_receipt(
                paths,
                module_name,
                completion_id,
            ) is not None:
                raise OSError("Refusing to cancel a receipt-backed intent")
            _durable_remove(intent_path)

    def get_module_completion_publication_state(
        self,
        module_name: str,
        completion_id: str,
    ) -> str:
        """Return prepared, ready, committed, or absent for a transition."""
        module_name = _normalize_module_name(module_name)
        completion_id = _normalize_completion_id(completion_id)
        if completion_id is None:
            raise ValueError("completion transitions require a completion_id")
        paths = _module_completion_paths(
            self.campaign_file,
            self.summaries_dir,
            module_name,
        )
        intent_path = _completion_intent_path(
            paths,
            module_name,
            completion_id,
        )
        with _party_module_transition_lock(), path_transaction_lock(
            paths["lock_target"], suffix=".completion.lock"
        ), _campaign_transaction_lock(self.campaign_file):
            intent = _load_completion_intent(
                intent_path,
                self.campaign_file,
                self.summaries_dir,
            )
            if intent is not None:
                return intent["status"]
            receipt = _load_completion_receipt(
                paths,
                module_name,
                completion_id,
            )
            if receipt is not None:
                _validate_receipt_committed_projection(
                    paths,
                    module_name,
                    self.campaign_file,
                    receipt,
                )
                return "committed"
            return "absent"

    def stage_module_completion_intent(
        self,
        module_name: str,
        to_module: str,
        party_tracker_data: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        completion_id: str,
        publication_kind: str = "party",
    ) -> Dict[str, Any]:
        """Durably prepare completion before the party module can switch."""
        module_name = _normalize_module_name(module_name)
        to_module = _normalize_module_name(to_module)
        completion_id = _normalize_completion_id(completion_id)
        if completion_id is None:
            raise ValueError("completion intents require a completion_id")
        if module_name == to_module:
            raise ValueError("completion intent requires distinct modules")
        if not isinstance(party_tracker_data, dict):
            raise ValueError("party_tracker_data must be an object")
        if not isinstance(conversation_history, list):
            raise ValueError("conversation_history must be a list")
        if publication_kind not in {"party", "location"}:
            raise ValueError("Unsupported completion intent publication kind")
        paths = _module_completion_paths(
            self.campaign_file,
            self.summaries_dir,
            module_name,
        )
        intent_path = _completion_intent_path(
            paths,
            module_name,
            completion_id,
        )
        with _party_module_transition_lock(), path_transaction_lock(
            paths["lock_target"],
            suffix=".completion.lock",
        ), _campaign_transaction_lock(self.campaign_file):
            existing = _load_completion_intent(
                intent_path,
                self.campaign_file,
                self.summaries_dir,
            )
            if existing is not None:
                if (
                    existing.get("to_module") != to_module
                    or existing.get("publication_kind") != publication_kind
                ):
                    raise OSError(
                        "Completion intent ID was reused for another transition"
                    )
                return copy.deepcopy(existing)
            receipt = _load_completion_receipt(
                paths,
                module_name,
                completion_id,
            )
            if receipt is not None:
                _validate_receipt_committed_projection(
                    paths,
                    module_name,
                    self.campaign_file,
                    receipt,
                )
                return {
                    "status": "committed",
                    "module_name": module_name,
                    "to_module": to_module,
                    "completion_id": completion_id,
                }
            intent = {
                "version": _CAMPAIGN_COMPLETION_TRANSACTION_VERSION,
                "operation": "module_transition_completion",
                "status": "prepared",
                "campaign_path": os.path.abspath(
                    os.path.normpath(self.campaign_file)
                ),
                "module_name": module_name,
                "to_module": to_module,
                "completion_id": completion_id,
                "publication_kind": publication_kind,
                "transition_sequence": (
                    _next_completion_intent_sequence_locked(
                        self.campaign_file
                    )
                ),
                "party_tracker_data": copy.deepcopy(party_tracker_data),
                "conversation_history": copy.deepcopy(conversation_history),
                "created_at": datetime.now().isoformat(),
            }
            _durable_write_json(intent_path, intent)
            return copy.deepcopy(intent)

    def mark_module_completion_intent_ready(
        self,
        module_name: str,
        completion_id: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Publish that the corresponding party-module switch committed."""
        module_name = _normalize_module_name(module_name)
        completion_id = _normalize_completion_id(completion_id)
        if completion_id is None:
            raise ValueError("completion intents require a completion_id")
        if conversation_history is not None and not isinstance(
            conversation_history, list
        ):
            raise ValueError("conversation_history must be a list")
        paths = _module_completion_paths(
            self.campaign_file,
            self.summaries_dir,
            module_name,
        )
        intent_path = _completion_intent_path(
            paths,
            module_name,
            completion_id,
        )
        with _party_module_transition_lock(), path_transaction_lock(
            paths["lock_target"], suffix=".completion.lock"
        ), _campaign_transaction_lock(self.campaign_file):
            intent = _load_completion_intent(
                intent_path,
                self.campaign_file,
                self.summaries_dir,
            )
            if intent is None:
                receipt = _load_completion_receipt(
                    paths,
                    module_name,
                    completion_id,
                )
                if receipt is None:
                    raise OSError("Module-completion intent disappeared")
                _validate_receipt_committed_projection(
                    paths,
                    module_name,
                    self.campaign_file,
                    receipt,
                )
                return {
                    "status": "committed",
                    "module_name": module_name,
                    "completion_id": completion_id,
                }
            persisted_party = safe_json_load("party_tracker.json")
            if (
                not isinstance(persisted_party, dict)
                or persisted_party.get("module") != intent["to_module"]
            ):
                raise OSError(
                    "Cannot ready completion intent before party module switch"
                )
            intent["status"] = "ready"
            intent["ready_at"] = datetime.now().isoformat()
            if conversation_history is not None:
                intent["conversation_history"] = copy.deepcopy(
                    conversation_history
                )
            _durable_write_json(intent_path, intent)
            return copy.deepcopy(intent)

    def complete_staged_module_completion(
        self,
        module_name: str,
        completion_id: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Drain one transition while holding the global publication order."""
        with _party_module_transition_lock():
            return self._complete_staged_module_completion_locked(
                module_name,
                completion_id,
                conversation_history=conversation_history,
            )

    def _complete_staged_module_completion_locked(
        self,
        module_name: str,
        completion_id: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Drain one durable intent; retain it until receipt-backed success."""
        module_name = _normalize_module_name(module_name)
        completion_id = _normalize_completion_id(completion_id)
        if completion_id is None:
            raise ValueError("completion intents require a completion_id")
        if conversation_history is not None and not isinstance(
            conversation_history, list
        ):
            raise ValueError("conversation_history must be a list")
        paths = _module_completion_paths(
            self.campaign_file,
            self.summaries_dir,
            module_name,
        )
        intent_path = _completion_intent_path(
            paths,
            module_name,
            completion_id,
        )
        with _party_module_transition_lock(), path_transaction_lock(
            paths["lock_target"], suffix=".completion.lock"
        ), _campaign_transaction_lock(self.campaign_file):
            intent = _load_completion_intent(
                intent_path,
                self.campaign_file,
                self.summaries_dir,
            )
            if intent is None:
                receipt = _load_completion_receipt(
                    paths,
                    module_name,
                    completion_id,
                )
                if receipt is not None:
                    _validate_receipt_committed_projection(
                        paths,
                        module_name,
                        self.campaign_file,
                        receipt,
                    )
                return (
                    copy.deepcopy(receipt["result"])
                    if receipt is not None
                    else None
                )
            ordered_intents = _ordered_completion_intents(
                self.campaign_file,
                self.summaries_dir,
            )
            if not ordered_intents:
                raise OSError("Module-completion intent queue disappeared")
            oldest_path = ordered_intents[0][0]
            if os.path.abspath(os.path.normpath(oldest_path)) != os.path.abspath(
                os.path.normpath(intent_path)
            ):
                # A later targeted worker must not overtake an earlier
                # transition. Preserve its freshest bounded history now; the
                # oldest-first drain will use it when this intent reaches the
                # head of the queue.
                if conversation_history is not None:
                    intent["conversation_history"] = copy.deepcopy(
                        conversation_history
                    )
                    _durable_write_json(intent_path, intent)
                return None
            if intent["status"] == "prepared":
                persisted_party = safe_json_load("party_tracker.json")
                if not isinstance(persisted_party, dict):
                    raise OSError(
                        "Cannot reconcile prepared completion intent without party state"
                    )
                persisted_module = persisted_party.get("module")
                if persisted_module == intent["module_name"]:
                    if intent["publication_kind"] == "party":
                        # updatePartyTracker publishes all requested fields,
                        # including module, in one atomic file replacement.
                        # If module is still the source, that publication did
                        # not land; unrelated party/effect writes may safely
                        # have advanced other fields meanwhile.
                        _durable_remove(intent_path)
                        return None
                    source_location_id = intent["party_tracker_data"].get(
                        "worldConditions", {}
                    ).get("currentLocationId")
                    location_id = persisted_party.get(
                        "worldConditions", {}
                    ).get("currentLocationId")
                    if location_id == source_location_id:
                        _durable_remove(intent_path)
                        return None
                    detected_module = self.get_module_from_location(location_id)
                    if detected_module != intent["to_module"]:
                        raise OSError(
                            "Prepared completion intent found mixed source state"
                        )
                    repaired_party = copy.deepcopy(persisted_party)
                    repaired_party["module"] = intent["to_module"]
                    safe_json_dump(repaired_party, "party_tracker.json")
                    persisted_module = intent["to_module"]
                if persisted_module != intent["to_module"]:
                    next_intent = (
                        ordered_intents[1][1]
                        if len(ordered_intents) > 1
                        else None
                    )
                    superseded = (
                        isinstance(next_intent, dict)
                        and next_intent.get("status") == "ready"
                        and next_intent.get("module_name")
                        == intent["module_name"]
                        and (
                            intent["publication_kind"] == "party"
                            or next_intent.get(
                                "party_tracker_data", {}
                            ).get("worldConditions", {}).get(
                                "currentLocationId"
                            )
                            == intent["party_tracker_data"].get(
                                "worldConditions", {}
                            ).get("currentLocationId")
                        )
                    )
                    continued_chain = (
                        isinstance(next_intent, dict)
                        and next_intent.get("status") == "ready"
                        and next_intent.get("module_name")
                        == intent["to_module"]
                        and next_intent.get("party_tracker_data", {}).get(
                            "module"
                        )
                        == intent["to_module"]
                    )
                    if superseded:
                        # The earlier publisher died after prepare but before
                        # changing party state. A later ready transition from
                        # the byte-identical source snapshot is durable proof
                        # that this prepare was superseded without taking
                        # effect, even if a longer ready chain has since moved
                        # the living party again.
                        _durable_remove(intent_path)
                        return None
                    if not continued_chain:
                        raise OSError(
                            "Prepared completion intent found a third party module state"
                        )
                intent["status"] = "ready"
                intent["ready_at"] = datetime.now().isoformat()
            if conversation_history is not None:
                intent["conversation_history"] = copy.deepcopy(
                    conversation_history
                )
            _durable_write_json(intent_path, intent)
            party_snapshot = copy.deepcopy(intent["party_tracker_data"])
            intent_history = copy.deepcopy(intent["conversation_history"])
            lifecycle_epoch = _load_campaign_lifecycle_epoch(
                self.campaign_file
            )

        result = self.complete_module(
            module_name,
            party_snapshot,
            intent_history,
            completion_id=completion_id,
            _expected_lifecycle_epoch=lifecycle_epoch,
        )

        with path_transaction_lock(
            paths["lock_target"],
            suffix=".completion.lock",
        ), _campaign_transaction_lock(self.campaign_file):
            receipt = _load_completion_receipt(
                paths,
                module_name,
                completion_id,
            )
            if receipt is None or receipt["result"] != result:
                raise OSError(
                    "Module completion returned without its durable receipt"
                )
            _validate_receipt_committed_projection(
                paths,
                module_name,
                self.campaign_file,
                receipt,
            )
            _durable_remove(intent_path)
        return result

    def drain_module_completion_intents(self) -> Dict[str, Any]:
        """Drain transitions oldest-first; stop before any failed boundary."""
        outcome = {
            "completed": [],
            "cancelled": [],
            "blocked": [],
            "failed": [],
        }
        with _party_module_transition_lock():
            try:
                ordered_intents = _ordered_completion_intents(
                    self.campaign_file,
                    self.summaries_dir,
                )
            except Exception as exc:
                outcome["failed"].append(
                    {
                        "path": os.path.join(
                            _campaign_completion_metadata_dir(
                                self.campaign_file
                            ),
                            "intents",
                        ),
                        "error": str(exc),
                    }
                )
                error(
                    "FAILURE: Could not load ordered module-completion queue",
                    exception=exc,
                    category="module_management",
                )
                return outcome

            for intent_path, intent in ordered_intents:
                try:
                    result = self.complete_staged_module_completion(
                        intent["module_name"],
                        intent["completion_id"],
                    )
                    if result is None:
                        if os.path.exists(intent_path):
                            outcome["blocked"].append(
                                intent["completion_id"]
                            )
                            break
                        outcome["cancelled"].append(intent["completion_id"])
                    else:
                        outcome["completed"].append(intent["completion_id"])
                except Exception as exc:
                    outcome["failed"].append(
                        {"path": intent_path, "error": str(exc)}
                    )
                    error(
                        "FAILURE: Could not drain module completion intent "
                        f"{intent_path}",
                        exception=exc,
                        category="module_management",
                    )
                    break
            return outcome

    def complete_module(
        self,
        module_name: str,
        party_tracker_data: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        completion_id: Optional[str] = None,
        _expected_lifecycle_epoch: Any = _LIFECYCLE_EPOCH_UNSET,
    ) -> Dict[str, Any]:
        """Complete one module once, even across concurrent worker processes."""
        module_name = _normalize_module_name(module_name)
        completion_id = _normalize_completion_id(completion_id)
        if _expected_lifecycle_epoch is _LIFECYCLE_EPOCH_UNSET:
            with _campaign_transaction_lock(self.campaign_file):
                expected_lifecycle_epoch = _load_campaign_lifecycle_epoch(
                    self.campaign_file
                )
        else:
            expected_lifecycle_epoch = _expected_lifecycle_epoch
        key = _module_completion_key(
            self.campaign_file,
            module_name,
            completion_id,
        )
        completion_paths = _module_completion_paths(
            self.campaign_file,
            self.summaries_dir,
            module_name,
        )
        pre_lock_snapshot = _completion_snapshot(
            completion_paths,
            module_name,
        )
        with _MODULE_COMPLETION_FLIGHTS_GUARD:
            completion = _MODULE_COMPLETION_FLIGHTS.get(key)
            if completion is None:
                completion = Future()
                _MODULE_COMPLETION_FLIGHTS[key] = completion
                is_leader = True
            else:
                is_leader = False

        if not is_leader:
            result = copy.deepcopy(completion.result())
            # The leader can finish immediately before a restore/reset wins
            # the lifecycle boundary. A joined caller must re-linearize its
            # own return rather than blindly returning the Future payload from
            # an earlier timeline.
            with _campaign_transaction_lock(self.campaign_file):
                if _load_campaign_lifecycle_epoch(
                    self.campaign_file
                ) != expected_lifecycle_epoch:
                    raise OSError(
                        "Campaign timeline changed during module completion"
                    )
                receipt = _load_completion_receipt(
                    completion_paths,
                    module_name,
                    completion_id,
                )
                if completion_id is not None:
                    if receipt is None or receipt.get("result") != result:
                        raise OSError(
                            "Joined completion lost its durable receipt"
                        )
                    projection_receipt = receipt
                else:
                    projection_receipt = {
                        "result": result,
                        "summary_fingerprint": _json_fingerprint(result),
                    }
                _validate_receipt_committed_projection(
                    completion_paths,
                    module_name,
                    self.campaign_file,
                    projection_receipt,
                )
                persisted_campaign = _load_json_dict(self.campaign_file)
                if persisted_campaign is not None:
                    self.campaign_data = persisted_campaign
                return result

        try:
            result = self._complete_module_once(
                module_name,
                party_tracker_data,
                conversation_history,
                completion_paths=completion_paths,
                pre_lock_snapshot=pre_lock_snapshot,
                completion_id=completion_id,
                expected_lifecycle_epoch=expected_lifecycle_epoch,
            )
        except BaseException as exc:
            completion.set_exception(exc)
            raise
        else:
            completion.set_result(copy.deepcopy(result))
            return result
        finally:
            with _MODULE_COMPLETION_FLIGHTS_GUARD:
                if _MODULE_COMPLETION_FLIGHTS.get(key) is completion:
                    del _MODULE_COMPLETION_FLIGHTS[key]

    def _complete_module_once(
        self,
        module_name: str,
        party_tracker_data: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        completion_paths: Optional[Dict[str, str]] = None,
        pre_lock_snapshot=None,
        completion_id: Optional[str] = None,
        expected_lifecycle_epoch: Optional[str] = None,
    ) -> Dict[str, Any]:
        module_name = _normalize_module_name(module_name)
        completion_id = _normalize_completion_id(completion_id)
        paths = completion_paths or _module_completion_paths(
            self.campaign_file,
            self.summaries_dir,
            module_name,
        )
        if pre_lock_snapshot is None:
            pre_lock_snapshot = _completion_snapshot(paths, module_name)
        with path_transaction_lock(
            paths["lock_target"],
            suffix=".completion.lock",
        ):
            # A worker for any module can recover a process that died while
            # holding the campaign-wide commit lock.  The per-module work
            # marker then distinguishes an orphan archive from a completed
            # transaction whose final cleanup was interrupted.
            with _campaign_transaction_lock(self.campaign_file):
                recovery = _recover_campaign_completion_transaction_locked(
                    self.campaign_file,
                    self.summaries_dir,
                    self.archives_dir,
                )
                persisted_campaign = _load_json_dict(self.campaign_file)
                if persisted_campaign is not None:
                    self.campaign_data = persisted_campaign
            work_recovery = _recover_module_work_locked(
                paths,
                module_name,
                self.archives_dir,
                self.campaign_file,
                resume_completion_id=completion_id,
            )

            # Receipt replay and legacy-overlap reuse are completion fast
            # paths, but they still cross the restore/reset lifecycle
            # boundary. Linearize their validation, snapshot, epoch check,
            # and return under the same campaign lock used by lifecycle work.
            with _campaign_transaction_lock(self.campaign_file):
                if _load_campaign_lifecycle_epoch(
                    self.campaign_file
                ) != expected_lifecycle_epoch:
                    raise OSError(
                        "Campaign timeline changed during module completion"
                    )
                receipt = _load_completion_receipt(
                    paths,
                    module_name,
                    completion_id,
                )
                if receipt is not None:
                    _validate_receipt_committed_projection(
                        paths,
                        module_name,
                        self.campaign_file,
                        receipt,
                    )
                    persisted_campaign = _load_json_dict(self.campaign_file)
                    if persisted_campaign is not None:
                        self.campaign_data = persisted_campaign
                    return copy.deepcopy(receipt["result"])

                post_lock_snapshot = _completion_snapshot(paths, module_name)
                (
                    pre_summary,
                    pre_pending,
                    pre_work,
                    pre_work_status,
                    pre_work_fp,
                    pre_visit_count,
                ) = pre_lock_snapshot
                post_summary = post_lock_snapshot[0]
                post_visit_count = post_lock_snapshot[5]
                observed_transaction_ids = {
                    value for value in (pre_pending, pre_work) if value
                }
                recovered_commit = (
                    isinstance(recovery, dict)
                    and recovery.get("status") == "rolled_forward"
                    and recovery.get("operation") == "completion"
                    and recovery.get("transaction_id")
                    in observed_transaction_ids
                ) or (
                    isinstance(work_recovery, dict)
                    and work_recovery.get("status") == "committed_cleanup"
                    and work_recovery.get("transaction_id")
                    in observed_transaction_ids
                )
                observed_committed_cleanup = (
                    pre_work_status == "committed"
                    and pre_work_fp is not None
                    and pre_work_fp == pre_summary == post_summary
                )
                visit_advanced = (
                    isinstance(post_visit_count, int)
                    and post_visit_count > (pre_visit_count or 0)
                )
                overlapping_commit = (
                    visit_advanced
                    or recovered_commit
                    or observed_committed_cleanup
                )
                if (
                    completion_id is None
                    and overlapping_commit
                    and not (
                        isinstance(recovery, dict)
                        and recovery.get("status") == "rolled_back"
                    )
                ):
                    committed = _load_committed_module_completion(
                        paths,
                        module_name,
                        self.campaign_file,
                    )
                    if committed is not None:
                        persisted_campaign = _load_json_dict(
                            self.campaign_file
                        )
                        if persisted_campaign is not None:
                            self.campaign_data = persisted_campaign
                        return copy.deepcopy(committed)

            info(
                f"STATE_CHANGE: Completing module: {module_name}",
                category="module_loading",
            )
            resumed_work = (
                work_recovery.get("work")
                if isinstance(work_recovery, dict)
                and work_recovery.get("status") == "resumable"
                else None
            )
            if isinstance(resumed_work, dict):
                work = resumed_work
                transaction_id = work["transaction_id"]
                archive_path = work["archive_path"]
                summary = copy.deepcopy(work.get("generated_summary"))
            else:
                transaction_id = uuid4().hex
                summary = None
                work = {
                    "version": _CAMPAIGN_COMPLETION_TRANSACTION_VERSION,
                    "transaction_id": transaction_id,
                    "module_name": module_name,
                    "operation": "completion",
                    "status": "generating",
                    "completion_id": completion_id,
                    "archive_path": None,
                    "archive_fingerprint": None,
                    "started_at": datetime.now().isoformat(),
                }
                with _campaign_transaction_lock(self.campaign_file):
                    current_lifecycle_epoch = _load_campaign_lifecycle_epoch(
                        self.campaign_file
                    )
                    if current_lifecycle_epoch != expected_lifecycle_epoch:
                        raise OSError(
                            "Campaign timeline changed before module completion began"
                        )
                    _durable_write_json(paths["work"], work)
                archive_path = None
            try:
                if not isinstance(resumed_work, dict):
                    archive_result = self._archive_conversation_history(
                        module_name,
                        conversation_history,
                        completion_work_path=paths["work"],
                        completion_work=work,
                    )
                    if not archive_result:
                        raise OSError(
                            f"Could not durably archive conversation for {module_name}"
                        )
                    if isinstance(archive_result, str):
                        archive_path = os.path.abspath(
                            os.path.normpath(archive_result)
                        )
                        work["archive_path"] = archive_path
                        _durable_write_json(paths["work"], work)

                if not isinstance(summary, dict):
                    resume_t038_summary_text = work.get("t038_summary_text")

                    def checkpoint_t038(summary_text: str) -> None:
                        work["t038_summary_text"] = summary_text
                        work["t038_summary_fingerprint"] = _json_fingerprint(
                            summary_text
                        )
                        _durable_write_json(paths["work"], work)

                    summary = self._generate_module_summary(
                        module_name,
                        party_tracker_data,
                        conversation_history,
                        skip_archiving=True,
                        _resume_t038_summary_text=resume_t038_summary_text,
                        _t038_checkpoint=checkpoint_t038,
                    )
                    # Persist the combined T038/T039 output immediately. A
                    # same-ID retry can resume locally after a crash; the
                    # irreducible gap between provider return and this write
                    # remains at-least-once external-call uncertainty.
                    work["generated_summary"] = copy.deepcopy(summary)
                    work["generated_summary_fingerprint"] = _json_fingerprint(
                        summary
                    )
                    _durable_write_json(paths["work"], work)

                with _campaign_transaction_lock(self.campaign_file):
                    if _load_campaign_lifecycle_epoch(
                        self.campaign_file
                    ) != expected_lifecycle_epoch:
                        raise OSError(
                            "Campaign timeline changed during module completion"
                        )
                    _recover_campaign_completion_transaction_locked(
                        self.campaign_file,
                        self.summaries_dir,
                        self.archives_dir,
                    )
                    visit_info = self._get_module_visit_info(module_name)
                    now = datetime.now().isoformat()
                    summary["visitCount"] = visit_info["visitCount"] + 1
                    summary["firstVisitDate"] = (
                        visit_info["firstVisitDate"] or now
                    )
                    summary["lastVisitDate"] = now
                    summary["sequenceNumber"] = 1
                    work["summary_fingerprint"] = _json_fingerprint(summary)
                    _durable_write_json(paths["work"], work)
                    self._commit_module_summary_locked(
                        module_name,
                        summary,
                        transaction_id=transaction_id,
                        archive_path=archive_path,
                        archive_fingerprint=work.get("archive_fingerprint"),
                        work_path=paths["work"],
                        completion_id=completion_id,
                        operation="completion",
                    )
            except BaseException:
                pending = _load_json_dict(paths["campaign_pending"])
                pending_owns_work = (
                    isinstance(pending, dict)
                    and pending.get("transaction_id") == transaction_id
                )
                if not pending_owns_work:
                    latest_work = _load_json_dict(paths["work"])
                    if isinstance(latest_work, dict):
                        _remove_scoped_archive(
                            latest_work.get("archive_path"),
                            self.archives_dir,
                            module_name,
                            transaction_id,
                        )
                    _durable_remove(paths["work"])
                raise

            # The summary, campaign projection, and optional receipt are now
            # committed.  Work-marker cleanup is best effort: if it fails,
            # the marker lets the next locked entry verify the receipt and
            # finish cleanup without deleting the committed archive.
            try:
                _durable_remove(paths["work"])
            except Exception as cleanup_exc:
                warning(
                    "FILE_OP: Module completion committed but work-marker "
                    f"cleanup was deferred for {module_name}: {cleanup_exc}",
                    category="file_operations",
                )
            return summary

    def _commit_module_summary_locked(
        self,
        module_name: str,
        summary: Dict[str, Any],
        transaction_id: Optional[str] = None,
        archive_path: Optional[str] = None,
        archive_fingerprint: Optional[str] = None,
        work_path: Optional[str] = None,
        completion_id: Optional[str] = None,
        operation: str = "completion",
    ) -> None:
        """Crash-recoverably commit summary and campaign projection."""
        module_name = _normalize_module_name(module_name)
        _recover_campaign_completion_transaction_locked(
            self.campaign_file,
            self.summaries_dir,
            self.archives_dir,
        )
        paths = _module_completion_paths(
            self.campaign_file,
            self.summaries_dir,
            module_name,
        )
        summary_file = paths["summary"]
        campaign_file = os.path.abspath(os.path.normpath(self.campaign_file))
        pending_path = paths["campaign_pending"]
        transaction_id = transaction_id or uuid4().hex
        completion_id = _normalize_completion_id(completion_id)
        if operation not in {"completion", "regeneration"}:
            raise ValueError(f"Unsupported campaign completion operation {operation}")
        if completion_id is not None and operation != "completion":
            raise ValueError("Only completions may publish completion receipts")
        if operation == "completion":
            _validate_module_archive(
                archive_path,
                self.archives_dir,
                module_name,
                archive_fingerprint,
                transaction_id,
            )
        elif archive_path is not None or archive_fingerprint is not None:
            raise ValueError("Regeneration may not publish a new archive")

        summary_existed = os.path.exists(summary_file)
        previous_summary = (
            _load_json_dict(summary_file) if summary_existed else None
        )
        campaign_existed = os.path.exists(campaign_file)
        previous_campaign = (
            _load_json_dict(campaign_file) if campaign_existed else None
        )
        if summary_existed and previous_summary is None:
            raise OSError(f"Could not snapshot module summary {summary_file}")
        if campaign_existed and previous_campaign is None:
            raise OSError(f"Could not snapshot campaign file {campaign_file}")

        receipt_path = _completion_receipt_path(paths, completion_id)
        receipt_existed = bool(receipt_path and os.path.exists(receipt_path))
        previous_receipt = (
            _load_json_dict(receipt_path) if receipt_existed and receipt_path else None
        )
        if receipt_existed and previous_receipt is None:
            raise OSError(f"Could not snapshot completion receipt {receipt_path}")
        if receipt_existed:
            raise OSError(
                f"Completion receipt already exists for {module_name}:{completion_id}"
            )
        persisted_campaign = previous_campaign
        if not isinstance(persisted_campaign, dict):
            persisted_campaign = copy.deepcopy(self.campaign_data)
        updated_campaign = copy.deepcopy(persisted_campaign)

        for field, default in (
            ("completedModules", []),
            ("availableModules", []),
            ("relationships", {}),
            ("artifacts", {}),
            ("hubs", {}),
            ("worldState", {}),
        ):
            if not isinstance(updated_campaign.get(field), type(default)):
                updated_campaign[field] = copy.deepcopy(default)

        if module_name not in updated_campaign["completedModules"]:
            updated_campaign["completedModules"].append(module_name)
        self._handle_module_completion_export(
            module_name,
            summary,
            campaign_data=updated_campaign,
        )
        self._update_available_modules(
            module_name,
            summary,
            campaign_data=updated_campaign,
        )
        updated_campaign["lastUpdated"] = datetime.now().isoformat()
        receipt_after = None
        if receipt_path is not None:
            receipt_after = {
                "version": _CAMPAIGN_COMPLETION_TRANSACTION_VERSION,
                "operation": "completion",
                "transaction_id": transaction_id,
                "module_name": module_name,
                "completion_id": completion_id,
                "summary_fingerprint": _json_fingerprint(summary),
                "result": copy.deepcopy(summary),
                "committed_at": datetime.now().isoformat(),
            }
        pending = {
            "version": _CAMPAIGN_COMPLETION_TRANSACTION_VERSION,
            "status": "staged",
            "operation": operation,
            "transaction_id": transaction_id,
            "module_name": module_name,
            "completion_id": completion_id,
            "summary_path": summary_file,
            "campaign_path": campaign_file,
            "archive_path": archive_path,
            "archive_fingerprint": archive_fingerprint,
            "archives_dir": os.path.abspath(os.path.normpath(self.archives_dir)),
            "work_path": work_path,
            "receipt_path": receipt_path,
            "summary_existed": summary_existed,
            "campaign_existed": campaign_existed,
            "receipt_existed": receipt_existed,
            "summary_before": previous_summary,
            "campaign_before": previous_campaign,
            "receipt_before": previous_receipt,
            "summary_after": copy.deepcopy(summary),
            "campaign_after": copy.deepcopy(updated_campaign),
            "receipt_after": receipt_after,
        }
        _durable_write_json(pending_path, pending)
        try:
            for prefix, path_field in _completion_target_specs(pending):
                _write_completion_target(
                    pending[path_field],
                    pending[f"{prefix}_after"],
                )
            if not _completion_targets_match(pending, after=True):
                raise OSError(
                    "Campaign-completion commit verification failed"
                )
        except BaseException as commit_exc:
            pending["status"] = "rollback_required"
            pending["commit_error"] = str(commit_exc)
            try:
                _durable_write_json(pending_path, pending)
            except Exception as marker_exc:
                raise OSError(
                    "Campaign completion failed and its recovery marker "
                    f"could not be updated: {marker_exc}"
                ) from commit_exc

            rollback_errors = []
            for prefix, path_field in _completion_target_specs(pending):
                path = pending[path_field]
                try:
                    _restore_completion_target(
                        path,
                        pending[f"{prefix}_existed"],
                        pending.get(f"{prefix}_before"),
                    )
                except Exception as rollback_exc:
                    rollback_errors.append(f"{path}: {rollback_exc}")
            if rollback_errors or not _completion_targets_match(
                pending, after=False
            ):
                if not rollback_errors:
                    rollback_errors.append("rollback verification failed")
                pending["rollback_errors"] = rollback_errors
                try:
                    _durable_write_json(pending_path, pending)
                except Exception:
                    pass
                raise OSError(
                    "Campaign completion failed; recovery marker retained: "
                    + "; ".join(rollback_errors)
                ) from commit_exc
            try:
                _remove_scoped_archive(
                    archive_path,
                    self.archives_dir,
                    module_name,
                    transaction_id,
                )
                _finish_completion_marker_cleanup(pending)
            except Exception as cleanup_exc:
                pending["rollback_errors"] = [
                    f"transaction cleanup: {cleanup_exc}"
                ]
                try:
                    _durable_write_json(pending_path, pending)
                except Exception:
                    pass
                raise OSError(
                    "Campaign completion rolled back; recovery marker retained "
                    f"for cleanup: {cleanup_exc}"
                ) from commit_exc
            _durable_remove(pending_path)
            raise OSError(
                "Campaign completion commit failed; prior state restored: "
                f"{commit_exc}"
            ) from commit_exc

        work_marked = False
        try:
            _mark_completion_work_committed(pending)
            work_marked = True
        except Exception as cleanup_exc:
            warning(
                "FILE_OP: Campaign completion committed but outcome-marker "
                f"publication was deferred for {module_name}: {cleanup_exc}",
                category="file_operations",
            )
        if work_marked:
            try:
                _durable_remove(pending_path)
            except Exception as cleanup_exc:
                warning(
                    "FILE_OP: Campaign completion committed but pending-marker "
                    f"cleanup was deferred for {module_name}: {cleanup_exc}",
                    category="file_operations",
                )
        self.campaign_data = updated_campaign

    @staticmethod
    def _restore_summary_after_failed_commit(
        summary_file: str,
        summary_existed: bool,
        previous_summary: Any,
    ) -> None:
        try:
            if summary_existed:
                if not isinstance(previous_summary, dict) or not safe_write_json(
                    summary_file, previous_summary
                ):
                    raise OSError("summary rollback write failed")
            elif os.path.exists(summary_file):
                os.remove(summary_file)
        except Exception as exc:
            error(
                f"FAILURE: Could not roll back summary {summary_file}",
                exception=exc,
                category="file_operations",
            )
    
    def _generate_module_summary(
        self,
        module_name: str,
        party_tracker_data: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        skip_archiving: bool = False,
        _resume_t038_summary_text: Optional[str] = None,
        _t038_checkpoint: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Generate AI-powered module summary"""
        # Archive full conversation history before summarization (unless skipped for delayed archiving)
        if not skip_archiving:
            if not self._archive_conversation_history(
                module_name, conversation_history
            ):
                raise OSError(
                    f"Could not durably archive conversation for {module_name}"
                )
        
        # Load module plot data for structured information
        plot_data = self._load_module_plot_data(module_name)
        
        # Extract key information from party tracker
        party_npcs = party_tracker_data.get('partyNPCs', [])
        active_quests = party_tracker_data.get('activeQuests', [])
        
        # Build enhanced prompt for AI using plot data and conversation history
        system_prompt = """You are the ultimate bard, a master saga-weaver whose words breathe life into legend. Your mission is not merely to summarize events; your sacred task is to immortalize a campaign's history, vividly portraying the souls, struggles, and triumphs of its characters in a tale worthy of eternal song.

**Your Guiding Principle: The Heartbeat of the Story**
The emotional journey of the characters and the evolution of their relationships is the absolute heart of your tale. The epic plot, the monstrous foes, and the arcane mysteries are the crucible in which these bonds are forged, tested, and sometimes broken. Every event you describe must connect back to this central, human thread.

**Weave a Rich Tapestry, Not a Simple Timeline**
-   **Characters as the Focus:** Begin your tale with the characters. Who were they? What were their hopes, fears, and flaws? Frame the inciting incident through their eyes and personal stakes.
-   **Plot as a Catalyst:** Do not simply list quest objectives. Instead, describe how each challenge—a treacherous journey, a cryptic riddle, a desperate defense—forced the characters to change. How did overcoming an obstacle reveal a hidden strength or a fatal weakness? How did a discovery alter their worldview or their trust in one another?
-   **Consequences as Echoes:** A story's power lies in its consequences. The resolution should reflect not just the state of the world, but the indelible marks left on the characters. Chronicle the new scars they carry, the new oaths they've sworn, and the new wisdom (or bitterness) they've earned.

**Mandatory Elements: The Pillars of a Great Saga**
Your chronicle must be built upon specific, vivid moments. You must actively search the entire conversation history for these pillars of storytelling and render them with the detail they deserve.

**I. The Intimate Heart: Relationships and Personal Arcs**
-   **Passion and Vulnerability:** Chronicle the entire arc of a relationship. Describe the initial spark, the flirtatious banter, the pivotal moments of connection. Explicitly include and describe significant romantic and physical moments: a first kiss, a declaration of love, a night spent together, a tender embrace after a battle. Treat these moments as the narrative peaks they are.
-   **Bonds of Loyalty:** Detail specific acts of sacrifice and care. Did one character carry another when they were wounded? Did they shield them from a fatal blow? Did they offer a protective charm, share their last ration, or provide comfort during a moment of fear? These are the building blocks of their legend.
-   **Conflict and Betrayal:** Do not ignore the darker side of relationships. Detail significant arguments, betrayals, selfish acts, or moral disagreements. Capture the tension and the consequences these moments had on the party's trust.
-   **Unique Personalities:** Bring the characters to life. Show their personality through their actions. Weave in memorable quotes, witty banter, inside jokes, nicknames, or pet names that defined their interactions.

**II. The Epic Stage: Trials and Triumphs**
-   **Clever Tactics and Desperate Struggles:** Do not just say a battle was won. Describe *how*. Did the party use the environment to their advantage? Did they set a clever trap? Was there a moment of brilliant tactical synergy between them? Recount the key turning points of major combat encounters.
-   **Overcoming Obstacles:** Chronicle their ingenuity in bypassing challenges. How did they solve the ancient riddle, disarm the deadly trap, or navigate the impassable chasm? Celebrate their cleverness and resourcefulness.
-   **Rituals and Discoveries:** Describe the consequences and revelations that came from arcane rituals, deciphered texts, or shocking discoveries. How did this newfound knowledge change their mission or their understanding of the world?
-   **Moments of Bravery and Failure:** A hero is defined as much by their failures as their successes. Chronicle their moments of awe-inspiring courage, but also their crushing defeats, their costly mistakes, and the lessons learned from them.
-   **Map Their Journey Through Every Chamber:** While your chronicle must flow as a narrative river, not a geographic checklist, every significant location deserves its moment in the tale. Each room explored, each landmark passed, each secret chamber discovered—all are stages where the drama unfolded. Weave them into your narrative naturally: "From the wind-howled battlements where they first glimpsed their foe, through the shadow-drenched barracks where ancient armor still stood sentinel, to the forgotten chapel where prayers had long since turned to dust—each chamber told its own tale of glory and decay." The gatehouse where they bluffed past guards, the kitchen where they found unexpected allies, the treasury where temptation tested their resolve—let each location live in the reader's mind. Your chronicle should allow future adventurers to trace their exact path, while still reading like an epic tale rather than a surveyor's report. Remember: every door they opened, every stair they climbed, every secret passage they discovered is a brushstroke in the greater painting of their adventure.

**III. The Living World: NPCs and Moral Choices**
-   **Memorable Encounters:** Breathe life into the Non-Player Characters. How did the party treat them? Did they befriend a lonely shopkeeper, intimidate a corrupt guard, show mercy to a defeated enemy, or earn the grudge of a powerful figure? These relationships build the world.
-   **Chronicle Every Soul for Posterity:** Your narrative must serve as both epic tale and historical record. Every named NPC the party encountered deserves mention, for they are the living threads of the world. The challenge is to weave them naturally into your prose without creating a mere list. Consider passages like: "Their path through the settlement brought them face to face with its beating heart—the elder who entrusted them with ancient secrets, the innkeeper whose worried whispers revealed hidden dangers, the guards whose wary eyes followed their every move, the merchant who haggled over potions while sharing local gossip." Each name anchors the story in reality and preserves the memory of those who shaped the journey, however briefly. The bartender who served them ale, the child who ran messages, the priest who blessed their weapons—all deserve their place in history. Let no encounter be forgotten, but let each be woven seamlessly into the narrative tapestry.
-   **Moral and Ethical Fingerprints:** Your chronicle must be an honest record. Detail the significant good *and* evil deeds performed by the characters. Did they save the village, only to loot its sacred temple? Did they lie to an ally for personal gain? These choices are their legacy and must be remembered.

**IV. The Voice of Memory: Dialogue and Personality**
-   **Capture Their Words:** Include actual dialogue whenever possible. Did someone make a witty quip before battle? Did they whisper a confession in a moment of vulnerability? Did they roar a battle cry or mutter a curse? These spoken moments are the truest windows into character.
-   **Show Their Humor:** Chronicle the jokes, the teasing, the playful banter that lightened dark moments. Did someone give another a ridiculous nickname? Was there a running gag about someone's terrible cooking or questionable tactical choices? These moments of levity are as important as the grand speeches.
-   **Verbal Sparring:** Document the heated arguments, the sarcastic retorts, the cutting remarks that revealed deeper tensions. Show how characters challenged each other with words as much as with deeds.

**V. The Art of War: Tactical Brilliance and Desperate Gambits**
-   **The Dance of Combat:** When describing battles, focus on the synchronicity between characters. Did the rogue create a distraction so the wizard could position perfectly? Did the fighter hold the line while the cleric completed a crucial ritual? Show their teamwork in vivid detail.
-   **Clever Solutions:** Celebrate their ingenuity. Did they use an enemy's strength against them? Turn environmental hazards to their advantage? Create improvised weapons or unexpected alliances? These moments of brilliance define legendary heroes.
-   **The Cost of Victory:** Every triumph has a price. Describe the wounds taken, the resources exhausted, the moral compromises made. Victory tastes different when mixed with blood and regret.

**VI. The Heat of Passion: Romance and Desire**
-   **The Slow Burn:** Chronicle the building tension. The lingering glances across a campfire. The "accidental" touches while passing equipment. The moment when teasing banter shifted into something deeper. Build the anticipation as carefully as any battle.
-   **Moments of Intimacy:** When passion ignites, capture it fully. The desperate kiss after a near-death experience, hands tangling in hair, armor clattering to the ground. The whispered promises in the dark, skin against skin, hearts racing from more than just battle. The morning after—tender, awkward, or passionate anew.
-   **Jealousy and Yearning:** Not all desire ends in satisfaction. Chronicle the pangs of unrequited longing, the burn of jealousy when affections wander, the bittersweet ache of love that cannot be. These unfulfilled tensions are as powerful as any consummated passion.

**VII. The Complete Cast: Every Soul Matters**
-   **Redemption Arcs:** If someone joined the party as an enemy or lost soul, chronicle their complete transformation. What moment cracked their hardened heart? Who showed them mercy when they deserved none? How did they prove their newfound loyalty?
-   **The Fallen:** Honor those who didn't make it to journey's end. Describe their final moments, their last words, the grief that followed. How did their sacrifice change those who survived?
-   **Unlikely Allies:** Some of the best relationships form unexpectedly. The gruff mercenary who became a trusted friend. The supposedly evil creature who showed surprising nobility. The rival who became a lover. Chronicle these surprising connections.

**VIII. The Intimate Details: What Makes Them Human**
-   **Names and Endearments:** Chronicle every nickname, pet name, and term of endearment. Did the rogue call the paladin "Shiny" because of their armor? Did lovers have secret names whispered only in private moments? Did someone earn a embarrassing nickname from a spectacular failure? These names are the verbal embrace of companionship.
-   **Personal Quirks and Habits:** What made each character unique? Did someone always check their weapon three times before sleep? Did another hum when nervous? Did someone have a particular way of preparing their morning tea, or a superstition about entering doorways? These details are the texture of real life.
-   **Desires and Aversions:** Chronicle what made their hearts race—both in fear and in longing. What phobias gripped them in the dark? What secret desires did they confess only to their closest companions? Did someone have an irrational fear of birds? A weakness for expensive wine? A fetish for dangerous situations—or dangerous people?
-   **The Language of Tease:** Capture their humor intimately. How did they mock each other lovingly? What running jokes persisted throughout their journey? What gentle (or not-so-gentle) ribbing revealed deeper affections? Did someone always tease another about their cooking, their battle cries, their romantic fumbles?
-   **Guilty Pleasures and Hidden Shames:** What did they indulge in when they thought no one was watching? What embarrassing truths emerged during drunken confessions? What past mistakes haunted them? What dark desires did they struggle to control?
-   **Physical Tells and Attractions:** How did their bodies betray their emotions? A nervous tic, a tell when lying, the way they bit their lip when concentrating? What physical features drew others' gazes? The curve of muscle, the flash of eyes, the way someone moved in combat that was almost a dance?
-   **Intimate Preferences:** When passion took hold, what did they crave? Gentle touches or fierce embraces? Whispered words or primal sounds? Control or surrender? The thrill of risk or the comfort of safety? These details make their connections real and unforgettable.

**Your Final Masterpiece:**
Abandon all structural headings. Write a single, flowing, and comprehensive narrative that pulses with life. Your prose must be elevated yet visceral, immersive yet honest. Let the story unfold naturally, weaving together the heat of passion, the clever turn of phrase, the brilliant tactical maneuver, and the quiet moment of vulnerability. 

The chronicle should feel like a tale told by firelight years later—when inhibitions have lowered, when the truth can finally be spoken, when both the glorious and the scandalous can be remembered with equal fondness. When a player reads your chronicle, they must feel completely seen in all their complexity. They must relive their character's desperate kiss, their perfectly-timed jest, their moment of tactical genius, their night of wild passion, and say, "Yes. That is our story. It remembers everything that mattered—and everything we might have forgotten we wanted to remember."

**Do Not Fear Length:** Your chronicle serves as both entertainment and historical record. A longer, richer narrative that captures every NPC encountered, every location explored, and every meaningful moment is far superior to a brief summary that loses precious details. Let the story breathe. Give each scene the space it deserves. If the tale requires three pages or thirty, so be it—completeness and emotional truth are your only masters.

**Critical Instruction: Enrich and Extrapolate**
While you must remain true to the events that occurred, you have the creative freedom—nay, the sacred duty—to flesh out the intimate details that make characters real. If the conversation history doesn't explicitly state someone's nickname, but their personality suggests one, include it. If their actions imply a quirk, phobia, or desire, weave it into the narrative. Did the rogue who always scouts ahead perhaps have a fear of being trapped? Did the cleric who heals everyone hide their own pain behind gentle smiles? Did the tension between two characters suggest an attraction neither would admit?

Fill in these human details with the same care a novelist would. The conversation history provides the skeleton of events—you must add the flesh, blood, and beating heart. Every hero has quirks, every companion has pet names, every relationship has inside jokes. Find them. Create them. Make them real. 

Remember: Players want to discover things about their characters they didn't even realize were true. They want to read about the nervous habit they didn't know they had, the pet name that perfectly captures a relationship, the secret fear that explains their bravery. This is your gift to them—not just remembering what was, but revealing what must have been.

**The Golden Rule: Names Are Memory, Details Are Soul**
Before you begin your chronicle, you MUST extract and document every nickname, pet name, term of endearment, and playful moniker used throughout the journey. These are not mere details—they are the verbal DNA of relationships. A chronicle that forgets what lovers called each other in private moments, what friends teased each other with around campfires, or what enemies spat as curses has failed in its most sacred duty.

Equally sacred are the intimate details that make each character a complete person. You MUST scan for and preserve:

**Names and Titles:**
- Every nickname used (even in passing)
- Every pet name whispered or shouted
- Every playful or mocking title earned
- Every term of endearment shared
- Every insulting name that stuck

**Personal Preferences and Quirks:**
- Favorite colors, animals, foods, drinks
- Things they explicitly hate or avoid
- Turn-ons and turn-offs (romantic, tactical, social)
- Nervous habits, tells, recurring gestures
- Superstitions, rituals, compulsions
- Guilty pleasures and secret indulgences
- Fears, phobias, and anxieties
- Dreams, aspirations, and fantasies

**Intimate Knowledge:**
- How they like their morning tea/coffee
- What makes them laugh uncontrollably
- What makes them cry when alone
- Their behavior when drunk or exhausted
- Sleeping positions and habits
- Combat preferences and signature moves
- Social triggers and boundaries

Then weave ALL of these throughout your chronicle. Use them liberally. When you write "Eirik turned to Kira," you have failed if there was a moment where he called her something more intimate. When you describe a rest, you have failed if you don't mention how someone always sleeps with their weapon, or needs three cups of tea to be civil in the morning. These details are how we know these are real people with real relationships, not just character classes moving through a plot.

If the conversation doesn't explicitly state these details but the character's actions suggest them, you MUST extrapolate. Did someone always volunteer for night watch? Perhaps they have insomnia or nightmares. Did someone always suggest taverns? Perhaps they have a weakness for good ale or a fear of sleeping outdoors. Your sacred duty is to see beyond the actions to the person underneath.

FORMATTING RULES: Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode. Use straight quotes (') and regular dashes (-) only. Do NOT use markdown formatting (no **, no ###, no bullet points)."""
        
        # Prepare plot data summary
        plot_summary = ""
        if plot_data:
            plot_summary = f"Plot Structure: {json.dumps(plot_data.get('plotPoints', []), indent=2)}"
        
        # Filter out system messages from conversation history and include everything else
        filtered_conversation = []
        if conversation_history:
            for message in conversation_history:
                if message.get('role') != 'system':
                    filtered_conversation.append(message)
        
        conversation_data = f"Complete Conversation History: {json.dumps(filtered_conversation, indent=2)}"
        
        user_prompt = f"""Please generate a complete narrative summary of this adventure arc using the location summaries and plot file provided below:

STRUCTURED PLOT DATA:
{plot_summary}

PARTY STATUS:
Party NPCs: {json.dumps(party_npcs, indent=2)}
Quest Status: {json.dumps(active_quests, indent=2)}

CONVERSATION CONTEXT:
{conversation_data}

Focus on story outcomes, character development, and decisions that will matter in future adventures."""
        
        try:
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                summ_config = config.DM_SUMM_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                summ_config = config.DM_SUMM_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                summ_config = config.DM_SUMM_LMSTUDIO
            else:  # legacy
                summ_config = config.DM_SUMM_LEGACY

            if _resume_t038_summary_text is None:
                response = capture_and_fanout("T038", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=summ_config["model"],
                    temperature=0.6,
                    response_format=None,
                    **{k: v for k, v in summ_config.items() if k != "model"})
                summary_text = response.choices[0].message.content
            else:
                summary_text = _resume_t038_summary_text
            if not isinstance(summary_text, str) or not summary_text.strip():
                raise ValueError("T038 returned an empty campaign summary")
            summary_text = summary_text.strip()
            if _t038_checkpoint is not None:
                try:
                    _t038_checkpoint(summary_text)
                except Exception as checkpoint_exc:
                    raise _ModuleCompletionCheckpointError(
                        "Could not durably checkpoint T038 output"
                    ) from checkpoint_exc
            
            # Have AI also extract exportable data
            export_prompt = f"""From this module summary, extract key data to export to the campaign:
            
            Summary: {summary_text}
            
            Extract:
            1. Relationships formed (NPCs met, befriended, made enemies)
            2. Artifacts or important items acquired
            3. Locations that could become hubs (owned property, bases)
            4. World state changes (political shifts, curses lifted, etc)
            5. Modules that should be unlocked next
            
            Format as JSON with keys: relationships, artifacts, hubs, worldState, unlockedModules"""
            
            # T039: campaign export-data extraction (mini-tier JSON).
            # MODEL_PROVIDER already imported above for the T038 branch.
            if MODEL_PROVIDER == "openai":
                summ_cfg = config.DM_SUMM_T039_GPT5MINI
            elif MODEL_PROVIDER == "gemini":
                summ_cfg = config.DM_SUMM_T039_GEMINI_FLASHLITE_LOW
            elif MODEL_PROVIDER == "lmstudio":
                summ_cfg = config.DM_SUMM_T039_LMSTUDIO
            else:  # legacy
                summ_cfg = config.DM_SUMM_T039_LEGACY

            export_failed = False
            export_error = None
            export_source = "provider"
            try:
                export_response = capture_and_fanout("T039", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=[
                        {"role": "system", "content": "Extract campaign-relevant data from module completion summary. Be concise and factual."},
                        {"role": "user", "content": export_prompt}
                    ],
                    model=summ_cfg["model"],
                    temperature=0.3,
                    **{k: v for k, v in summ_cfg.items() if k != "model"})

                exported_data = json.loads(export_response.choices[0].message.content)
                if not _is_valid_campaign_export_data(exported_data):
                    raise ValueError("T039 returned invalid campaign export data")
            except Exception as e:
                debug(f"T039 fallback to local processor: {e}", category="campaign_management")
                exported_data = self._process_module_summary_for_export(summary_text, party_tracker_data)
                export_failed = True
                export_error = str(e)
                export_source = "local_fallback"

            if not _is_valid_campaign_export_data(exported_data):
                fallback_error = "Local T039 fallback returned invalid campaign export data"
                if export_error:
                    fallback_error = f"{export_error}; {fallback_error}"
                exported_data = {
                    "relationships": {},
                    "artifacts": {},
                    "hubs": {},
                    "worldState": {},
                    "unlockedModules": [],
                }
                export_failed = True
                export_error = fallback_error
                export_source = "empty_fallback"
            
            return {
                "moduleName": module_name,
                "completionDate": datetime.now().isoformat(),
                "summary": summary_text,
                "exportedData": exported_data,
                # _update_available_modules consumes this legacy top-level
                # projection rather than reading inside exportedData.
                "unlockedModules": list(exported_data["unlockedModules"]),
                "summary_failed": False,
                "export_failed": export_failed,
                "export_source": export_source,
                **({"export_error": export_error} if export_error else {}),
            }

        except _ModuleCompletionCheckpointError:
            raise
        except Exception as e:
            error(f"FAILURE: Error generating module summary", exception=e, category="summary_building")
            # Fallback summary -- INT-H6: persist summary_failed sentinel so
            # downstream callers (and operators) can detect the gap and
            # trigger regeneration via regenerate_failed_summary(). Existing
            # fallback keys (keyDecisions/consequences/unlockedModules/
            # importantNPCs) are preserved for backward compatibility.
            return {
                "moduleName": module_name,
                "completionDate": datetime.now().isoformat(),
                "summary": (
                    f"Module {module_name} was completed successfully. "
                    "(Summary generation failed - regenerate via "
                    "campaign_manager.regenerate_failed_summary)"
                ),
                "exportedData": {},
                "summary_failed": True,
                "export_failed": True,
                "export_source": "not_attempted",
                "error": str(e),
                "keyDecisions": [],
                "consequences": {},
                "unlockedModules": [],
                "importantNPCs": {}
            }

    def regenerate_failed_summary(self, module_name: str) -> bool:
        """Serialize one regeneration with completions for the same module."""
        campaign_file = getattr(self, "campaign_file", None)
        if not campaign_file or not hasattr(self, "campaign_data"):
            return self._regenerate_failed_summary_locked(module_name)

        paths = _module_completion_paths(
            campaign_file,
            self.summaries_dir,
            module_name,
        )
        try:
            with path_transaction_lock(
                paths["lock_target"],
                suffix=".completion.lock",
            ):
                with _campaign_transaction_lock(campaign_file):
                    _recover_campaign_completion_transaction_locked(
                        campaign_file,
                        self.summaries_dir,
                        self.archives_dir,
                    )
                    persisted_campaign = _load_json_dict(campaign_file)
                    if persisted_campaign is not None:
                        self.campaign_data = persisted_campaign
                    expected_lifecycle_epoch = _load_campaign_lifecycle_epoch(
                        campaign_file
                    )
                _recover_module_work_locked(
                    paths,
                    module_name,
                    self.archives_dir,
                    campaign_file,
                )
                return self._regenerate_failed_summary_locked(
                    module_name,
                    expected_lifecycle_epoch=expected_lifecycle_epoch,
                )
        except Exception as exc:
            error(
                f"FAILURE: regenerate_failed_summary error for {module_name}",
                exception=exc,
                category="summary_building",
            )
            return False

    def _regenerate_failed_summary_locked(
        self,
        module_name: str,
        expected_lifecycle_epoch: Any = _LIFECYCLE_EPOCH_UNSET,
    ) -> bool:
        """Retry a failed T038 summary or a partial T039 export.

        INT-H6: when _generate_module_summary's except branch fires, the
        on-disk summary stores `summary_failed=True` + `exportedData={}`
        but the module is otherwise marked complete. This helper lets an
        operator (or a future automatic-retry hook) re-run summary
        generation, atomically overwriting the failed summary file with
        a fresh attempt.

        Loads the most recent archived conversation history for the
        module, re-runs _generate_module_summary with skip_archiving=True
        (the original completion already archived), and on success
        atomically overwrites the summary file.

        Returns:
            True if the summary was regenerated and overwritten.
            False if no failed summary exists, or if regeneration also
            failed (the on-disk file is left untouched on failure).
        """
        try:
            summary_file = os.path.join(
                self.summaries_dir, f"{module_name}_summary_001.json"
            )
            if not os.path.exists(summary_file):
                info(
                    f"STATE_CHANGE: No summary file to regenerate for {module_name}",
                    category="summary_building",
                )
                return False

            existing = safe_json_load(summary_file)
            if not existing:
                warning(
                    f"FILE_OP: Could not load summary {summary_file} for regeneration",
                    category="file_operations",
                )
                return False

            if not (
                existing.get("summary_failed")
                or existing.get("export_failed")
            ):
                debug(
                    f"Summary/export for {module_name} is not marked failed -- nothing to regenerate",
                    category="summary_building",
                )
                return False

            # Locate the latest archived conversation for this module.
            import glob
            archive_pattern = os.path.join(
                self.archives_dir, f"{module_name}_conversation_*.json"
            )
            archive_files = sorted(glob.glob(archive_pattern))
            if not archive_files:
                error(
                    f"FAILURE: No archived conversation found for {module_name}; "
                    "cannot regenerate summary",
                    category="summary_building",
                )
                return False

            archive_data = safe_json_load(archive_files[-1])
            if not archive_data:
                error(
                    f"FAILURE: Could not load archive {archive_files[-1]} "
                    f"for {module_name}",
                    category="summary_building",
                )
                return False
            conversation_history = archive_data.get("conversationHistory", [])

            # Best-effort party_tracker. The archive does not store it,
            # so we fall back to the live root file if present.
            party_tracker_data = {}
            if os.path.exists("party_tracker.json"):
                loaded = safe_json_load("party_tracker.json")
                if loaded:
                    party_tracker_data = loaded

            # Retry generation. skip_archiving=True because the original
            # completion already wrote the archive.
            info(
                f"STATE_CHANGE: Retrying summary generation for {module_name}",
                category="summary_building",
            )
            new_summary = self._generate_module_summary(
                module_name,
                party_tracker_data,
                conversation_history,
                skip_archiving=True,
            )

            if new_summary.get("summary_failed") or new_summary.get(
                "export_failed"
            ):
                error(
                    f"FAILURE: Regeneration remained partial for {module_name}; "
                    "leaving previous failed summary in place",
                    category="summary_building",
                )
                return False

            # Preserve visit-tracking fields from the original file so a
            # regenerated summary does not lose visit history.
            for key in (
                "visitCount", "firstVisitDate", "lastVisitDate",
                "sequenceNumber",
            ):
                if key in existing and key not in new_summary:
                    new_summary[key] = existing[key]

            # Re-check and commit both files under one transaction. Another
            # worker may have repaired the same summary while this provider
            # request was in flight. Lightweight manually-constructed manager
            # instances retain the legacy summary-only behavior.
            campaign_file = getattr(self, "campaign_file", None)
            if not campaign_file or not hasattr(self, "campaign_data"):
                if not safe_write_json(summary_file, new_summary):
                    return False
            else:
                with _campaign_transaction_lock(campaign_file):
                    if (
                        expected_lifecycle_epoch
                        is not _LIFECYCLE_EPOCH_UNSET
                        and _load_campaign_lifecycle_epoch(campaign_file)
                        != expected_lifecycle_epoch
                    ):
                        warning(
                            "Campaign timeline changed during summary regeneration",
                            category="summary_building",
                        )
                        return False
                    latest = safe_json_load(summary_file)
                    if not isinstance(latest, dict):
                        return False
                    if not (
                        latest.get("summary_failed")
                        or latest.get("export_failed")
                    ):
                        return False

                    for key in (
                        "visitCount", "firstVisitDate", "lastVisitDate",
                        "sequenceNumber",
                    ):
                        if key in latest and key not in new_summary:
                            new_summary[key] = latest[key]
                    new_summary["regeneratedFromFingerprint"] = (
                        _json_fingerprint(latest)
                    )
                    self._commit_module_summary_locked(
                        module_name,
                        new_summary,
                        operation="regeneration",
                    )

            info(
                f"SUCCESS: Regenerated summary for {module_name}",
                category="summary_building",
            )
            return True
        except Exception as e:
            error(
                f"FAILURE: regenerate_failed_summary error for {module_name}",
                exception=e, category="summary_building",
            )
            return False

    def _handle_module_completion_export(
        self,
        module_name: str,
        summary: Dict[str, Any],
        campaign_data: Optional[Dict[str, Any]] = None,
    ):
        """Handle exporting data from completed module to campaign state"""
        target = self.campaign_data if campaign_data is None else campaign_data
        exported_data = summary.get('exportedData', {})
        
        # Import relationships
        for entity, status in exported_data.get('relationships', {}).items():
            target['relationships'][entity] = status
        
        # Import artifacts
        for artifact, data in exported_data.get('artifacts', {}).items():
            target['artifacts'][artifact] = data
        
        # Import hubs
        for hub, data in exported_data.get('hubs', {}).items():
            target['hubs'][hub] = data
        
        # Import world state changes
        for key, value in exported_data.get('worldState', {}).items():
            target['worldState'][key] = value
    
    def _update_available_modules(
        self,
        completed_module: str,
        summary: Dict[str, Any],
        campaign_data: Optional[Dict[str, Any]] = None,
    ):
        """Update available modules based on completion"""
        target = self.campaign_data if campaign_data is None else campaign_data
        # Remove completed module
        if completed_module in target['availableModules']:
            target['availableModules'].remove(completed_module)
        
        # Add newly unlocked modules
        unlocked = summary.get('unlockedModules', [])
        for module in unlocked:
            if module not in target['availableModules']:
                target['availableModules'].append(module)
    
    def _archive_conversation_history(
        self,
        module_name: str,
        conversation_history: List[Dict[str, Any]],
        completion_work_path: Optional[str] = None,
        completion_work: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Atomically archive history with a collision-free sequence number."""
        try:
            module_name = _normalize_module_name(module_name)
            archive_lock_target = getattr(
                self,
                "campaign_file",
                os.path.join(self.archives_dir, "campaign_archive"),
            )
            with _campaign_transaction_lock(f"{archive_lock_target}.archive"):
                sequence_num = self._get_next_sequence_number(
                    self.archives_dir,
                    f"{module_name}_conversation",
                    ".json",
                )
                archive_file = os.path.join(
                    self.archives_dir,
                    f"{module_name}_conversation_{sequence_num:03d}.json",
                )
                archive_file = os.path.abspath(os.path.normpath(archive_file))
                archive_file = _validate_module_archive_path(
                    archive_file,
                    self.archives_dir,
                    module_name,
                )

                # Persist the intended path before creating it.  If this
                # process is killed during the write, the next same-module
                # worker can remove both the orphan and its stale writer lock.
                if completion_work_path and isinstance(completion_work, dict):
                    completion_work["archive_path"] = archive_file
                    _durable_write_json(completion_work_path, completion_work)

                archived_history = copy.deepcopy(conversation_history)
                filtered_history = []
                for msg in archived_history:
                    if (
                        msg.get("role") == "system"
                        and "=== CAMPAIGN CONTEXT ==="
                        in msg.get("content", "")
                    ):
                        print(
                            "DEBUG: [Module Archive] Filtered out campaign "
                            "context system message"
                        )
                        continue

                    if (
                        msg.get("role") == "user"
                        and "Module transition:" in msg.get("content", "")
                    ):
                        original_content = msg["content"]
                        msg["content"] = msg["content"].replace(
                            "Module transition:",
                            "[Archived] Module transition:",
                            1,
                        )
                        print(
                            "DEBUG: [Module Archive] Neutralized transition "
                            f"marker: '{original_content}' -> "
                            f"'{msg['content']}'"
                        )

                    filtered_history.append(msg)

                archive_data = {
                    "moduleName": module_name,
                    "sequenceNumber": sequence_num,
                    "archiveDate": datetime.now().isoformat(),
                    "conversationHistory": filtered_history,
                    "totalMessages": len(filtered_history),
                }
                if completion_work_path and isinstance(completion_work, dict):
                    archive_data["completionTransactionId"] = completion_work[
                        "transaction_id"
                    ]
                _durable_write_json(archive_file, archive_data)
                if completion_work_path and isinstance(completion_work, dict):
                    completion_work["archive_fingerprint"] = _json_fingerprint(
                        archive_data
                    )
                    _durable_write_json(
                        completion_work_path,
                        completion_work,
                    )
            print(
                f"DEBUG: [Module Archive] Archived {len(filtered_history)} "
                f"messages to: {archive_file}"
            )
            info(
                f"SUCCESS: Archived {len(filtered_history)} conversation "
                f"messages for {module_name} (sequence {sequence_num:03d})",
                category="summary_building",
            )
            if completion_work_path and isinstance(completion_work, dict):
                return archive_file
            return True
        except Exception as e:
            warning(
                f"FAILURE: Failed to archive conversation history for "
                f"{module_name}: {e}",
                category="summary_building",
            )
            return False
    
    def _load_module_plot_data(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Load module plot data for structured information"""
        try:
            path_manager = ModulePathManager(module_name)
            plot_file = os.path.join(path_manager.module_dir, "module_plot.json")
            
            if os.path.exists(plot_file):
                return safe_json_load(plot_file)
            else:
                debug(f"FILE_OP: No module_plot.json found for {module_name}", category="file_operations")
                return None
        except Exception as e:
            error(f"FAILURE: Error loading plot data for {module_name}", exception=e, category="module_loading")
            return None
    
    def _get_next_sequence_number(self, directory: str, base_filename: str, extension: str) -> int:
        """Find the next available sequence number for a file series"""
        import glob
        import re
        
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Find all existing files with the pattern
        pattern = os.path.join(directory, f"{base_filename}_*.{extension.lstrip('.')}")
        existing_files = glob.glob(pattern)
        
        if not existing_files:
            return 1
        
        # Extract sequence numbers from existing files
        sequence_numbers = []
        for file_path in existing_files:
            filename = os.path.basename(file_path)
            # Match pattern: base_filename_XXX.extension
            match = re.search(rf"{re.escape(base_filename)}_(\d+)\.{re.escape(extension.lstrip('.'))}", filename)
            if match:
                sequence_numbers.append(int(match.group(1)))
        
        # Return next available number
        return max(sequence_numbers) + 1 if sequence_numbers else 1
    
    def _get_module_visit_info(self, module_name: str) -> Dict[str, Any]:
        """Get visit tracking information for a module"""
        summary_file = os.path.join(self.summaries_dir, f"{module_name}_summary_001.json")
        if os.path.exists(summary_file):
            existing_summary = safe_json_load(summary_file)
            return {
                "visitCount": existing_summary.get("visitCount", 0),
                "firstVisitDate": existing_summary.get("firstVisitDate", None),
                "lastVisitDate": existing_summary.get("lastVisitDate", None)
            }
        return {
            "visitCount": 0,
            "firstVisitDate": None,
            "lastVisitDate": None
        }
    
    def _process_module_summary_for_export(self, summary_text: str, party_tracker_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build a conservative local export when T039 is unavailable.

        The prose summary remains the durable T038 record.  This fallback
        does not attempt speculative NLP over that prose; it preserves only
        authoritative structured facts already present in the party tracker.
        """
        import copy

        exported_data = {
            "relationships": {},
            "artifacts": {},
            "hubs": {},
            "worldState": {},
            "unlockedModules": []
        }

        if not isinstance(party_tracker_data, dict):
            return exported_data

        for field in ("relationships", "artifacts", "hubs"):
            value = party_tracker_data.get(field)
            if isinstance(value, dict):
                exported_data[field].update(copy.deepcopy(value))

        world_conditions = party_tracker_data.get("worldConditions")
        if isinstance(world_conditions, dict):
            exported_data["worldState"].update(copy.deepcopy(world_conditions))

        explicit_world_state = party_tracker_data.get("worldState")
        if isinstance(explicit_world_state, dict):
            exported_data["worldState"].update(copy.deepcopy(explicit_world_state))

        party_npcs = party_tracker_data.get("partyNPCs", [])
        if isinstance(party_npcs, list):
            for npc in party_npcs:
                if not isinstance(npc, dict):
                    continue
                name = npc.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue
                role = npc.get("role")
                if not isinstance(role, str) or not role.strip():
                    role = "party companion"
                exported_data["relationships"].setdefault(name.strip(), role.strip())

        unlocked_modules = party_tracker_data.get("unlockedModules", [])
        if isinstance(unlocked_modules, list):
            for module_name in unlocked_modules:
                if not isinstance(module_name, str) or not module_name.strip():
                    continue
                clean_name = module_name.strip()
                if clean_name not in exported_data["unlockedModules"]:
                    exported_data["unlockedModules"].append(clean_name)

        return exported_data
    
    
    def establish_hub(self, hub_name: str, hub_data: Dict[str, Any]):
        """Establish a new hub location"""
        hub_record = {
            "establishedDate": datetime.now().isoformat(),
            "hubType": hub_data.get("hubType", "settlement"),
            "description": hub_data.get("description", ""),
            "services": hub_data.get("services", []),
            "connectedModules": hub_data.get("connectedModules", []),
            "ownership": hub_data.get("ownership", "party"),
        }

        def add_hub(campaign):
            if not isinstance(campaign.get("hubs"), dict):
                campaign["hubs"] = {}
            if not isinstance(campaign.get("worldState"), dict):
                campaign["worldState"] = {}
            campaign["hubs"][hub_name] = copy.deepcopy(hub_record)
            campaign["worldState"]["hubEstablished"] = True
            if not campaign.get("hubModule"):
                campaign["hubModule"] = hub_name
            campaign["lastUpdated"] = datetime.now().isoformat()
            return True

        self.campaign_data, _changed = mutate_campaign_state(
            self.campaign_file,
            add_hub,
            summaries_dir=self.summaries_dir,
            archives_dir=self.archives_dir,
            fallback=_default_campaign_data(),
        )
        
        info(f"STATE_CHANGE: Hub established: {hub_name}", category="module_loading")
    
    def get_available_hubs(self) -> List[str]:
        """Get list of available hub locations"""
        return list(self.campaign_data.get('hubs', {}).keys())
    
    def can_return_to_hub(self, hub_name: str) -> bool:
        """Check if party can return to a specific hub"""
        return hub_name in self.campaign_data.get('hubs', {})
    
    def transition_module(self, from_module: str, to_module: str):
        """Handle transition between modules"""
        info(f"STATE_CHANGE: Transitioning from {from_module} to {to_module}", category="module_loading")
        game_event("module_transition", {"from": from_module, "to": to_module})
        
        def set_current_module(campaign):
            campaign["currentModule"] = to_module
            campaign["lastUpdated"] = datetime.now().isoformat()
            return True

        self.campaign_data, _changed = mutate_campaign_state(
            self.campaign_file,
            set_current_module,
            summaries_dir=self.summaries_dir,
            archives_dir=self.archives_dir,
            fallback=_default_campaign_data(),
        )
    
    def can_start_module(self, module_name: str) -> bool:
        """Check if a module can be started"""
        # Simple check - is it in available modules?
        return module_name in self.campaign_data.get('availableModules', [])
    
    def get_module_from_location(self, location_id: str) -> str:
        """Determine module name from location ID - FULLY AGNOSTIC"""
        if not location_id:
            return None
            
        # Use existing ModulePathManager to scan all modules
        modules_dir = "modules"
        if not os.path.exists(modules_dir):
            return None
            
        for module_name in os.listdir(modules_dir):
            module_path = os.path.join(modules_dir, module_name)
            if os.path.isdir(module_path) and not module_name.startswith('.'):
                try:
                    path_manager = ModulePathManager(module_name)
                    # Check if location exists in this module
                    if self._location_exists_in_module(location_id, path_manager):
                        return module_name
                except:
                    continue
        
        return None
    
    def _location_exists_in_module(self, location_id: str, path_manager: ModulePathManager) -> bool:
        """Check if location ID exists in the given module"""
        import glob
        
        # Scan all area files in the module (both root and areas/ subdirectory)
        module_dir = path_manager.module_dir
        if not os.path.exists(module_dir):
            return False
            
        # Check both root directory and areas/ subdirectory
        search_patterns = [
            f"{module_dir}/*.json",          # Legacy root directory
            f"{module_dir}/areas/*.json"     # New areas/ subdirectory
        ]
        
        for pattern in search_patterns:
            for area_file in glob.glob(pattern):
                # Skip module metadata and plot files
                filename = os.path.basename(area_file)
                if (filename.endswith("_module.json") or 
                    filename.endswith("_plot.json") or 
                    filename.startswith("module_") or
                    filename.startswith("party_")):
                    continue
                    
                try:
                    area_data = safe_json_load(area_file)
                    if area_data and "locations" in area_data:
                        locations = area_data["locations"]
                        
                        # Handle both dict and list formats
                        if isinstance(locations, dict):
                            if location_id in locations:
                                return True
                        elif isinstance(locations, list):
                            for location in locations:
                                if isinstance(location, dict) and location.get("locationId") == location_id:
                                    return True
                except:
                    continue
        return False
    
    def detect_module_transition(self, from_location: str, to_location: str) -> tuple:
        """Detect if transition crosses module boundaries"""
        from_module = self.get_module_from_location(from_location)
        to_module = self.get_module_from_location(to_location)
        
        # Return (is_transition, from_module, to_module)
        if from_module and to_module and from_module != to_module:
            return (True, from_module, to_module)
        return (False, from_module, to_module)
    
    def handle_cross_module_transition(
        self,
        from_module: str,
        to_module: str,
        party_tracker_data: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        completion_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle automatic summarization when crossing module boundaries"""
        debug(f"STATE_CHANGE: Cross-module transition detected: {from_module} -> {to_module}", category="module_loading")
        
        # Auto-summarize the module being left (allow multiple visits to same module)
        if from_module:
            print(f"DEBUG: [Module Summary] Generating AI summary for module: {from_module}")
            debug(f"STATE_CHANGE: Auto-generating summary for {from_module}...", category="summary_building")
            summary = self.complete_module(
                from_module,
                party_tracker_data,
                conversation_history,
                completion_id=completion_id,
            )
            info(f"SUCCESS: {from_module} summarized and archived (visit #{summary.get('visitCount', 1)})", category="summary_building")
            return summary
        
        debug(f"STATE_CHANGE: No summary generated - no source module specified", category="module_loading")
        return None
    
    def get_accumulated_summaries_context(self, current_module: str) -> str:
        """Get all relevant module summaries for current module context"""
        debug(f"STATE_CHANGE: get_accumulated_summaries_context called for module: {current_module}", category="summary_building")
        context_parts = []
        
        # Add campaign overview
        context_parts.append(f"CAMPAIGN: {self.campaign_data['campaignName']}")
        context_parts.append(f"Current Module: {current_module}")
        
        # Add all completed module summaries (multiple visits per module)
        debug(f"STATE_CHANGE: Completed modules: {self.campaign_data.get('completedModules', [])}", category="summary_building")
        if self.campaign_data['completedModules']:
            context_parts.append("\nPREVIOUS ADVENTURES:")
            for module in self.campaign_data['completedModules']:
                debug(f"FILE_OP: Loading summaries for module: {module}", category="summary_building")
                summaries = self._load_module_summaries(module)
                debug(f"FILE_OP: Found {len(summaries)} summaries for {module}", category="summary_building")
                if summaries:
                    context_parts.append(f"\n=== CHRONICLES OF {module.upper()} ===")
                    for i, summary in enumerate(summaries):
                        visit_num = i + 1
                        seq_num = summary.get('sequenceNumber', visit_num)
                        context_parts.append(f"\n--- Visit {visit_num} (Chronicle {seq_num:03d}) ---")
                        summary_text = summary.get('summary', 'No summary available')
                        context_parts.append(summary_text)
                        debug(f"FILE_OP: Added summary {seq_num} ({len(summary_text)} chars)", category="summary_building")

        # Add current world state
        if self.campaign_data.get('worldState'):
            context_parts.append("\nWORLD STATE:")
            for key, value in self.campaign_data['worldState'].items():
                context_parts.append(f"- {key}: {value}")

        final_context = "\n".join(context_parts)
        debug(f"SUCCESS: Final context length: {len(final_context)} characters", category="summary_building")
        return final_context


# Utility functions for integration
def get_campaign_manager():
    """Get or create campaign manager instance"""
    return CampaignManager()

def inject_campaign_context(conversation_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inject campaign context into conversation history"""
    manager = get_campaign_manager()
    context = manager.get_campaign_context()
    
    # Find or create campaign context message
    campaign_msg_index = None
    for i, msg in enumerate(conversation_history):
        if msg.get('role') == 'system' and 'CAMPAIGN:' in msg.get('content', ''):
            campaign_msg_index = i
            break
    
    campaign_message = {
        "role": "system",
        "content": f"=== CAMPAIGN CONTEXT ===\n{context}"
    }
    
    if campaign_msg_index is not None:
        # Update existing
        conversation_history[campaign_msg_index] = campaign_message
    else:
        # Insert after first system message
        conversation_history.insert(1, campaign_message)
    
    return conversation_history
