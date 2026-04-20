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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from utils.enhanced_logger import error, info
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_semantic_authority import enrich_module_semantic_authority


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalize_stage_status(status: str) -> str:
    """Normalize stage status into success/degraded/failed."""
    normalized = str(status or "").strip().lower()
    if normalized in {"success", "ok", "passed"}:
        return "success"
    if normalized in {"degraded", "warning", "warn", "partial", "skipped"}:
        return "degraded"
    return "failed"


def _run_continuity_stage(
    module_slug: str, module_dir: Path, strict: bool
) -> Dict[str, Any]:
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

    changed = bool(continuity_patch.get("changed")) or bool(
        continuity_enrichment.get("changed")
    )
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


def _run_semantic_authority_stage(module_slug: str, module_dir: Path) -> Dict[str, Any]:
    """Run semantic-authority enrichment stage (non-blocking in this phase)."""
    context_path = module_dir / "module_context.json"
    plot_path = module_dir / "module_plot.json"

    if not context_path.exists() or not plot_path.exists():
        return {
            "status": "degraded",
            "reason": "Semantic authority stage skipped due to missing context/plot file",
            "context_path": str(context_path),
            "plot_path": str(plot_path),
            "semantic_authority": {},
            "warnings": ["semantic_authority_missing_context_or_plot"],
            "errors": [],
        }

    module_context = safe_read_json(str(context_path)) or {}
    module_plot = safe_read_json(str(plot_path)) or {}

    stage_result = enrich_module_semantic_authority(
        module_slug=module_slug,
        module_context=module_context,
        module_plot=module_plot,
        module_dir=module_dir,
    )

    if stage_result.get("changed"):
        write_ok = safe_write_json(
            str(context_path), stage_result.get("module_context") or module_context
        )
        if not write_ok:
            stage_result["status"] = "degraded"
            stage_result.setdefault("warnings", []).append(
                f"Failed to persist semantic authority payload to {context_path}"
            )

    if stage_result.get("status") == "failed":
        return {
            "status": "degraded",
            "reason": "Semantic authority enrichment reported failure (fail-open this phase)",
            "semantic_authority": stage_result.get("semantic_authority", {}),
            "warnings": stage_result.get("warnings", []),
            "errors": stage_result.get("errors", []),
        }

    return {
        "status": stage_result.get("status", "success"),
        "semantic_authority": stage_result.get("semantic_authority", {}),
        "warnings": stage_result.get("warnings", []),
        "errors": stage_result.get("errors", []),
    }


def _run_monster_materialization_stage(module_slug: str) -> Dict[str, Any]:
    """Run module-local monster materialization stage."""
    try:
        from scripts.homebrew_materialize_monsters import materialize_monsters

        parsed_output = materialize_monsters(
            module_slug=module_slug,
            strict=False,
            dry_run=False,
        )
    except Exception as mat_error:
        return {
            "status": "failed",
            "reason": f"Monster materialization invocation failed: {mat_error}",
        }

    blocked_count = int(parsed_output.get("blocked_count", 0) or 0)
    blocker_classes = parsed_output.get("blocker_classes") or {}
    parsed_status = _normalize_stage_status(parsed_output.get("status", "success"))
    if blocked_count > 0:
        stage_status = "failed"
    else:
        stage_status = parsed_status

    if stage_status == "failed":
        if blocked_count > 0:
            stage_reason = (
                "Monster hydration blocked by structured blocker classes: "
                f"{', '.join(sorted(blocker_classes.keys())) or 'unknown'}"
            )
        else:
            stage_reason = "Monster materialization reported failure"
    elif stage_status == "degraded":
        stage_reason = "Monster materialization completed with degraded status"
    else:
        stage_reason = None

    return {
        "status": stage_status,
        "reason": stage_reason,
        "returncode": 0,
        "parsed_output": parsed_output,
    }


def _detect_media_only_debt(publishability_stage: Dict[str, Any]) -> bool:
    """Detect if publishability gate failed only because media is missing.

    The finisher receives a wrapped stage payload from `_run_publishability_stage()`
    where the raw audit report is under `publishability_stage["report"]`.
    """
    if not isinstance(publishability_stage, dict):
        return False

    report = publishability_stage.get("report") or {}
    if not isinstance(report, dict):
        return False

    ready_status = str(
        publishability_stage.get("ready_status") or report.get("ready_status") or ""
    ).strip().lower()
    publishable_status = str(
        publishability_stage.get("publishable_status")
        or report.get("publishable_status")
        or ""
    ).strip().lower()
    if ready_status != "pass" or publishable_status != "fail":
        return False

    readiness_report = report.get("readiness") or {}
    if str(readiness_report.get("overall_status") or "").strip().lower() != "pass":
        return False

    categories = report.get("remediation_categories") or []
    if "structured_monster_media_missing" not in categories:
        return False
    if "mixed_media_semantic_blocking" in categories:
        return False
    if "semantic_publishability_blocking" in categories:
        return False

    blocking_errors = report.get("blocking_errors") or []
    if not blocking_errors:
        return True

    media_related_terms = ("media", "monster", "portrait", "image")
    return all(
        any(term in str(item or "").lower() for term in media_related_terms)
        for item in blocking_errors
    )


