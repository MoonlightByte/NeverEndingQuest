# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""The in-game module build's record, module_build_job.json (#2052 J3c).

One record at most, in the game's own folder (utils.data_root.game_root: the
working directory, which is NEQ_DATA_DIR once a data root is entered). It says which build was running
or published-but-not-yet-announced when this game last ran, so a later start
can carry it on (J3c-3) and a Load can tell the DM whether it exists (J3c-2).

Written only by the build job and the restart, always whole and atomically
(a temp file in the same folder, fsync, os.replace), under the record lock.
It never holds a secret or an address: no API key, no base URL (only its
SHA-256), no party names. It is never part of a save or a Reset backup; a
Load and a Reset remove it. A record that cannot be read is no record.

A deliberate Quit (the player's or the host's) removes the running record of
the build it stopped (remove_running_for_quit); a published one is kept. An
unexpected end (a crash, a kill) keeps it, and the next start carries the
build on once (J3c-3: decide_restart, then main.service_build_restart).

Every write and removal is fail-forward: a failure is logged and the build
and the game carry on (a missing record only means a crash cannot be
carried on, as before J3c).
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from utils.data_root import game_root
from utils.enhanced_logger import debug, warning

RECORD_NAME = "module_build_job.json"
RECORD_VERSION = 1
STATES = ("running", "published")
DECLARATION_NAMES = ("module_declaration.json", "module_declaration.refused.json")
_WRITE_WAIT_SECONDS = 5.0


def record_path() -> str:
    return os.path.join(game_root(), RECORD_NAME)


def _lock_target() -> str:
    """The record lock, in the game folder's .runtime_locks (as the build
    locks): two processes on one game folder meet there whatever their
    RUNTIME_LOCKS_DIR. Resolved once per locked call."""
    return os.path.join(game_root(), ".runtime_locks", "module_build_job")


def url_sha256(url: Optional[str]) -> Optional[str]:
    """The base URL's SHA-256 (hex) as configured, or None without one."""
    if not isinstance(url, str) or not url:
        return None
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def current_in_game_build_id() -> Optional[str]:
    """The build_id of the in-game build running in this execution context
    (its BuildProviderScope), else None (a toolkit build, or no build)."""
    try:
        from utils.capture.live_provider_call import (
            BuildProviderScope,
            get_live_provider_scope,
        )

        scope = get_live_provider_scope()
    except Exception:
        return None
    if isinstance(scope, BuildProviderScope) and scope.build_id:
        return str(scope.build_id)
    return None


def _valid(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and data.get("version") == RECORD_VERSION
        and isinstance(data.get("build_id"), str)
        and bool(data.get("build_id"))
        and data.get("state") in STATES
        and isinstance(data.get("workspaces"), list)
    )


def read_record() -> Optional[Dict[str, Any]]:
    """The record, or None when it is missing or cannot be used (a torn,
    unreadable or other-version file counts as none and is removed)."""
    path = record_path()
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        warning("Build record unreadable (%s); treated as none" % type(exc).__name__,
                category="module_management")
        return None
    if not stat.S_ISREG(st.st_mode):
        warning("Build record is not a regular file; treated as none",
                category="module_management")
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        data = None
        reason = type(exc).__name__
    else:
        reason = "not a version %d record" % RECORD_VERSION
    if _valid(data):
        return data
    version = data.get("version") if isinstance(data, dict) else None
    if type(version) is int and version > RECORD_VERSION:
        # A newer game's record: not ours to read or delete.
        warning("Build record is version %d (newer than %d); left in place and not used"
                % (version, RECORD_VERSION), category="module_management")
        return None
    warning("Build record could not be used (%s); removed" % reason,
            category="module_management")
    _remove_file(path)
    return None


