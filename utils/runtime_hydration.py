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

import copy
import json
from pathlib import Path
from shutil import copy2
from typing import Any, Dict, List

from utils.enhanced_logger import warning


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _merge_live_area_payload(live_payload: Dict[str, Any], canonical_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Merge canonical area structure into live runtime state, preserving mutable fields."""
    if not isinstance(canonical_payload, dict):
        return live_payload

    merged_payload = copy.deepcopy(canonical_payload)
    live_locations = {
        str(location.get("locationId", "") or "").strip(): location
        for location in live_payload.get("locations", [])
        if isinstance(location, dict) and str(location.get("locationId", "") or "").strip()
    }
    runtime_fields = {
        "npcs",
        "encounters",
        "adventure_event_summary",
        "items",
        "objects",
        "doors",
        "traps",
        "monsters",
        "temporaryEffects",
    }

    merged_locations: List[Dict[str, Any]] = []
    for canonical_location in canonical_payload.get("locations", []):
        if not isinstance(canonical_location, dict):
            continue
        location_id = str(canonical_location.get("locationId", "") or "").strip()
        merged_location = copy.deepcopy(canonical_location)
        live_location = live_locations.get(location_id, {})
        if isinstance(live_location, dict):
            for field, value in live_location.items():
                if field in runtime_fields and value:
                    merged_location[field] = copy.deepcopy(value)
                elif field not in merged_location:
                    merged_location[field] = copy.deepcopy(value)
        merged_locations.append(merged_location)

    merged_payload["locations"] = merged_locations
    for field, value in live_payload.items():
        if field not in merged_payload:
            merged_payload[field] = copy.deepcopy(value)
    return merged_payload


def _merge_live_plot_payload(live_payload: Dict[str, Any], canonical_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Merge canonical plot structure into live runtime plot state, preserving progress."""
    if not isinstance(canonical_payload, dict):
        return live_payload

    merged_payload = copy.deepcopy(canonical_payload)
    live_plot_points = {
        str(plot_point.get("id", "") or "").strip(): plot_point
        for plot_point in live_payload.get("plotPoints", [])
        if isinstance(plot_point, dict) and str(plot_point.get("id", "") or "").strip()
    }
    runtime_fields = {
        "status",
        "plotImpact",
        "sideQuests",
        "currentSituation",
        "notes",
        "completed_at",
        "updated_at",
    }

    merged_plot_points: List[Dict[str, Any]] = []
    for canonical_plot_point in canonical_payload.get("plotPoints", []):
        if not isinstance(canonical_plot_point, dict):
            continue
        plot_point_id = str(canonical_plot_point.get("id", "") or "").strip()
        merged_plot_point = copy.deepcopy(canonical_plot_point)
        live_plot_point = live_plot_points.get(plot_point_id, {})
        if isinstance(live_plot_point, dict):
            for field in runtime_fields:
                if field in live_plot_point:
                    merged_plot_point[field] = copy.deepcopy(live_plot_point[field])
            for field, value in live_plot_point.items():
                if field not in merged_plot_point:
                    merged_plot_point[field] = copy.deepcopy(value)
        merged_plot_points.append(merged_plot_point)

    canonical_ids = {str(plot_point.get("id", "") or "").strip() for plot_point in canonical_payload.get("plotPoints", []) if isinstance(plot_point, dict)}
    for plot_point_id, live_plot_point in live_plot_points.items():
        if plot_point_id and plot_point_id not in canonical_ids:
            merged_plot_points.append(copy.deepcopy(live_plot_point))

    merged_payload["plotPoints"] = merged_plot_points
    for field, value in live_payload.items():
        if field not in merged_payload:
            merged_payload[field] = copy.deepcopy(value)
    return merged_payload


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
        "repaired_existing": 0,
        "repaired_files": [],
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
            canonical_payload = _load_json(bu_file)
            live_payload = _load_json(live_file)
            canonical_ids = {
                str(location.get("locationId", "") or "").strip()
                for location in canonical_payload.get("locations", [])
                if isinstance(location, dict)
            }
            live_ids = {
                str(location.get("locationId", "") or "").strip()
                for location in live_payload.get("locations", [])
                if isinstance(location, dict)
            }
            if canonical_ids and canonical_ids != live_ids:
                try:
                    merged_payload = _merge_live_area_payload(live_payload, canonical_payload)
                    _write_json(live_file, merged_payload)
                    result["repaired_existing"] += 1
                    result["repaired_files"].append(str(live_file))
                except Exception as exc:
                    result["failed"] += 1
                    result["failed_files"].append(str(live_file))
                    warning(
                        f"Startup area hydration repair failed for {live_file}: {exc}",
                        category="startup",
                    )
            else:
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
        "repaired_existing": 0,
        "repaired_files": [],
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
            canonical_payload = _load_json(bu_file)
            live_payload = _load_json(live_file)
            canonical_ids = {
                str(plot_point.get("id", "") or "").strip()
                for plot_point in canonical_payload.get("plotPoints", [])
                if isinstance(plot_point, dict)
            }
            live_ids = {
                str(plot_point.get("id", "") or "").strip()
                for plot_point in live_payload.get("plotPoints", [])
                if isinstance(plot_point, dict)
            }
            if canonical_ids and canonical_ids != live_ids:
                try:
                    merged_payload = _merge_live_plot_payload(live_payload, canonical_payload)
                    _write_json(live_file, merged_payload)
                    result["repaired_existing"] += 1
                    result["repaired_files"].append(str(live_file))
                except Exception as exc:
                    result["failed"] += 1
                    result["failed_files"].append(str(live_file))
                    warning(
                        f"Startup plot hydration repair failed for {live_file}: {exc}",
                        category="startup",
                    )
            else:
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
