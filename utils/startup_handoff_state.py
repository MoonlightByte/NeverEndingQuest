"""Startup handoff state management with lease-based exactly-once kickoff semantics."""

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from utils.encoding_utils import safe_json_load

STATE_FILE = "modules/conversation_history/startup_state.json"
LOCK_FILE = "modules/conversation_history/startup_state.lock"
LOCK_STALE_SECONDS = 120


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _default_state() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "state_version": 0,
        "status": "none",
        "startup_attempt_id": str(uuid.uuid4()),
        "lease_owner": "",
        "lease_expires_at": "",
        "attempt_count": 0,
        "forced_recovery_used": False,
        "last_error": "",
        "updated_at": _iso(_now_utc()),
    }


def _ensure_parent_dirs() -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    _ensure_parent_dirs()
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, separators=(",", ": "))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _clear_stale_lock_if_needed() -> None:
    try:
        stat = os.stat(LOCK_FILE)
    except FileNotFoundError:
        return

    lock_is_old = (time.time() - stat.st_mtime) > LOCK_STALE_SECONDS
    pid = None
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as handle:
            raw = handle.read().strip()
            pid = int(raw) if raw else None
    except Exception:
        pid = None

    pid_dead = pid is not None and not _is_pid_alive(pid)
    # Never reclaim a just-created empty lock file; only reclaim old/dead locks.
    if (pid_dead and lock_is_old) or (pid is None and lock_is_old):
        try:
            os.remove(LOCK_FILE)
        except FileNotFoundError:
            pass


def _try_acquire_lock(max_wait_seconds: float = 5.0, poll_seconds: float = 0.05) -> bool:
    _ensure_parent_dirs()
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        _clear_stale_lock_if_needed()
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(poll_seconds)
    return False


def _release_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def load_state() -> Dict[str, Any]:
    try:
        raw = safe_json_load(STATE_FILE)
    except Exception:
        # Corrupt state file: reset to safe defaults with a new attempt id.
        state = _default_state()
        _atomic_write_json(STATE_FILE, state)
        return state
    if not raw or not isinstance(raw, dict):
        return _default_state()

    state = _default_state()
    state.update(raw)
    return state


def save_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state["state_version"] = int(state.get("state_version", 0)) + 1
    state["updated_at"] = _iso(_now_utc())
    _atomic_write_json(STATE_FILE, state)
    return state


def sync_wizard_completion(has_character_data: bool) -> Dict[str, Any]:
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        if has_character_data and state.get("status") == "none":
            state["status"] = "wizard_complete"
            save_state(state)
            return {"status": "updated", "state": state}
        return {"status": "unchanged", "state": state}
    finally:
        _release_lock()


def mark_wizard_complete() -> Dict[str, Any]:
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        state["status"] = "wizard_complete"
        state["last_error"] = ""
        save_state(state)
        return {"status": "updated", "state": state}
    finally:
        _release_lock()


def _is_lease_active(state: Dict[str, Any]) -> bool:
    lease_expires_at = state.get("lease_expires_at")
    if not lease_expires_at:
        return False
    try:
        lease_time = datetime.fromisoformat(lease_expires_at)
    except ValueError:
        return False
    return lease_time > _now_utc()


def get_state_snapshot() -> Dict[str, Any]:
    """Return current startup state without mutating it."""
    return load_state()


def is_kickoff_claim_still_active(startup_attempt_id: str, lease_owner: str) -> bool:
    state = load_state()
    if state.get("status") not in {"kickoff_started", "kickoff_processing"}:
        return False
    if state.get("startup_attempt_id") != startup_attempt_id:
        return False
    if state.get("lease_owner") != lease_owner:
        return False
    return _is_lease_active(state)


def is_kickoff_currently_in_progress() -> bool:
    state = load_state()
    return state.get("status") in {"kickoff_started", "kickoff_processing"} and _is_lease_active(state)


def renew_kickoff_lease(startup_attempt_id: str, lease_owner: str, lease_seconds: int = 900) -> Dict[str, Any]:
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        if (
            state.get("status") not in {"kickoff_started", "kickoff_processing"}
            or state.get("startup_attempt_id") != startup_attempt_id
            or state.get("lease_owner") != lease_owner
        ):
            return {"status": "stale", "state": state}
        state["lease_expires_at"] = _iso(_now_utc() + timedelta(seconds=lease_seconds))
        save_state(state)
        return {"status": "updated", "state": state}
    finally:
        _release_lock()