def _remove_file(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        warning("Build record not removed (%s)" % type(exc).__name__,
                category="module_management")


def _clear_leftover_temps(folder: str) -> None:
    """Temp files of a writer that died mid-write. Every write runs under the
    record lock, which no dead process holds, so any temp file present now is
    a leftover (removed fail-forward)."""
    prefix = RECORD_NAME + "."
    try:
        with os.scandir(folder) as entries:
            names = [e.name for e in entries
                     if e.name.startswith(prefix) and e.name.endswith(".tmp") and e.is_file(follow_symlinks=False)]
    except OSError:
        return
    for name in names:
        _remove_file(os.path.join(folder, name))


def _write(data: Dict[str, Any]) -> bool:
    """Whole-file atomic write, under the record lock; False (logged) on any
    failure, the old record then stays as it was."""
    path = record_path()
    folder = os.path.dirname(path)
    _clear_leftover_temps(folder)
    tmp = os.path.join(folder, "%s.%d.%s.tmp" % (RECORD_NAME, os.getpid(), uuid.uuid4().hex[:8]))
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        warning("Build record not written (%s); the build carries on" % type(exc).__name__,
                category="module_management")
        _remove_file(tmp)
        return False
    if os.name != "nt":
        try:
            fd = os.open(folder, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass
    return True


def _locked(fn):
    """Run fn under the record lock (a short wait); a lock that cannot be
    taken or that raises is a logged no-op (fail-forward)."""
    try:
        from utils.path_transaction_lock import path_transaction_lock

        with path_transaction_lock(_lock_target(), timeout_seconds=_WRITE_WAIT_SECONDS) as acquired:
            if acquired is None:
                warning("Build record busy; not updated", category="module_management")
                return False
            return fn()
    except Exception as exc:
        warning("Build record not updated (%s)" % type(exc).__name__,
                category="module_management")
        return False


def _start_module() -> Optional[str]:
    try:
        with open(os.path.join(game_root(), "party_tracker.json"), "r", encoding="utf-8") as handle:
            module = json.load(handle).get("module")
    except (OSError, ValueError, AttributeError):
        return None
    return module if isinstance(module, str) and module else None


def create_record(build_id: str, parameters: Dict[str, Any], inputs: Any) -> bool:
    """At a job's start: a new running record (replaces any older one).
    Field by field from the inputs: never the key, the URL or party names."""
    from core.ai.module_creation_contract import CREATE_NEW_MODULE_PARAMETER_KEYS

    # Only the contract's keys (J3c-3: the restart's parameters), never the
    # raw action dict.
    kept = {
        key: parameters.get(key) if isinstance(parameters, dict) else None
        for key in sorted(CREATE_NEW_MODULE_PARAMETER_KEYS)
    }
    data = {
        "version": RECORD_VERSION,
        "build_id": str(build_id),
        "state": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "start_module": _start_module(),
        "restarts": 0,
        "parameters": {k: (v if isinstance(v, str) else None) for k, v in kept.items()},
        "inputs": {
            "provider": getattr(inputs, "provider", None),
            "story_first": bool(getattr(inputs, "story_first", False)),
            "local_model": getattr(inputs, "local_model", None),
            "local_base_url_sha256": url_sha256(getattr(inputs, "local_base_url", None)),
        },
        "workspaces": [],
    }
    ok = _locked(lambda: _write(data))
    if ok:
        debug("Build record written for build %s" % build_id, category="module_management")
    return bool(ok)


def _epoch_moved() -> bool:
    """True when the running build's fence was claimed in an earlier game
    epoch (a Load or Reset since): its record must not be written back."""
    try:
        from utils.capture.live_provider_call import active_build_fence, game_epoch

        fence = active_build_fence()
        return fence is not None and game_epoch() != fence.start_epoch
    except Exception:
        return False


def _update(build_id: str, change) -> bool:
    def run():
        if _epoch_moved():
            debug("Build record not updated: a Load or Reset replaced the game",
                  category="module_management")
            return False
        data = read_record()
        if data is None or data.get("build_id") != str(build_id):
            return False
        change(data)
        return _write(data)

    return bool(_locked(run))


def note_workspace(build_id: str, workspace_hex: str) -> bool:
    """A reservation of this build: its hex appended to workspaces."""
    def change(data):
        if workspace_hex not in data["workspaces"]:
            data["workspaces"].append(workspace_hex)

    return _update(build_id, change)


def mark_published(build_id: str, module_name: str) -> bool:
    def change(data):
        data["state"] = "published"
        data["module_name"] = module_name

    return _update(build_id, change)


def remove_record(build_id: Optional[str] = None, reason: str = "") -> bool:
    """Remove the record; with build_id, only when it is that build's."""
    def run():
        data = read_record()
        if data is None:
            return False
        if build_id is not None and data.get("build_id") != str(build_id):
            return False
        _remove_file(record_path())
        debug("Build record removed (%s)" % (reason or "ended"), category="module_management")
        return True

    return bool(_locked(run))


_LIFECYCLE_WAIT_SECONDS = 3.0


def remove_record_for_lifecycle(reason: str) -> None:
    """Load and Reset: remove whatever record there is, UNDER the record lock
    (a short wait), so a build job's update in flight (read, then replace)
    cannot write it back after this removal. The callers hold the transition
    and refresh locks first: the order is always those, then the record lock.
    A lock that times out or fails: the removal runs unlocked, logged. Never
    raises."""
    def remove():
        if os.path.lexists(record_path()):
            _remove_file(record_path())
            debug("Build record removed (%s)" % reason, category="module_management")

    try:
        from utils.path_transaction_lock import path_transaction_lock

        with path_transaction_lock(_lock_target(), timeout_seconds=_LIFECYCLE_WAIT_SECONDS) as acquired:
            if acquired is not None:
                remove()
                return
        warning("Build record lock busy at %s; removed without it" % reason,
                category="module_management")
    except Exception as exc:
        warning("Build record lock failed at %s (%s); removed without it" % (reason, type(exc).__name__),
                category="module_management")
    try:
        remove()
    except Exception:
        pass


def find_module_by_build_id(build_id: str, modules_root: Optional[str] = None) -> Optional[str]:
    """The live module whose declaration (or set-aside declaration) carries
    buildId == build_id, else None. Real, visible folders only (no link,
    junction or reparse point); read errors count as not found. The modules
    folder is the game's own (game_root()/modules), as every module read."""
    if not build_id:
        return None
    from utils.module_publish import _plain_directory

    root = modules_root or os.path.join(game_root(), "modules")
    try:
        with os.scandir(root) as entries:
            names = sorted(entry.name for entry in entries)
    except OSError:
        return None
    for name in names:
        if name.startswith("."):
            continue
        folder = os.path.join(root, name)
        try:
            if not _plain_directory(folder, os.lstat(folder)):
                continue
        except OSError:
            continue
        for declaration in DECLARATION_NAMES:
            try:
                with open(os.path.join(folder, declaration), "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("buildId") == str(build_id):
                return name
    return None


def remove_running_for_quit(build_id: Optional[str], kind: str) -> bool:
    """J3c-3 (D-AUTH-1): a deliberate Quit stopped this process's build: its
    record goes when it is still running; a published one is kept (the next
    start announces it). Under the record lock (a short wait); fail-forward,
    never raises."""
    if not build_id:
        return False

    def run():
        data = read_record()
        if data is None or data.get("build_id") != str(build_id) or data.get("state") != "running":
            return False
        _remove_file(record_path())
        debug("Build record removed (%s: a deliberate quit)" % kind, category="module_management")
        return True

    try:
        return bool(_locked(run))
    except Exception:
        return False


RESTART_MAX_AGE_SECONDS = 24 * 60 * 60


def _archived_open_start(start_module: Any, build_id: str) -> bool:
    """a9 L2 (iii): the start module's newest conversation archive holds an
    OPEN start for build_id. Any doubt is False."""
    try:
        from core.ai import history_markers as hm
        from core.managers.campaign_manager import _normalize_module_name as writer_name

        name = writer_name(start_module)
        folder = os.path.join(game_root(), "modules", "campaign_archives")
        prefix = name + "_conversation_"
        newest = None
        with os.scandir(folder) as entries:
            for entry in entries:
                tail = entry.name[len(prefix):] if entry.name.startswith(prefix) else ""
                if len(tail) == 8 and tail.endswith(".json") and tail[:3].isdigit():
                    if newest is None or int(tail[:3]) > newest[0]:
                        newest = (int(tail[:3]), entry.name)
        if newest is None:
            return False
        with open(os.path.join(folder, newest[1]), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not (isinstance(data, dict) and data.get("moduleName") == name
                and isinstance(data.get("conversationHistory"), list)):
            return False
        return str(build_id) in hm.open_build_ids(data["conversationHistory"])
    except Exception:
        return False


def _licensed(data: Dict[str, Any], live_history: Any, current_module: Any) -> bool:
    """a8 s3.2 / a9 s1: L1 an open start for the id in the live history; L2
    no note for the id in the live history, the current module differs from
    start_module (reconcile's normalizer on both sides) and start_module's
    archive holds an open start for it."""
    from core.ai import history_markers as hm
    from utils.reconcile_campaign_state import _normalize_module_name as same_name

    build_id = data["build_id"]
    history = live_history if isinstance(live_history, list) else []
    if build_id in hm.open_build_ids(history):
        return True
    if any((hm.build_marker(message) or (None,))[0] == build_id for message in history):
        return False
    start = data.get("start_module")
    if not isinstance(start, str) or not isinstance(current_module, str):
        return False
    try:
        if same_name(start) == same_name(current_module):
            return False
    except Exception:
        return False
    return _archived_open_start(start, build_id)


def _restart_refusal(data: Dict[str, Any], now: float) -> Optional[str]:
    """Why a running record is not carried on, or None (a8 s3.3 rule 5 with
    a9 s2 and a11 s4). The gateway check comes first (a12: a world under the
    operator's gateway never restarts by itself)."""
    from utils.provider_gateway import gateway

    if gateway() is not None:
        return "an operator-hosted world (gateway): no automatic restart"
    if data.get("restarts") != 0:
        return "already carried on once"
    try:
        started = datetime.fromisoformat(str(data.get("started_at")))
        if started.tzinfo is None:
            raise ValueError("naive")
        if now - started.timestamp() > RESTART_MAX_AGE_SECONDS:
            return "started more than 24 hours ago"
    except (TypeError, ValueError, OverflowError):
        return "start time unreadable"
    from core.ai.module_creation_contract import (
        ModuleCreationContractError,
        validate_create_new_module_parameters,
    )

    try:
        validate_create_new_module_parameters(data.get("parameters"))
    except ModuleCreationContractError:
        return "parameters not valid"
    from utils.build_inputs import provider_usable, take_build_inputs

    current = take_build_inputs()
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    if current.provider != inputs.get("provider"):
        return "provider changed"
    if current.provider == "lmstudio" and url_sha256(current.local_base_url) != inputs.get("local_base_url_sha256"):
        return "local address changed"
    if not provider_usable(current.provider):
        return "no usable key"
    if current.provider == "lmstudio" and current.local_model != inputs.get("local_model"):
        debug("Build %s: model changed since the build started" % data["build_id"], category="module_management")
    return None


def decide_restart(live_history: Any, current_module: Any, now: Optional[float] = None) -> Dict[str, Any]:
    """J3c-3 rules 1-5, under the record lock taken with NO wait. Returns
    {"outcome": "busy"} (another process decides), {"outcome": "none"},
    {"outcome": "drop", "reason", "build_id", "workspaces"} (record removed),
    {"outcome": "announce", "build_id", "module_name"} (record marked
    published), {"outcome": "restart", "build_id", "parameters", "story_first",
    "workspaces"} (restarts 1 written, strictly), or {"outcome": "kept",
    "reason"} (the restarts write failed). Never raises."""
    import time

    clock = time.time() if now is None else now
    result: Dict[str, Any] = {"outcome": "none"}

    def run():
        data = read_record()
        if data is None:
            return
        build_id = data["build_id"]
        workspaces = [w for w in data["workspaces"] if isinstance(w, str)]

        def drop(reason):
            _remove_file(record_path())
            result.update(outcome="drop", reason=reason, build_id=build_id, workspaces=workspaces)

        if not _licensed(data, live_history, current_module):
            return drop("not licensed")
        module = find_module_by_build_id(build_id)
        if module:
            if data.get("state") != "published" or data.get("module_name") != module:
                data["state"] = "published"
                data["module_name"] = module
                _write(data)
            result.update(outcome="announce", build_id=build_id, module_name=module)
            return
        if data.get("state") == "published":
            return drop("published, no live module")
        reason = _restart_refusal(data, clock)
        if reason:
            return drop(reason)
        data["restarts"] = 1
        if not _write(data):
            result.update(outcome="kept", reason="restarts not written")
            return
        inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
        result.update(outcome="restart", build_id=build_id, parameters=dict(data["parameters"]),
                      story_first=bool(inputs.get("story_first")), workspaces=workspaces)

    try:
        from utils.path_transaction_lock import path_transaction_lock

        with path_transaction_lock(_lock_target(), timeout_seconds=0) as acquired:
            if acquired is None:
                return {"outcome": "busy"}
            run()
    except Exception as exc:
        warning("Build restart decision failed (%s)" % type(exc).__name__, category="module_management")
        return {"outcome": "error", "reason": type(exc).__name__}
    return result
