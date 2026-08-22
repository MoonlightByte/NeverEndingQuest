#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Conservatively reconcile campaign-linked state files.

This utility patches missing entries and removes only known hidden/system
directory names that older reconciliation could misclassify as modules. It
does not overwrite differing campaign values or remove unknown modules.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.module_refresh_lock import module_refresh_lock

PARTY_TRACKER_FILE = "party_tracker.json"
CAMPAIGN_FILE = os.path.join("modules", "campaign.json")
WORLD_REGISTRY_FILE = os.path.join("modules", "world_registry.json")
STARTUP_STATE_FILE = os.path.join("modules", "conversation_history", "startup_state.json")
_SYSTEM_MODULE_DIRECTORIES = {
    "backups",
    "campaign_archives",
    "campaign_summaries",
    "conversation_history",
    "default",
    "encounters",
    "logs",
}


def _normalize_module_name(module_name: str) -> str:
    return module_name.replace(" ", "_").strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_startup_state() -> Dict[str, Any]:
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
        "updated_at": _utc_now_iso(),
    }


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _load_json_dict(path: str) -> Dict[str, Any]:
    data = safe_json_load(path)
    return data if isinstance(data, dict) else {}


def _append_unique(items: List[str], value: str) -> bool:
    if value in items:
        return False
    items.append(value)
    return True


def _is_system_module_name(module_name: Any) -> bool:
    return (
        not isinstance(module_name, str)
        or module_name.startswith(".")
        or module_name in _SYSTEM_MODULE_DIRECTORIES
    )


def _is_canonical_module_directory(module_dir: str) -> bool:
    """Match the stitcher's module shape, not arbitrary nested JSON."""
    areas_dir = os.path.join(module_dir, "areas")
    if not os.path.isdir(areas_dir):
        return False
    for filename in os.listdir(areas_dir):
        if not filename.endswith(".json") or filename.endswith("_BU.json"):
            continue
        if filename.startswith(("module_", "party_", "campaign_", "map_", "plot_")):
            continue
        area = _load_json_dict(os.path.join(areas_dir, filename))
        if {
            "areaId",
            "areaName",
            "locations",
        }.issubset(area):
            return True
    return False


def reconcile_campaign_state() -> Dict[str, Any]:
    """Reconcile only after any live module refresh reaches a stable phase."""
    with module_refresh_lock() as acquired:
        if not acquired:
            return {
                "changed": False,
                "changes": [],
                "module": None,
                "canonical_modules": [],
                "commit_recovery": {"status": "module_refresh_lock_timeout"},
            }
        return _reconcile_campaign_state_locked()


def _reconcile_campaign_state_locked() -> Dict[str, Any]:
    """Patch missing campaign state links conservatively.

    Returns a summary describing which files were changed.
    """
    changes: List[str] = []
    module_name = ""

    party_tracker = _load_json_dict(PARTY_TRACKER_FILE)
    raw_module_name = party_tracker.get("module", "")
    if isinstance(raw_module_name, str):
        module_name = _normalize_module_name(raw_module_name)

    # Build canonical module set from disk (module directories with at least one area JSON).
    canonical_modules: List[str] = []
    modules_root = "modules"
    if os.path.isdir(modules_root):
        for entry in os.listdir(modules_root):
            module_dir = os.path.join(modules_root, entry)
            if not os.path.isdir(module_dir):
                continue
            if _is_system_module_name(entry):
                continue
            if _is_canonical_module_directory(module_dir):
                canonical_modules.append(entry)

    if (
        module_name
        and not _is_system_module_name(module_name)
        and module_name not in canonical_modules
    ):
        canonical_modules.append(module_name)

    # Share the same recovery + process-lock + fresh-merge boundary as live
    # campaign writers so reconciliation cannot erase a concurrent completion.
    from core.managers.campaign_manager import (
        _default_campaign_data,
        mutate_campaign_state,
    )

    def merge_available_modules(fresh_campaign: Dict[str, Any]) -> bool:
        campaign_available = fresh_campaign.get("availableModules")
        changed = not isinstance(campaign_available, list)
        if not isinstance(campaign_available, list):
            campaign_available = []
        filtered_available = [
            item
            for item in campaign_available
            if not _is_system_module_name(item)
        ]
        if filtered_available != campaign_available:
            changed = True
        campaign_available = filtered_available
        fresh_campaign["availableModules"] = campaign_available
        for mod in canonical_modules:
            changed = _append_unique(campaign_available, mod) or changed
        return changed

    campaign, campaign_changed = mutate_campaign_state(
        CAMPAIGN_FILE,
        merge_available_modules,
        # Never seed a file deleted by reset/restore from a pre-lock snapshot.
        fallback=_default_campaign_data(),
    )
    if campaign_changed:
        changes.append("modules/campaign.json:availableModules")

    world_registry = _load_json_dict(WORLD_REGISTRY_FILE)
    modules_map = world_registry.get("modules")
    if not isinstance(modules_map, dict):
        modules_map = {}
        world_registry["modules"] = modules_map

    registry_changed = False
    for registered_module in list(modules_map):
        if _is_system_module_name(registered_module):
            del modules_map[registered_module]
            registry_changed = True
    for mod in canonical_modules:
        if mod not in modules_map:
            modules_map[mod] = {"moduleName": mod}
            registry_changed = True
    if registry_changed:
        _ensure_parent_dir(WORLD_REGISTRY_FILE)
        safe_json_dump(world_registry, WORLD_REGISTRY_FILE)
        changes.append("modules/world_registry.json:modules")

    if not os.path.exists(STARTUP_STATE_FILE):
        _ensure_parent_dir(STARTUP_STATE_FILE)
        safe_json_dump(_default_startup_state(), STARTUP_STATE_FILE)
        changes.append("modules/conversation_history/startup_state.json")

    return {
        "changed": bool(changes),
        "changes": changes,
        "module": module_name or None,
        "canonical_modules": canonical_modules,
        "commit_recovery": recovery_result,
    }


def main() -> int:
    """CLI entry point."""
    result = reconcile_campaign_state()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
