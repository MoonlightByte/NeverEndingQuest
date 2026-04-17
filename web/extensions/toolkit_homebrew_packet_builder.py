# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Toolkit Homebrew Packet Builder
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Packet-aware builder facade for approved Homebrew upload workspaces.
"""

import math
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from utils.enhanced_logger import error, info
from utils.toolkit_homebrew_upload_contract import (
    REVIEW_DECISION_APPROVE,
    get_workspace_files,
    load_json_artifact,
    persist_build_result_artifact,
    persist_builder_input_artifact,
    validate_review_packet,
)


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_module_name(raw_name: str) -> str:
    """Return a builder-safe module name."""
    safe = "".join(ch for ch in str(raw_name or "") if ch.isalnum() or ch in {"_", "-", " "}).strip()
    safe = safe.replace("-", "_").replace(" ", "_")
    if not safe:
        return "Homebrew_Upload_Module"
    return safe


def _derive_builder_shape(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Derive stable builder parameters from normalized packet shape."""
    acts = packet.get("acts") or []
    locations = packet.get("locations") or []

    if isinstance(acts, list) and acts:
        num_areas = max(1, min(len(acts), 10))
    else:
        num_areas = 3

    location_count = len(locations) if isinstance(locations, list) else 0
    if location_count > 0:
        locations_per_area = int(math.ceil(float(location_count) / float(num_areas)))
        locations_per_area = max(3, min(locations_per_area, 30))
    else:
        locations_per_area = 5

    title = str(packet.get("title") or "Homebrew Upload Module").strip()
    module_name = _sanitize_module_name(title)

    return {
        "module_name": module_name,
        "num_areas": num_areas,
        "locations_per_area": locations_per_area,
        "output_directory": f"./modules/{module_name}",
    }


def derive_packet_module_name(packet: Dict[str, Any]) -> str:
    """Return normalized module slug derived from packet content."""
    params = _derive_builder_shape(packet)
    return str(params.get("module_name") or "").strip()


def _read_builder_narrative(files: Dict[str, Path], packet: Dict[str, Any]) -> Dict[str, str]:
    """Resolve builder narrative text with packet fallback."""
    narrative_path = files["builder_narrative"]
    narrative_text = ""
    source = "packet_fallback"

    try:
        narrative_text = narrative_path.read_text(encoding="utf-8").strip()
    except Exception:
        narrative_text = ""

    if narrative_text:
        source = "workspace_builder_narrative"
    else:
        title = str(packet.get("title") or "Unknown Module").strip()
        description = str(packet.get("description") or "").strip()
        summary = str(packet.get("adventure_summary") or "").strip()
        narrative_text = "\n\n".join(
            line
            for line in [
                f"Build module: {title}",
                description,
                summary,
            ]
            if line
        ).strip()
        if not narrative_text:
            narrative_text = f"Build module: {title}"

    return {
        "narrative": narrative_text,
        "source": source,
    }


def _validate_review_snapshot(packet: Dict[str, Any], review_snapshot: Dict[str, Any]) -> Optional[str]:
    """Validate review snapshot and packet identity alignment."""
    if not isinstance(review_snapshot, dict) or not review_snapshot:
        return "review_snapshot_missing"

    decision = str(review_snapshot.get("decision") or "").strip().lower()
    if decision != REVIEW_DECISION_APPROVE:
        return "review_snapshot_not_approved"

    packet_identity = review_snapshot.get("packet_identity") or {}
    review_source_hash = str(packet_identity.get("source_hash") or "").strip()
    packet_source_hash = str(packet.get("source_hash") or "").strip()
    if review_source_hash and packet_source_hash and review_source_hash != packet_source_hash:
        return "review_packet_identity_mismatch"

    return None


