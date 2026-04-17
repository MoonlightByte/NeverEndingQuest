# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Toolkit Homebrew Rebuild Guard
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Safety helpers for repeated Homebrew upload rebuilds.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _utc_stamp() -> str:
    """Return compact UTC timestamp for folder naming."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def detect_module_collision(module_name: str) -> Dict[str, Any]:
    """Return module directory collision metadata."""
    slug = str(module_name or "").strip()
    module_dir = Path("modules") / slug
    exists = module_dir.exists() and module_dir.is_dir()
    return {
        "status": "success",
        "module_name": slug,
        "module_dir": str(module_dir),
        "module_dir_exists": exists,
    }


def prepare_backup_clean_rebuild(module_name: str, overwrite_policy: str = "backup_clean") -> Dict[str, Any]:
    """Create backup for existing module then clean active directory."""
    policy = str(overwrite_policy or "").strip().lower()
    if policy != "backup_clean":
        return {
            "status": "rebuild_prepare_failed",
            "reason": "unsupported_overwrite_policy",
            "overwrite_policy": policy,
        }

    slug = str(module_name or "").strip()
    module_dir = Path("modules") / slug
    if not module_dir.exists() or not module_dir.is_dir():
        return {
            "status": "success",
            "reason": "module_directory_not_present",
            "module_name": slug,
            "module_dir": str(module_dir),
            "overwrite_policy": policy,
            "rebuild_mode": False,
        }

    backup_root = Path("modules") / "_rebuild_backups"
    backup_root.mkdir(parents=True, exist_ok=True)

    backup_dir = backup_root / f"{slug}__pre_rebuild__{_utc_stamp()}"

    try:
        shutil.copytree(module_dir, backup_dir, dirs_exist_ok=False)
    except Exception as backup_error:
        return {
            "status": "rebuild_backup_failed",
            "reason": "backup_creation_failed",
            "error": str(backup_error),
            "module_name": slug,
            "module_dir": str(module_dir),
            "backup_dir": str(backup_dir),
            "overwrite_policy": policy,
            "rebuild_mode": True,
        }

    try:
        shutil.rmtree(module_dir)
    except Exception as clean_error:
        return {
            "status": "rebuild_prepare_failed",
            "reason": "cleanup_failed_after_backup",
            "error": str(clean_error),
            "module_name": slug,
            "module_dir": str(module_dir),
            "backup_dir": str(backup_dir),
            "overwrite_policy": policy,
            "rebuild_mode": True,
        }

    return {
        "status": "success",
        "reason": "backup_created_and_target_cleaned",
        "module_name": slug,
        "module_dir": str(module_dir),
        "backup_dir": str(backup_dir),
        "overwrite_policy": policy,
        "rebuild_mode": True,
    }
