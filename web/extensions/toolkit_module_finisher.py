# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Toolkit module post-build finishing helper.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from utils.enhanced_logger import error, info
from utils.file_operations import safe_read_json, safe_write_json


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_stage_status(status: str) -> str:
    """Normalize stage status into success/degraded/failed."""
    normalized = str(status or "").strip().lower()
    if normalized in {"success", "ok", "passed"}:
        return "success"
    if normalized in {"degraded", "warning", "warn", "partial", "skipped"}:
        return "degraded"
    return "failed"


def _run_continuity_stage(module_slug: str, module_dir: Path, strict: bool) -> Dict[str, Any]:
    """Run continuity normalization/enrichment stage."""
    from scripts.homebrew_ingest_dev import (
        _ensure_continuity_contract_keys,
        _normalize_continuity_contract,
        enrich_continuity_cross_refs,
    )

    context_path = module_dir / "module_context.json"
    plot_path = module_dir / "module_plot.json"

    if not context_path.exists() or not plot_path.exists():
        return {
            "status": "failed",
            "reason": "Required module context or plot file missing",
            "context_path": str(context_path),
            "plot_path": str(plot_path),
        }

    module_context = safe_read_json(str(context_path)) or {}
    module_plot = safe_read_json(str(plot_path)) or {}

    continuity_patch = _ensure_continuity_contract_keys(module_context, module_slug)
    module_context = continuity_patch.get("module_context", module_context)

    continuity_enrichment = enrich_continuity_cross_refs(
        module_slug=module_slug,
        module_context=module_context,
        module_plot=module_plot,
    )
    module_context = continuity_enrichment.get("module_context", module_context)

    changed = bool(continuity_patch.get("changed")) or bool(continuity_enrichment.get("changed"))
    if changed:
        write_ok = safe_write_json(str(context_path), module_context)
        if not write_ok:
            return {
                "status": "failed",
                "reason": "Failed to persist continuity normalization",
                "continuity_patch": continuity_patch,
                "continuity_enrichment": continuity_enrichment,
            }

    continuity_contract = _normalize_continuity_contract(
        module_context=module_context,
        module_plot=module_plot,
        strict=strict,
        alias_registry=None,
    )
    contract_status = str(continuity_contract.get("status", "success"))

    if strict and contract_status == "error":
        stage_status = "failed"
    elif contract_status in {"warning"}:
        stage_status = "degraded"
    else:
        stage_status = "success"

    return {
        "status": stage_status,
        "continuity_patch": continuity_patch,
        "continuity_enrichment": continuity_enrichment,
        "continuity_contract": continuity_contract,
        "context_path": str(context_path),
    }


def _run_registry_stage(module_slug: str) -> Dict[str, Any]:
    """Run registry verification and best-effort integration."""
    from core.generators.module_stitcher import ModuleStitcher
    from scripts.homebrew_registry_guard import verify_present

    verify_before = verify_present(module_slug)
    if verify_before.get("present", False):
        return {
            "status": "success",
            "verify_before": verify_before,
            "integration_attempted": False,
        }

    integration_attempted = True
    integration_success = False
    integration_error = None

    try:
        stitcher = ModuleStitcher()
        integration_success = bool(stitcher.integrate_module(module_slug))
    except Exception as stitch_error:
        integration_error = str(stitch_error)

    verify_after = verify_present(module_slug)
    if verify_after.get("present", False):
        return {
            "status": "success",
            "verify_before": verify_before,
            "verify_after": verify_after,
            "integration_attempted": integration_attempted,
            "integration_success": integration_success,
            "integration_error": integration_error,
        }

    return {
        "status": "failed",
        "reason": "Module not present in registry after integration attempt",
        "verify_before": verify_before,
        "verify_after": verify_after,
        "integration_attempted": integration_attempted,
        "integration_success": integration_success,
        "integration_error": integration_error,
    }