def _execute_module_builder(builder_input: Dict[str, Any]) -> None:
    """Run the upstream module builder using derived packet parameters."""
    from core.generators.module_builder import BuilderConfig, ModuleBuilder

    params = builder_input["derived_builder_parameters"]
    config = BuilderConfig(
        module_name=params["module_name"],
        num_areas=params["num_areas"],
        locations_per_area=params["locations_per_area"],
        output_directory=params["output_directory"],
        verbose=True,
    )
    builder = ModuleBuilder(config)
    builder.build_module(builder_input["builder_narrative"])


def run_toolkit_homebrew_packet_build(
    workspace: Path,
    job_id: str,
    builder_executor: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Build one approved Homebrew upload workspace from normalized packet."""
    files = get_workspace_files(workspace)
    packet = load_json_artifact(files["normalized_packet"])
    packet_ok, packet_error = validate_review_packet(packet)
    if not packet_ok:
        return {
            "status": "failed",
            "stage": "build",
            "error": f"normalized_packet_invalid:{packet_error}",
            "job_id": job_id,
        }

    review_snapshot = load_json_artifact(files["ui_review_snapshot"])
    review_error = _validate_review_snapshot(packet, review_snapshot)
    if review_error:
        return {
            "status": "failed",
            "stage": "build",
            "error": review_error,
            "job_id": job_id,
        }

    params = _derive_builder_shape(packet)
    narrative_bundle = _read_builder_narrative(files, packet)

    builder_input = {
        "status": "ready",
        "stage": "builder_input",
        "created_at": _utc_now_iso(),
        "job_id": job_id,
        "build_mode": "packet_workspace_v1",
        "packet_identity": {
            "packet_version": packet.get("packet_version"),
            "source_hash": packet.get("source_hash"),
            "source_path": packet.get("source_path"),
            "title": packet.get("title"),
        },
        "review_snapshot": {
            "decision": review_snapshot.get("decision"),
            "recorded_at": review_snapshot.get("recorded_at"),
            "job_id": review_snapshot.get("job_id"),
        },
        "derived_builder_parameters": params,
        "builder_narrative_source": narrative_bundle["source"],
        "builder_narrative": narrative_bundle["narrative"],
    }

    if not persist_builder_input_artifact(workspace, builder_input):
        return {
            "status": "failed",
            "stage": "build",
            "error": "builder_input_persist_failed",
            "job_id": job_id,
            "packet_identity": builder_input["packet_identity"],
        }

    executor = builder_executor or _execute_module_builder

    try:
        info(
            (
                f"TOOLKIT_HOMEBREW: Starting packet-driven build job={job_id} "
                f"module={params['module_name']}"
            ),
            category="web_interface",
        )
        executor(builder_input)

        build_result = {
            "status": "success",
            "stage": "build",
            "job_id": job_id,
            "build_mode": "packet_workspace_v1",
            "completed_at": _utc_now_iso(),
            "packet_identity": builder_input["packet_identity"],
            "module_name": params["module_name"],
            "output_directory": params["output_directory"],
            "builder_input_path": str(files["builder_input"]),
            "build_result_path": str(files["build_result"]),
        }
    except Exception as build_error:
        error(
            f"TOOLKIT_HOMEBREW: Packet-driven build failed for job={job_id}: {build_error}",
            exception=build_error,
            category="web_interface",
        )
        build_result = {
            "status": "failed",
            "stage": "build",
            "job_id": job_id,
            "build_mode": "packet_workspace_v1",
            "completed_at": _utc_now_iso(),
            "packet_identity": builder_input["packet_identity"],
            "module_name": params["module_name"],
            "output_directory": params["output_directory"],
            "builder_input_path": str(files["builder_input"]),
            "build_result_path": str(files["build_result"]),
            "error": str(build_error),
        }

    build_result["build_result_persisted"] = persist_build_result_artifact(workspace, build_result)
    if not build_result["build_result_persisted"]:
        build_result["status"] = "failed"
        build_result["error"] = "build_result_persist_failed"

    return build_result
