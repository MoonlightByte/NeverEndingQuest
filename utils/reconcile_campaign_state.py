#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Conservatively reconcile campaign-linked state files.

This utility only patches missing entries. It does not remove data or
overwrite existing values that already differ.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.commit_state import recover_incomplete_refresh_commit

PARTY_TRACKER_FILE = "party_tracker.json"
CAMPAIGN_FILE = os.path.join("modules", "campaign.json")
WORLD_REGISTRY_FILE = os.path.join("modules", "world_registry.json")
STARTUP_STATE_FILE = os.path.join("modules", "conversation_history", "startup_state.json")


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


def reconcile_campaign_state() -> Dict[str, Any]:
    """Patch missing campaign state links conservatively.

    Returns a summary describing which files were changed.
    """
    changes: List[str] = []
    module_name = ""
    recovered_commit, recovery_result = recover_incomplete_refresh_commit()
    if recovered_commit:
        changes.append("modules/commit_state.json:rolled_back")

    party_tracker = _load_json_dict(PARTY_TRACKER_FILE)
    raw_module_name = party_tracker.get("module", "")
    if isinstance(raw_module_name, str):
        module_name = _normalize_module_name(raw_module_name)

    campaign = _load_json_dict(CAMPAIGN_FILE)
    campaign_available = campaign.get("availableModules")
    if not isinstance(campaign_available, list):
        campaign_available = []
        campaign["availableModules"] = campaign_available

    # Build canonical module set from disk (module directories with at least one area JSON).
    canonical_modules: List[str] = []
    modules_root = "modules"
    if os.path.isdir(modules_root):
        for entry in os.listdir(modules_root):
            module_dir = os.path.join(modules_root, entry)
            if not os.path.isdir(module_dir):
                continue
            if entry in {"campaign_archives", "campaign_summaries", "conversation_history", ".commit_backups"}:
                continue
            has_area = False
            for root, _dirs, files in os.walk(module_dir):
                for name in files:
                    if not name.endswith(".json"):
                        continue
                    if name.startswith("map_") or name.startswith("module_") or name.startswith("plot_"):
                        continue
                    has_area = True
                    break
                if has_area:
                    break
            if has_area:
                canonical_modules.append(entry)

    if module_name and module_name not in canonical_modules:
        canonical_modules.append(module_name)

    campaign_changed = False
    for mod in canonical_modules:
        campaign_changed = _append_unique(campaign_available, mod) or campaign_changed

    if campaign_changed:
        _ensure_parent_dir(CAMPAIGN_FILE)
        safe_json_dump(campaign, CAMPAIGN_FILE)
        changes.append("modules/campaign.json:availableModules")

    world_registry = _load_json_dict(WORLD_REGISTRY_FILE)
    modules_map = world_registry.get("modules")
    if not isinstance(modules_map, dict):
        modules_map = {}
        world_registry["modules"] = modules_map

    registry_changed = False
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