def claim_kickoff_lease(source: str, lease_seconds: int = 180) -> Dict[str, Any]:
    """Attempt CAS-style transition to kickoff_started."""
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        status = state.get("status", "none")

        if status == "kickoff_done":
            return {"status": "already_done", "state": state}

        if status not in {"wizard_complete", "kickoff_started", "kickoff_processing", "kickoff_failed"}:
            return {"status": "not_ready", "state": state}

        if status in {"kickoff_started", "kickoff_processing"} and _is_lease_active(state):
            return {"status": "lease_held", "state": state}

        if status == "kickoff_failed":
            state["startup_attempt_id"] = str(uuid.uuid4())
            state["forced_recovery_used"] = False

        lease_owner = str(uuid.uuid4())
        state["status"] = "kickoff_started"
        state["lease_owner"] = lease_owner
        state["lease_expires_at"] = _iso(_now_utc() + timedelta(seconds=lease_seconds))
        state["attempt_count"] = int(state.get("attempt_count", 0)) + 1
        state["last_error"] = ""
        state["last_source"] = source
        save_state(state)

        return {
            "status": "claimed",
            "state": state,
            "startup_attempt_id": state["startup_attempt_id"],
            "lease_owner": lease_owner,
        }
    finally:
        _release_lock()


def mark_kickoff_done(startup_attempt_id: str, lease_owner: str) -> Dict[str, Any]:
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        if (
            state.get("status") not in {"kickoff_started", "kickoff_processing"}
            or state.get("startup_attempt_id") != startup_attempt_id
            or state.get("lease_owner") != lease_owner
        ):
            return {"status": "stale", "state": state}

        state["status"] = "kickoff_done"
        state["lease_owner"] = ""
        state["lease_expires_at"] = ""
        state["last_error"] = ""
        save_state(state)
        return {"status": "updated", "state": state}
    finally:
        _release_lock()


def mark_kickoff_failed(startup_attempt_id: str, lease_owner: str, error_text: str) -> Dict[str, Any]:
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        if (
            state.get("status") not in {"kickoff_started", "kickoff_processing"}
            or state.get("startup_attempt_id") != startup_attempt_id
            or state.get("lease_owner") != lease_owner
        ):
            return {"status": "stale", "state": state}

        state["status"] = "kickoff_failed"
        state["lease_owner"] = ""
        state["lease_expires_at"] = ""
        state["last_error"] = (error_text or "")[:500]
        save_state(state)
        return {"status": "updated", "state": state}
    finally:
        _release_lock()


def try_consume_forced_recovery(startup_attempt_id: str) -> Dict[str, Any]:
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        if state.get("startup_attempt_id") != startup_attempt_id:
            return {"status": "stale", "state": state}
        if state.get("forced_recovery_used"):
            return {"status": "already_used", "state": state}
        state["forced_recovery_used"] = True
        save_state(state)
        return {"status": "consumed", "state": state}
    finally:
        _release_lock()


def issue_new_attempt_id() -> Dict[str, Any]:
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        state["startup_attempt_id"] = str(uuid.uuid4())
        state["status"] = "wizard_complete"
        state["lease_owner"] = ""
        state["lease_expires_at"] = ""
        state["forced_recovery_used"] = False
        state["last_error"] = ""
        save_state(state)
        return {"status": "updated", "state": state}
    finally:
        _release_lock()


def prepare_manual_recovery_state() -> Dict[str, Any]:
    """Atomically decide/prepare state for manual startup recovery."""
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        status = state.get("status")
        if status == "kickoff_done":
            return {"status": "already_ready", "state": state}
        if status in {"kickoff_started", "kickoff_processing"}:
            if _is_lease_active(state):
                return {"status": "in_progress", "state": state}
            # Expired stale lease: roll forward to a fresh recoverable attempt.
            state["startup_attempt_id"] = str(uuid.uuid4())
            state["status"] = "wizard_complete"
            state["lease_owner"] = ""
            state["lease_expires_at"] = ""
            state["forced_recovery_used"] = False
            state["last_error"] = "stale_kickoff_recovery"
            save_state(state)
            return {"status": "recoverable", "state": state}
        if status in {"kickoff_failed", "wizard_complete"}:
            return {"status": "recoverable", "state": state}
        return {"status": "not_recoverable", "state": state}
    finally:
        _release_lock()


def lock_kickoff_processing(startup_attempt_id: str, lease_owner: str, lease_seconds: int = 3600) -> Dict[str, Any]:
    """Atomically transition kickoff into processing state before side effects."""
    if not _try_acquire_lock():
        return {"status": "lock_timeout"}
    try:
        state = load_state()
        if (
            state.get("status") != "kickoff_started"
            or state.get("startup_attempt_id") != startup_attempt_id
            or state.get("lease_owner") != lease_owner
        ):
            return {"status": "stale", "state": state}
        state["status"] = "kickoff_processing"
        state["lease_expires_at"] = _iso(_now_utc() + timedelta(seconds=lease_seconds))
        save_state(state)
        return {"status": "updated", "state": state}
    finally:
        _release_lock()
