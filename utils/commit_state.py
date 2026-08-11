"""Commit manifest + rollback helpers for multi-file module refresh durability."""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from utils.encoding_utils import safe_json_dump, safe_json_load

MODULES_DIR = "modules"
COMMIT_STATE_FILE = os.path.join(MODULES_DIR, "commit_state.json")
BACKUP_ROOT = os.path.join(MODULES_DIR, ".commit_backups")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _should_track_json(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    first_component = rel.split("/", 1)[0]
    # Campaign continuity has its own lock/WAL/receipt/lifecycle protocol.
    # Module-refresh rollback must never snapshot or restore that independent
    # timeline, including hidden intent/epoch/sequence metadata.
    if rel == "campaign.json" or first_component.startswith(".campaign.json"):
        return False
    if rel.startswith("campaign_archives/"):
        return False
    if rel.startswith("campaign_summaries/"):
        return False
    if rel.startswith("conversation_history/"):
        return False
    if first_component in {
        ".commit_backups",
        ".module_transactions",
        ".publication_transactions",
        ".module_orphan_quarantine",
        ".runtime_quarantine",
    }:
        return False
    if rel == "commit_state.json":
        return False
    return rel.endswith(".json")


def _list_tracked_module_json_files() -> List[str]:
    files: List[str] = []
    if not os.path.isdir(MODULES_DIR):
        return files
    for root, _dirs, names in os.walk(MODULES_DIR):
        for name in names:
            abs_path = os.path.join(root, name)
            rel_path = os.path.relpath(abs_path, MODULES_DIR).replace("\\", "/")
            if _should_track_json(rel_path):
                files.append(rel_path)
    files.sort()
    return files


def _sanitize_manifest_pre_files(pre_files: object) -> List[str]:
    """Constrain legacy manifest entries before delete/restore decisions."""
    if not isinstance(pre_files, list):
        raise OSError("Invalid refresh commit pre_files manifest")
    sanitized = set()
    for candidate in pre_files:
        if not isinstance(candidate, str):
            raise OSError("Invalid refresh commit path entry")
        rel = candidate.replace("\\", "/")
        if (
            not rel
            or rel.startswith("/")
            or re.match(r"^[A-Za-z]:", rel)
        ):
            raise OSError("Refresh commit path must be relative")
        parts = rel.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise OSError("Refresh commit path contains traversal")
        normalized = "/".join(parts)
        # Reapply current ownership rules to manifests written by older code;
        # this is what prevents legacy backups from restoring campaign WAL,
        # receipts, lifecycle epochs, or campaign.json itself.
        if _should_track_json(normalized):
            sanitized.add(normalized)
    return sorted(sanitized)


def _constrained_backup_dir(backup_dir: object) -> str:
    if not isinstance(backup_dir, str) or not backup_dir:
        raise OSError("Invalid refresh commit backup directory")
    canonical_root = os.path.realpath(BACKUP_ROOT)
    canonical_backup = os.path.realpath(backup_dir)
    try:
        within_root = (
            os.path.commonpath((canonical_root, canonical_backup))
            == canonical_root
        )
    except ValueError as exc:
        raise OSError("Refresh backup is outside backup root") from exc
    if not within_root or canonical_backup == canonical_root:
        raise OSError("Refresh backup is outside backup root")
    return canonical_backup


def begin_refresh_commit() -> Dict[str, object]:
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    commit_id = str(uuid.uuid4())
    backup_dir = os.path.join(BACKUP_ROOT, commit_id)
    os.makedirs(backup_dir, exist_ok=True)

    pre_files = _list_tracked_module_json_files()
    for rel_path in pre_files:
        src = os.path.join(MODULES_DIR, rel_path.replace("/", os.sep))
        dst = os.path.join(backup_dir, rel_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    state = {
        "schema_version": 1,
        "commit_id": commit_id,
        "phase": "prepare",
        "started_at": _utc_now(),
        "backup_dir": backup_dir.replace("\\", "/"),
        "pre_files": pre_files,
        "updated_at": _utc_now(),
    }
    safe_json_dump(state, COMMIT_STATE_FILE)
    return state


def mark_commit_phase(phase: str) -> None:
    state = safe_json_load(COMMIT_STATE_FILE) or {}
    if not isinstance(state, dict):
        return
    state["phase"] = phase
    state["updated_at"] = _utc_now()
    safe_json_dump(state, COMMIT_STATE_FILE)


def complete_refresh_commit() -> None:
    state = safe_json_load(COMMIT_STATE_FILE) or {}
    if not isinstance(state, dict):
        return
    state["phase"] = "complete"
    state["completed_at"] = _utc_now()
    state["updated_at"] = _utc_now()
    safe_json_dump(state, COMMIT_STATE_FILE)


def _restore_from_backup(backup_dir: str, pre_files: List[str]) -> List[str]:
    restored: List[str] = []
    pre_files = _sanitize_manifest_pre_files(pre_files)
    current_files = set(_list_tracked_module_json_files())
    previous_files = set(pre_files)

    # Remove newly-created tracked files that didn't exist pre-refresh.
    for extra in sorted(current_files - previous_files):
        try:
            os.remove(os.path.join(MODULES_DIR, extra.replace("/", os.sep)))
            restored.append(f"deleted:modules/{extra}")
        except FileNotFoundError:
            pass

    # Restore each tracked pre-refresh file from backup.
    for rel_path in pre_files:
        src = os.path.join(backup_dir, rel_path.replace("/", os.sep))
        dst = os.path.join(MODULES_DIR, rel_path.replace("/", os.sep))
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            restored.append(f"restored:modules/{rel_path}")
    return restored


def recover_incomplete_refresh_commit() -> Tuple[bool, Dict[str, object]]:
    state = safe_json_load(COMMIT_STATE_FILE)
    if not isinstance(state, dict):
        return False, {"status": "no_manifest"}

    phase = state.get("phase")
    if phase in {"complete", "rolled_back"}:
        return False, {"status": "already_complete"}

    backup_dir = _constrained_backup_dir(state.get("backup_dir"))
    pre_files = _sanitize_manifest_pre_files(state.get("pre_files", []))
    if not os.path.isdir(backup_dir):
        state["phase"] = "rolled_back"
        state["rolled_back_at"] = _utc_now()
        state["rollback_warning"] = "backup_missing"
        safe_json_dump(state, COMMIT_STATE_FILE)
        return True, {"status": "rolled_back_without_backup"}

    restored = _restore_from_backup(backup_dir, pre_files)
    state["phase"] = "rolled_back"
    state["rolled_back_at"] = _utc_now()
    state["restored_files"] = restored
    safe_json_dump(state, COMMIT_STATE_FILE)
    return True, {"status": "rolled_back", "restored_files": restored}