def _run_monster_materialization_stage(module_slug: str) -> Dict[str, Any]:
    """Run module-local monster materialization stage."""
    script_path = Path("scripts") / "homebrew_materialize_monsters.py"
    if not script_path.exists():
        return {
            "status": "degraded",
            "reason": "Monster materialization script not found",
            "script": str(script_path),
        }

    command = [
        sys.executable,
        str(script_path),
        "--module",
        module_slug,
        "--json",
    ]

    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except Exception as mat_error:
        return {
            "status": "failed",
            "reason": f"Monster materialization invocation failed: {mat_error}",
        }

    parsed_output: Dict[str, Any] = {}
    if completed.stdout:
        try:
            parsed_output = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed_output = {}

    if completed.returncode != 0:
        return {
            "status": "failed",
            "reason": "Monster materialization returned non-zero exit",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
            "parsed_output": parsed_output,
        }

    missing_count = int(parsed_output.get("missing_in_bestiary_count", 0) or 0)
    parsed_status = _normalize_stage_status(parsed_output.get("status", "success"))
    stage_status = "degraded" if (parsed_status != "failed" and missing_count > 0) else parsed_status

    if stage_status == "failed":
        stage_reason = "Monster materialization reported failure"
    elif stage_status == "degraded":
        stage_reason = "Some seed monsters were unresolved in bestiary"
    else:
        stage_reason = None

    return {
        "status": stage_status,
        "reason": stage_reason,
        "returncode": completed.returncode,
        "parsed_output": parsed_output,
    }


def run_toolkit_module_postbuild_finishing(module_slug: str, strict: bool = True) -> Dict[str, Any]:
    """Run post-build publication parity stages for toolkit-generated modules."""
    module_slug = str(module_slug or "").strip()
    if not module_slug:
        return {
            "status": "failed",
            "module_slug": module_slug,
            "reason": "Missing module slug",
            "stages": {},
        }

    module_dir = Path("modules") / module_slug
    if not module_dir.exists() or not module_dir.is_dir():
        return {
            "status": "failed",
            "module_slug": module_slug,
            "reason": "Module directory not found",
            "module_dir": str(module_dir),
            "stages": {},
        }

    info(
        f"TOOLKIT_FINISHER: Starting post-build finishing for {module_slug}",
        category="module_ingest",
    )

    stages: Dict[str, Dict[str, Any]] = {}
    overall_status = "success"

    continuity_stage = _run_continuity_stage(module_slug=module_slug, module_dir=module_dir, strict=strict)
    stages["continuity"] = continuity_stage
    if continuity_stage.get("status") == "failed":
        overall_status = "failed"
    elif continuity_stage.get("status") == "degraded":
        overall_status = "degraded"

    registry_stage = _run_registry_stage(module_slug=module_slug)
    stages["registry"] = registry_stage
    if registry_stage.get("status") == "failed":
        overall_status = "failed"
    elif registry_stage.get("status") == "degraded" and overall_status != "failed":
        overall_status = "degraded"

    materialization_stage = _run_monster_materialization_stage(module_slug=module_slug)
    stages["monster_materialization"] = materialization_stage
    if materialization_stage.get("status") == "failed":
        overall_status = "failed"
    elif materialization_stage.get("status") == "degraded" and overall_status != "failed":
        overall_status = "degraded"

    report: Dict[str, Any] = {
        "generated_at": _utc_now_iso(),
        "module_slug": module_slug,
        "status": overall_status,
        "strict": bool(strict),
        "stages": stages,
        "publication_parity_note": (
            "Post-build parity improves publication readiness but does not include full semantic publication probes."
        ),
    }

    report_path = module_dir / "toolkit_build_report.json"
    write_ok = safe_write_json(str(report_path), report)
    if not write_ok:
        error(
            f"TOOLKIT_FINISHER: Failed to write report for {module_slug}",
            category="module_ingest",
        )
        if overall_status != "failed":
            overall_status = "degraded"
        report["status"] = overall_status
        report["report_write_error"] = True

    report["report_path"] = str(report_path)

    info(
        f"TOOLKIT_FINISHER: Completed post-build finishing for {module_slug} status={overall_status}",
        category="module_ingest",
    )
    return report
