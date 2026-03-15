# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Runtime Hydration - Deterministic startup hydration helpers.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from pathlib import Path
from shutil import copy2
from typing import Any, Dict, List

from utils.enhanced_logger import warning


def hydrate_missing_live_area_files_from_bu(modules_root: str = "modules") -> Dict[str, Any]:
    """Hydrate missing live area files from tracked *_BU.json backups.

    Args:
        modules_root: Root directory that contains module folders.

    Returns:
        Summary with restored/skipped/failed counts and deterministic file lists.
    """
    modules_path = Path(modules_root)
    result: Dict[str, Any] = {
        "restored": 0,
        "skipped_existing": 0,
        "failed": 0,
        "restored_files": [],
        "failed_files": [],
    }

    if not modules_path.exists():
        return result

    bu_files: List[Path] = sorted(
        modules_path.glob("*/areas/*_BU.json"),
        key=lambda path: str(path).lower(),
    )

    for bu_file in bu_files:
        if "saved_games" in bu_file.parts:
            continue

        live_file = bu_file.with_name(bu_file.name.replace("_BU.json", ".json"))
        if live_file.exists():
            result["skipped_existing"] += 1
            continue

        try:
            copy2(bu_file, live_file)
            result["restored"] += 1
            result["restored_files"].append(str(live_file))
        except Exception as exc:
            result["failed"] += 1
            result["failed_files"].append(str(live_file))
            warning(
                f"Startup area hydration failed for {live_file}: {exc}",
                category="startup",
            )

    return result


def hydrate_missing_module_plot_files_from_bu(modules_root: str = "modules") -> Dict[str, Any]:
    """Hydrate missing live module_plot.json files from tracked BU backups.

    Args:
        modules_root: Root directory that contains module folders.

    Returns:
        Summary with restored/skipped/failed counts and deterministic file lists.
    """
    modules_path = Path(modules_root)
    result: Dict[str, Any] = {
        "restored": 0,
        "skipped_existing": 0,
        "failed": 0,
        "restored_files": [],
        "failed_files": [],
    }

    if not modules_path.exists():
        return result

    bu_files: List[Path] = sorted(
        modules_path.glob("*/module_plot_BU.json"),
        key=lambda path: str(path).lower(),
    )

    for bu_file in bu_files:
        if "saved_games" in bu_file.parts:
            continue

        live_file = bu_file.with_name("module_plot.json")
        if live_file.exists():
            result["skipped_existing"] += 1
            continue

        try:
            copy2(bu_file, live_file)
            result["restored"] += 1
            result["restored_files"].append(str(live_file))
        except Exception as exc:
            result["failed"] += 1
            result["failed_files"].append(str(live_file))
            warning(
                f"Startup plot hydration failed for {live_file}: {exc}",
                category="startup",
            )

    return result