def _extract_media_debt_details(publishability_stage: Dict[str, Any]) -> Dict[str, Any]:
    """Extract missing media debt details for handoff reporting."""
    if not isinstance(publishability_stage, dict):
        return {}

    report = publishability_stage.get("report") or {}
    if not isinstance(report, dict):
        return {}

    toolkit_media_policy = report.get("toolkit_media_policy") or {}
    debt_slugs = toolkit_media_policy.get("structural_media_debt_slugs") or []
    normalized_slugs = [
        str(slug).strip()
        for slug in debt_slugs
        if str(slug or "").strip()
    ]
    media_debt_count = int(
        toolkit_media_policy.get("structural_media_debt_count") or len(normalized_slugs)
    )

    return {
        "media_debt_count": media_debt_count,
        "media_debt_slugs": normalized_slugs,
        "media_debt_workflow": (
            "Module Builder -> Module Media Generator"
        ),
        "media_debt_workflow_detail": (
            "Toolkit modules require manual monster portrait generation. "
            "Use: Module Builder -> Module Media Generator -> Generate Monster Images"
        ),
    }


def _run_publishability_stage(module_slug: str, source: str = "watcher") -> Dict[str, Any]:
    """Run standalone publishability audit stage."""
    from scripts.audit_module_publishability import audit_module_publishability

    report = audit_module_publishability(module_slug, source=source)
    ready_status = str(report.get("ready_status", "fail") or "fail")
    publishable_status = str(report.get("publishable_status", "fail") or "fail")

    if publishable_status == "pass":
        stage_status = "success"
    elif ready_status == "pass":
        stage_status = "degraded"
    else:
        stage_status = "failed"

    return {
        "status": stage_status,
        "ready_status": ready_status,
        "publishable_status": publishable_status,
        "source": source,
        "report": report,
    }


def run_toolkit_module_postbuild_finishing(
    module_slug: str, strict: bool = True
) -> Dict[str, Any]:
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

    continuity_stage = _run_continuity_stage(
        module_slug=module_slug, module_dir=module_dir, strict=strict
    )
    stages["continuity"] = continuity_stage
    if continuity_stage.get("status") == "failed":
        overall_status = "failed"
    elif continuity_stage.get("status") == "degraded":
        overall_status = "degraded"

    semantic_authority_stage = _run_semantic_authority_stage(
        module_slug=module_slug, module_dir=module_dir
    )
    stages["semantic_authority"] = semantic_authority_stage
    if (
        semantic_authority_stage.get("status") in {"failed", "degraded"}
        and overall_status != "failed"
    ):
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
    elif (
        materialization_stage.get("status") == "degraded" and overall_status != "failed"
    ):
        overall_status = "degraded"

    report_path = module_dir / "toolkit_build_report.json"

    def _build_report(
        *, status: str, ready_status: str, publishable_status: str, phase: str
    ) -> Dict[str, Any]:
        return {
            "generated_at": _utc_now_iso(),
            "module_slug": module_slug,
            "status": status,
            "ready_status": ready_status,
            "publishable_status": publishable_status,
            "strict": bool(strict),
            "source": "toolkit",
            "provenance": {
                "source": "toolkit",
                "artifact": "toolkit_build_report.json",
                "contract": "toolkit_build_report_required",
                "phase": phase,
            },
            "stages": stages,
            "publication_parity_note": (
                "Post-build parity now reports both structural readiness and semantic publishability."
            ),
            "semantic_authority_note": (
                "Semantic authority and semantic probes now feed a standalone publishable gate distinct from readiness."
            ),
        }

    # TABLETOP MODE: Persist toolkit provenance before toolkit-source readiness
    # and publishability checks so same-run toolkit audits can self-validate.
    pre_publishability_report = _build_report(
        status=overall_status,
        ready_status="pending",
        publishable_status="pending",
        phase="pre_publishability",
    )
    pre_write_ok = safe_write_json(str(report_path), pre_publishability_report)
    if not pre_write_ok:
        error(
            f"TOOLKIT_FINISHER: Failed to write pre-publishability report for {module_slug}",
            category="module_ingest",
        )
        stages["toolkit_provenance"] = {
            "status": "failed",
            "reason": "toolkit_provenance_write_failed",
            "report_path": str(report_path),
        }
        overall_status = "failed"
    else:
        stages["toolkit_provenance"] = {
            "status": "success",
            "reason": "toolkit_provenance_prepared",
            "report_path": str(report_path),
        }

    publishability_stage = _run_publishability_stage(
        module_slug=module_slug,
        source="toolkit",
    )
    stages["publishability"] = publishability_stage

    ready_status = str(publishability_stage.get("ready_status", "fail") or "fail")
    publishable_status = str(
        publishability_stage.get("publishable_status", "fail") or "fail"
    )

    if _detect_media_only_debt(publishability_stage):
        media_debt = _extract_media_debt_details(publishability_stage)
        stages["publishability"]["media_handoff"] = {
            "status": "media_only_debt",
            "build_outcome": "success_with_media_handoff",
            "message": (
                "Build completed successfully. Manual media generation required for "
                "monster portraits. Use: Module Builder -> Module Media Generator"
            ),
            "next_step": "Module Builder -> Module Media Generator",
            "next_step_detail": media_debt.get("media_debt_workflow_detail", ""),
            "media_debt_count": media_debt.get("media_debt_count", 0),
            "media_debt_slugs": media_debt.get("media_debt_slugs", []),
        }
        stages["publishability"]["status"] = "degraded"
        publishable_status = "fail_with_media_handoff"
        info(
            f"TOOLKIT_FINISHER: Media-only debt detected for {module_slug} - reporting success_with_media_handoff",
            category="module_ingest",
        )
    elif publishable_status == "fail":
        overall_status = "failed"
    elif publishability_stage.get("status") == "failed":
        overall_status = "failed"
    elif (
        publishability_stage.get("status") == "degraded" and overall_status != "failed"
    ):
        overall_status = "degraded"

    report = _build_report(
        status=overall_status,
        ready_status=ready_status,
        publishable_status=publishable_status,
        phase="final",
    )

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
