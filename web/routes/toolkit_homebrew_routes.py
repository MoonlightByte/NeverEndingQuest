# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Routes - Toolkit Homebrew source ingest routes.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

from utils.enhanced_logger import error, info, warning
from utils.file_operations import safe_write_json
from utils.toolkit_homebrew_pdf_adapter import (
    PdfConversionError,
    convert_pdf_upload_to_markdown,
)
from utils.toolkit_homebrew_normalizer import normalize_homebrew_upload
from utils.toolkit_homebrew_upload_contract import (
    REVIEW_DECISION_APPROVE,
    REVIEW_DECISION_REJECT,
    SOURCE_RIGHTS_USER_AUTHORED,
    VALID_SOURCE_RIGHTS_CLASSES,
    VALID_REVIEW_DECISIONS,
    build_review_snapshot,
    build_review_summary,
    ensure_workspace_placeholders,
    get_workspace_files,
    load_json_artifact,
    load_normalized_packet_artifact,
    normalize_review_decision,
    persist_review_snapshot_artifact,
    validate_review_packet,
    validate_normalization_artifacts,
)

from web.extensions.toolkit_homebrew_rebuild_guard import (
    detect_module_collision,
    prepare_backup_clean_rebuild,
)


_TERMINAL_JOB_STATES = {
    "completed",
    "not_publishable",
    "quarantined",
    "failed",
    "rejected",
    "awaiting_overwrite_confirmation",
}

_FINISHING_REACHABLE_STATES = {
    "ready_for_finishing",
    "finishing",
    "publishability_audit",
    "completed",
    "not_publishable",
    "quarantined",
    "failed",
}


def _build_artifact_manifest(workspace: Path, job_status: str) -> Dict[str, Any]:
    """Build artifact manifest dict for a toolkit Homebrew upload workspace."""
    workspace_files = get_workspace_files(workspace)

    artifact_keys = [
        "source_original",
        "source_upload_original_pdf",
        "pdf_conversion_report",
        "normalized_packet",
        "normalization_report",
        "ui_review_snapshot",
        "builder_input",
        "build_result",
        "readiness_validation_report",
        "readiness_audit_report",
        "repair_report",
        "finishing_report",
    ]

    artifacts: Dict[str, Any] = {}
    for key in artifact_keys:
        file_path = workspace_files.get(key)
        if file_path and file_path.exists():
            try:
                size = file_path.stat().st_size
            except OSError:
                size = None
            artifacts[key] = {
                "exists": True,
                "path": str(file_path),
                "size_bytes": size,
            }
        else:
            artifacts[key] = {"exists": False}

    normalized_exists = artifacts.get("normalized_packet", {}).get("exists", False)
    build_input_exists = artifacts.get("builder_input", {}).get("exists", False)
    build_result_exists = artifacts.get("build_result", {}).get("exists", False)
    finishing_report_exists = artifacts.get("finishing_report", {}).get("exists", False)

    rebuild_from_packet = bool(normalized_exists and job_status in _TERMINAL_JOB_STATES)

    rebuild_from_finishing = bool(
        build_input_exists
        and build_result_exists
        and job_status in _FINISHING_REACHABLE_STATES
    )

    cleanup_allowed = job_status in _TERMINAL_JOB_STATES

    return {
        "workspace": str(workspace),
        "artifacts": artifacts,
        "rebuild_eligible": {
            "from_packet": rebuild_from_packet,
            "from_finishing": rebuild_from_finishing,
        },
        "cleanup_allowed": cleanup_allowed,
    }


def _build_hydration_summary(job_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build normalized hydration diagnostics from readiness/finisher payloads."""
    summary: Dict[str, Any] = {
        "phase": "",
        "blocked_count": 0,
        "blocker_classes": {},
        "hydration_modes": {},
        "sample_monsters": [],
        "candidate_sources": {},
    }
    payload = job_payload if isinstance(job_payload, dict) else {}

    readiness_hydration = (
        payload.get("repair_attempts", [{}])[-1]
        .get("repairs", {})
        .get("monster_materialization", {})
        .get("hydration_result", {})
        if isinstance(payload.get("repair_attempts"), list)
        and payload.get("repair_attempts")
        else {}
    )

    finisher_hydration = (
        payload.get("stages", {})
        .get("monster_materialization", {})
        .get("parsed_output", {})
        if isinstance(payload.get("stages"), dict)
        else {}
    )

    hydration_payload = {}
    phase = ""
    if isinstance(finisher_hydration, dict) and finisher_hydration:
        hydration_payload = finisher_hydration
        phase = "finisher"
    elif isinstance(readiness_hydration, dict) and readiness_hydration:
        hydration_payload = readiness_hydration
        phase = "readiness"

    if not hydration_payload:
        return summary

    summary["phase"] = phase
    summary["blocked_count"] = int(hydration_payload.get("blocked_count", 0) or 0)

    blocker_classes = hydration_payload.get("blocker_classes")
    if isinstance(blocker_classes, dict):
        summary["blocker_classes"] = blocker_classes

    hydration_modes = hydration_payload.get("hydration_modes")
    if isinstance(hydration_modes, dict):
        summary["hydration_modes"] = hydration_modes

    candidate_sources = hydration_payload.get("candidate_sources")
    if isinstance(candidate_sources, dict):
        summary["candidate_sources"] = candidate_sources

    monster_results = hydration_payload.get("monster_results")
    if isinstance(monster_results, list):
        samples = []
        for item in monster_results[:5]:
            if not isinstance(item, dict):
                continue
            samples.append(
                {
                    "requested_name": str(item.get("requested_name") or ""),
                    "canonical_name": str(item.get("canonical_name") or ""),
                    "canonical_slug": str(item.get("canonical_slug") or ""),
                    "mode": str(item.get("mode") or ""),
                    "blocker_class": str(item.get("blocker_class") or ""),
                }
            )
        summary["sample_monsters"] = samples

    return summary


ALLOWED_HOME_BREW_EXTENSIONS = {".md", ".pdf"}
TOOLKIT_HOMEBREW_UPLOAD_ROOT = Path("user_uploads") / "toolkit" / "homebrew_md"
TOOLKIT_HOMEBREW_MAX_UPLOAD_BYTES = 20 * 1024 * 1024

_jobs_lock = threading.Lock()
_jobs: Dict[str, Dict[str, Any]] = {}
_active_job_id: Optional[str] = None


def reset_toolkit_homebrew_jobs_for_tests() -> None:
    """Reset in-memory toolkit Homebrew ingest job state (tests only)."""
    global _active_job_id
    with _jobs_lock:
        _jobs.clear()
        _active_job_id = None


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sanitize_filename(raw_name: str) -> str:
    """Return a safe basename without path traversal."""
    base_name = Path(str(raw_name or "")).name
    safe = "".join(
        ch for ch in base_name if ch.isalnum() or ch in {"_", "-", ".", " "}
    ).strip()
    return safe.replace(" ", "_")


def _set_job_state(job_id: str, status: str, **fields: Any) -> None:
    """Update one toolkit Homebrew ingest job state."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = status
        job["updated_at"] = _utc_now_iso()
        for key, value in fields.items():
            job[key] = value


def _normalize_homebrew_build_progress_stage(
    progress_status: str, progress_message: str
) -> str:
    """Map ModuleBuilder progress signals to stable toolkit stage labels."""
    status_text = f"{progress_status} {progress_message}".strip().lower()
    if "getting party members" in status_text or "initializing" in status_text:
        return "builder_initializing"
    if "directory structure" in status_text or "creating builder" in status_text:
        return "builder_setup"
    if "module overview" in status_text:
        return "builder_overview"
    if "generating areas" in status_text:
        return "builder_areas"
    if "generating locations" in status_text:
        return "builder_locations"
    if "finalizing location" in status_text or "connections" in status_text:
        return "builder_connections"
    if "generating plots" in status_text:
        return "builder_plots"
    if "unified module plot" in status_text:
        return "builder_plot_merge"
    if "plot hooks" in status_text:
        return "builder_plot_hooks"
    if "antagonist placement" in status_text:
        return "builder_antagonist"
    if "party tracker" in status_text:
        return "builder_party_tracker"
    if "module summary" in status_text:
        return "builder_summary"
    if "npc names" in status_text or "reconciling" in status_text:
        return "builder_reconciliation"
    if "validating module consistency" in status_text:
        return "builder_validation"
    if "backup files" in status_text:
        return "builder_backups"
    if "starting module build process" in status_text:
        return "builder_start"
    return "builder_progress"


def _update_homebrew_build_progress(
    job_id: str, progress_status: str, progress_message: str
) -> None:
    """Persist the latest packet-build progress milestone for polling UI."""
    message = str(progress_message or "").strip()
    if not message:
        return

    progress_stage = _normalize_homebrew_build_progress_stage(progress_status, message)
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "building"
        job["stage"] = "build"
        job["pipeline_status"] = "building"
        job["progress_message"] = message
        job["progress_stage"] = progress_stage
        job["progress_updated_at"] = _utc_now_iso()
        job["progress_tick"] = int(job.get("progress_tick") or 0) + 1
        job["updated_at"] = _utc_now_iso()


def _make_homebrew_build_progress_callback(job_id: str):
    """Create a fail-open callback for packet-build progress updates."""

    def _callback(progress_status: str, progress_message: str) -> None:
        try:
            _update_homebrew_build_progress(job_id, progress_status, progress_message)
        except Exception as progress_error:
            warning(
                (
                    f"TOOLKIT_HOMEBREW: Progress update failed for job {job_id}: "
                    f"{progress_error}"
                ),
                exception=progress_error,
                category="web_interface",
            )

    return _callback


def _extract_quarantine_reason(result: Dict[str, Any]) -> Optional[str]:
    """Extract best-effort quarantine reason from pipeline payload."""
    direct_reason = str(result.get("quarantine_reason") or "").strip()
    if direct_reason:
        return direct_reason

    nested_candidates = [
        result.get("dry_run", {}),
        result.get("ingest", {}),
        result.get("verify", {}),
        result.get("preflight", {}),
        result.get("transform", {}),
    ]
    for candidate in nested_candidates:
        if not isinstance(candidate, dict):
            continue
        reason = str(candidate.get("quarantine_reason") or "").strip()
        if reason:
            return reason

    return None


def _run_shared_ingest_pipeline(
    source_path: str,
    artifact_workspace: Optional[str] = None,
    source_rights_class: str = SOURCE_RIGHTS_USER_AUTHORED,
) -> Dict[str, Any]:
    """Invoke the shared Homebrew ingest orchestrator."""
    from scripts.homebrew_ingest_dev import run_ingest_pipeline

    return run_ingest_pipeline(
        source_path=source_path,
        strict=True,
        dry_run_only=False,
        cleanup_failed=True,
        no_media_extract=False,
        no_prewarm=False,
        media_timeout=30,
        allow_provider=False,
        allow_normalization_routing=True,
        artifact_workspace=artifact_workspace,
        source_rights_class=source_rights_class,
    )


def _run_homebrew_normalization(
    source_path: Path,
    artifact_workspace: Path,
    preflight: Dict[str, Any],
    source_rights_class: str,
) -> Dict[str, Any]:
    """Run toolkit Homebrew normalization stage for readable ambiguous uploads."""
    return normalize_homebrew_upload(
        source_path=source_path,
        workspace=artifact_workspace,
        preflight=preflight,
        source_rights_class=source_rights_class,
    )


def _run_homebrew_packet_build(
    artifact_workspace: Path,
    job_id: str,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run packet-driven builder for one approved toolkit Homebrew job."""
    from web.extensions.toolkit_homebrew_packet_builder import (
        run_toolkit_homebrew_packet_build,
    )

    return run_toolkit_homebrew_packet_build(
        workspace=artifact_workspace,
        job_id=job_id,
        progress_callback=progress_callback,
    )


def _run_homebrew_readiness_gate(
    artifact_workspace: Path,
    job_id: str,
    state_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run post-build structural readiness gate for one upload workspace."""
    from web.extensions.toolkit_homebrew_readiness_gate import (
        run_toolkit_homebrew_readiness_gate,
    )

    return run_toolkit_homebrew_readiness_gate(
        workspace=artifact_workspace,
        job_id=job_id,
        state_callback=state_callback,
    )


def _run_homebrew_finisher(module_slug: str) -> Dict[str, Any]:
    """Run shared toolkit finisher/publication stack for one module."""
    from web.extensions.toolkit_module_finisher import (
        refresh_toolkit_build_report,
    )

    return refresh_toolkit_build_report(
        module_slug,
        strict=True,
        refresh_reason="toolkit_homebrew_route_finisher",
    )


def _resolve_finisher_module_name(
    workspace: Path,
    readiness_result: Dict[str, Any],
    build_result: Dict[str, Any],
    expected_module_name: str,
) -> str:
    """Resolve module slug for finisher entry from job artifacts."""
    for candidate in (
        readiness_result.get("module_name"),
        readiness_result.get("module_slug"),
        build_result.get("module_name"),
        build_result.get("module_slug"),
        expected_module_name,
    ):
        module_name = str(candidate or "").strip()
        if module_name:
            return module_name

    target_info = _resolve_homebrew_build_target(workspace)
    if str(target_info.get("status") or "") == "success":
        return str(target_info.get("module_name") or "").strip()

    return ""


def _validate_finisher_entry(
    workspace: Path,
    module_name: str,
    build_result_path: str,
    readiness_validation_report_path: str,
    readiness_audit_report_path: str,
) -> Dict[str, Any]:
    """Validate uploader finisher entry prerequisites."""
    if not workspace.exists() or not workspace.is_dir():
        return {
            "ok": False,
            "error": "artifact_workspace_missing",
            "workspace": str(workspace),
        }

    module_slug = str(module_name or "").strip()
    if not module_slug:
        return {
            "ok": False,
            "error": "module_slug_missing",
            "workspace": str(workspace),
        }

    workspace_files = get_workspace_files(workspace)
    build_path = Path(
        str(build_result_path or "").strip() or str(workspace_files["build_result"])
    )
    readiness_validation_path = Path(
        str(readiness_validation_report_path or "").strip()
        or str(workspace_files["readiness_validation_report"])
    )
    readiness_audit_path = Path(
        str(readiness_audit_report_path or "").strip()
        or str(workspace_files["readiness_audit_report"])
    )

    missing = []
    if not build_path.exists():
        missing.append("build_result")
    if not readiness_validation_path.exists():
        missing.append("readiness_validation_report")
    if not readiness_audit_path.exists():
        missing.append("readiness_audit_report")

    if missing:
        return {
            "ok": False,
            "error": "finisher_entry_prerequisites_missing",
            "missing": missing,
            "workspace": str(workspace),
            "module_name": module_slug,
        }

    return {
        "ok": True,
        "module_name": module_slug,
        "build_result_path": str(build_path),
        "readiness_validation_report_path": str(readiness_validation_path),
        "readiness_audit_report_path": str(readiness_audit_path),
        "finishing_report_path": str(workspace_files["finishing_report"]),
    }


def _resolve_homebrew_build_target(artifact_workspace: Path) -> Dict[str, Any]:
    """Resolve packet-derived module target and collision metadata."""
    from web.extensions.toolkit_homebrew_packet_builder import derive_packet_module_name

    packet = load_normalized_packet_artifact(artifact_workspace)
    packet_valid, packet_error = validate_review_packet(packet)
    if not packet_valid:
        return {
            "status": "failed",
            "error": f"normalized_packet_invalid:{packet_error}",
        }

    module_name = derive_packet_module_name(packet)
    if not module_name:
        return {
            "status": "failed",
            "error": "module_name_unresolved",
        }

    collision = detect_module_collision(module_name)
    return {
        "status": "success",
        "module_name": module_name,
        "collision": collision,
    }


def _prepare_homebrew_rebuild_target(
    module_name: str, overwrite_policy: str
) -> Dict[str, Any]:
    """Prepare backup+clean rebuild target for confirmed repeated uploads."""
    return prepare_backup_clean_rebuild(
        module_name=module_name,
        overwrite_policy=overwrite_policy,
    )


def _run_homebrew_ingest_job(
    job_id: str,
    source_path: Path,
    artifact_workspace: Path,
    source_rights_class: str,
) -> None:
    """Run one toolkit Homebrew ingest job in background."""
    global _active_job_id

    try:
        _set_job_state(job_id, "running", stage="preflight")

        _set_job_state(job_id, "running", stage="pipeline")
        result = _run_shared_ingest_pipeline(
            str(source_path),
            artifact_workspace=str(artifact_workspace),
            source_rights_class=source_rights_class,
        )

        pipeline_status = str(result.get("status") or "failed")
        pipeline_stage = str(result.get("stage") or "unknown")
        quarantine_reason = _extract_quarantine_reason(result)

        if pipeline_status == "normalization_required":
            # TABLETOP MODE: Run explicit normalization stage before review gate.
            _set_job_state(
                job_id,
                "running",
                stage="normalizing",
                pipeline_status="normalizing",
                routing_outcome=str(
                    result.get("routing_outcome") or "normalization_required"
                ),
                quarantine_reason=None,
            )

            normalization_result = _run_homebrew_normalization(
                source_path=source_path,
                artifact_workspace=artifact_workspace,
                preflight=result.get("preflight") or {},
                source_rights_class=source_rights_class,
            )

            if normalization_result.get("status") != "success":
                _set_job_state(
                    job_id,
                    "failed",
                    stage="normalizing",
                    pipeline_status="failed",
                    quarantine_reason=None,
                    result={
                        "routing": result,
                        "normalization": normalization_result,
                    },
                )
                return

            artifacts_valid, artifacts_error = validate_normalization_artifacts(
                artifact_workspace
            )
            if not artifacts_valid:
                _set_job_state(
                    job_id,
                    "failed",
                    stage="normalizing",
                    pipeline_status="failed",
                    quarantine_reason=None,
                    result={
                        "routing": result,
                        "normalization": normalization_result,
                        "normalization_validation": {
                            "status": "failed",
                            "error": artifacts_error,
                        },
                    },
                )
                return

            auto_build_result: Dict[str, Any] = {
                "routing": result,
                "normalization": normalization_result,
            }
            routing_outcome = str(
                result.get("routing_outcome") or "normalization_required"
            )

            # TABLETOP MODE: Preserve review snapshot artifact compatibility even though
            # upload now auto-approves and auto-starts packet build.
            snapshot = build_review_snapshot(
                job_id=job_id,
                decision=REVIEW_DECISION_APPROVE,
                packet=load_normalized_packet_artifact(artifact_workspace),
                source_rights_class=source_rights_class,
            )
            if persist_review_snapshot_artifact(artifact_workspace, snapshot):
                auto_build_result["auto_review_snapshot"] = snapshot
                workspace_files = get_workspace_files(artifact_workspace)
                _set_job_state(
                    job_id,
                    "approved_for_build",
                    stage="build",
                    pipeline_status="normalization_ready",
                    routing_outcome=routing_outcome,
                    review_decision=REVIEW_DECISION_APPROVE,
                    review_snapshot=snapshot,
                    review_snapshot_path=str(workspace_files["ui_review_snapshot"]),
                    quarantine_reason=None,
                    result=auto_build_result,
                )
            else:
                warning(
                    f"TOOLKIT_HOMEBREW: Failed to persist review snapshot for job {job_id}; proceeding with auto-build",
                    category="web_interface",
                )
                _set_job_state(
                    job_id,
                    "approved_for_build",
                    stage="build",
                    pipeline_status="normalization_ready",
                    routing_outcome=routing_outcome,
                    review_decision=REVIEW_DECISION_APPROVE,
                    quarantine_reason=None,
                    result=auto_build_result,
                )

            target_info = _resolve_homebrew_build_target(artifact_workspace)
            if target_info.get("status") != "success":
                _set_job_state(
                    job_id,
                    "failed",
                    stage="build",
                    pipeline_status="failed",
                    routing_outcome=routing_outcome,
                    quarantine_reason=None,
                    error="build_target_resolution_failed",
                    result={
                        **auto_build_result,
                        "build_target": target_info,
                    },
                )
                return

            module_name = str(target_info.get("module_name") or "").strip()
            collision = (
                target_info.get("collision")
                if isinstance(target_info.get("collision"), dict)
                else {}
            )
            module_dir_exists = bool((collision or {}).get("module_dir_exists"))
            if module_dir_exists:
                _set_job_state(
                    job_id,
                    "awaiting_overwrite_confirmation",
                    stage="build",
                    pipeline_status="awaiting_confirmation",
                    routing_outcome=routing_outcome,
                    review_decision=REVIEW_DECISION_APPROVE,
                    expected_module_name=module_name,
                    rebuild_mode=True,
                    rebuild_collision=collision,
                    quarantine_reason=None,
                    result={
                        **auto_build_result,
                        "build_target": target_info,
                    },
                )
                return

            build_options = {
                "finishing_only": False,
                "rebuild_mode": False,
                "module_name": module_name,
                "module_dir": str((collision or {}).get("module_dir") or ""),
                "overwrite_policy": "backup_clean",
            }
            _set_job_state(
                job_id,
                "building",
                stage="build",
                pipeline_status="building",
                routing_outcome=routing_outcome,
                review_decision=REVIEW_DECISION_APPROVE,
                expected_module_name=module_name,
                rebuild_mode=False,
                rebuild_collision=collision,
                overwrite_policy="backup_clean",
                build_started_at=_utc_now_iso(),
                quarantine_reason=None,
                result={
                    **auto_build_result,
                    "build_target": target_info,
                },
            )
            _run_homebrew_build_job(job_id, build_options)
            return

        if pipeline_status in {"success", "degraded"}:
            _set_job_state(
                job_id,
                "completed",
                stage=pipeline_stage,
                pipeline_status=pipeline_status,
                quarantine_reason=None,
                result=result,
            )
            return

        if quarantine_reason:
            _set_job_state(
                job_id,
                "quarantined",
                stage=pipeline_stage,
                pipeline_status=pipeline_status,
                quarantine_reason=quarantine_reason,
                result=result,
            )
            return

        _set_job_state(
            job_id,
            "failed",
            stage=pipeline_stage,
            pipeline_status=pipeline_status,
            quarantine_reason=None,
            result=result,
        )

    except Exception as job_error:
        error(
            f"TOOLKIT_HOMEBREW: Ingest job {job_id} failed: {job_error}",
            exception=job_error,
            category="web_interface",
        )
        _set_job_state(
            job_id,
            "failed",
            stage="pipeline",
            pipeline_status="failed",
            quarantine_reason=None,
            error=str(job_error),
        )
    finally:
        with _jobs_lock:
            if _active_job_id == job_id:
                _active_job_id = None


def _run_homebrew_build_job(
    job_id: str, build_options: Optional[Dict[str, Any]] = None
) -> None:
    """Run packet-driven build for one approved toolkit Homebrew job."""
    global _active_job_id

    workspace = None
    build_opts = dict(build_options or {})
    rebuild_prep_result: Dict[str, Any] = {}
    finishing_only = bool(build_opts.get("finishing_only"))
    try:
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return
            workspace_raw = str(job.get("artifact_workspace") or "").strip()
            if not workspace_raw:
                job["status"] = "failed"
                job["stage"] = "build"
                job["pipeline_status"] = "failed"
                job["result"] = {
                    "status": "failed",
                    "stage": "build",
                    "error": "artifact_workspace_missing",
                    "job_id": job_id,
                }
                job["updated_at"] = _utc_now_iso()
                return
            workspace = Path(workspace_raw)

        workspace_files = get_workspace_files(workspace)

        if finishing_only:
            with _jobs_lock:
                job = _jobs.get(job_id) or {}
                current_status = str(job.get("status") or "")
                if current_status not in {"ready_for_finishing", "finishing"}:
                    invalid_state = {
                        "status": "failed",
                        "stage": "finishing",
                        "job_id": job_id,
                        "error": "finisher_entry_state_invalid",
                        "expected_status": "ready_for_finishing",
                        "actual_status": current_status,
                    }
                else:
                    invalid_state = {}

                prior_result = (
                    job.get("result") if isinstance(job.get("result"), dict) else {}
                )
                expected_module_name = str(
                    job.get("expected_module_name") or ""
                ).strip()
                build_result_path = str(job.get("build_result_path") or "")
                readiness_validation_report_path = str(
                    job.get("readiness_validation_report_path") or ""
                )
                readiness_audit_report_path = str(
                    job.get("readiness_audit_report_path") or ""
                )

            if invalid_state:
                _set_job_state(
                    job_id,
                    "finishing_failed",
                    stage="finishing",
                    pipeline_status="failed",
                    error="finisher_entry_state_invalid",
                    result=invalid_state,
                )
                return

            finisher_module_name = _resolve_finisher_module_name(
                workspace=workspace,
                readiness_result=prior_result,
                build_result={},
                expected_module_name=expected_module_name,
            )
            finisher_entry = _validate_finisher_entry(
                workspace=workspace,
                module_name=finisher_module_name,
                build_result_path=build_result_path,
                readiness_validation_report_path=readiness_validation_report_path,
                readiness_audit_report_path=readiness_audit_report_path,
            )
            if not bool(finisher_entry.get("ok")):
                _set_job_state(
                    job_id,
                    "finishing_failed",
                    stage="finishing",
                    pipeline_status="failed",
                    error=str(
                        finisher_entry.get("error")
                        or "finisher_entry_prerequisites_missing"
                    ),
                    result={
                        "status": "failed",
                        "stage": "finishing",
                        "job_id": job_id,
                        "error": str(
                            finisher_entry.get("error")
                            or "finisher_entry_prerequisites_missing"
                        ),
                        "details": finisher_entry,
                    },
                )
                return

            _set_job_state(
                job_id,
                "finishing",
                stage="finishing",
                pipeline_status="finishing",
                result={
                    "status": "running",
                    "stage": "finishing",
                    "job_id": job_id,
                    "module_name": finisher_entry.get("module_name"),
                },
            )

            try:
                finishing_report = _run_homebrew_finisher(
                    str(finisher_entry.get("module_name") or "")
                )
            except Exception as finisher_error:
                _set_job_state(
                    job_id,
                    "finishing_failed",
                    stage="finishing",
                    pipeline_status="failed",
                    error=str(finisher_error),
                    result={
                        "status": "failed",
                        "stage": "finishing",
                        "job_id": job_id,
                        "error": str(finisher_error),
                    },
                )
                return

            safe_write_json(
                str(finisher_entry.get("finishing_report_path") or ""), finishing_report
            )

            _set_job_state(
                job_id,
                "publishability_audit",
                stage="finishing",
                pipeline_status="publishability_audit",
                result=finishing_report,
                finishing_report_path=str(
                    finisher_entry.get("finishing_report_path") or ""
                ),
                module_name=str(finisher_entry.get("module_name") or ""),
            )

            ready_status = (
                str(finishing_report.get("ready_status") or "fail").strip().lower()
            )
            publishable_status = (
                str(finishing_report.get("publishable_status") or "fail")
                .strip()
                .lower()
            )
            final_status = (
                str(finishing_report.get("status") or "failed").strip().lower()
            )

            if ready_status == "pass" and publishable_status == "pass":
                _set_job_state(
                    job_id,
                    "completed",
                    stage="finishing",
                    pipeline_status="success",
                    result=finishing_report,
                    finishing_report_path=str(
                        finisher_entry.get("finishing_report_path") or ""
                    ),
                    module_name=str(finisher_entry.get("module_name") or ""),
                )
                return

            if ready_status == "pass" and publishable_status != "pass":
                _set_job_state(
                    job_id,
                    "not_publishable",
                    stage="finishing",
                    pipeline_status="blocked",
                    result=finishing_report,
                    finishing_report_path=str(
                        finisher_entry.get("finishing_report_path") or ""
                    ),
                    module_name=str(finisher_entry.get("module_name") or ""),
                )
                return

            _set_job_state(
                job_id,
                "finishing_failed",
                stage="finishing",
                pipeline_status="failed",
                error=str(
                    finishing_report.get("reason") or final_status or "finisher_failed"
                ),
                result=finishing_report,
                finishing_report_path=str(
                    finisher_entry.get("finishing_report_path") or ""
                ),
                module_name=str(finisher_entry.get("module_name") or ""),
            )
            return

        rebuild_mode = bool(build_opts.get("rebuild_mode"))
        build_progress_callback = _make_homebrew_build_progress_callback(job_id)
        if rebuild_mode:
            rebuild_module_name = str(build_opts.get("module_name") or "").strip()
            overwrite_policy = (
                str(build_opts.get("overwrite_policy") or "backup_clean")
                .strip()
                .lower()
            )

            _set_job_state(
                job_id,
                "rebuild_backup_running",
                stage="build",
                pipeline_status="rebuild_backup",
                result={
                    "status": "rebuild_backup_running",
                    "stage": "build",
                    "job_id": job_id,
                    "module_name": rebuild_module_name,
                    "overwrite_policy": overwrite_policy,
                },
            )

            rebuild_prep_result = _prepare_homebrew_rebuild_target(
                module_name=rebuild_module_name,
                overwrite_policy=overwrite_policy,
            )

            prep_status = str(
                rebuild_prep_result.get("status") or "rebuild_prepare_failed"
            )
            if prep_status != "success":
                _set_job_state(
                    job_id,
                    prep_status,
                    stage="build",
                    pipeline_status="failed",
                    result=rebuild_prep_result,
                    error=str(
                        rebuild_prep_result.get("error")
                        or rebuild_prep_result.get("reason")
                        or prep_status
                    ),
                )
                return

        if rebuild_prep_result:
            initial_progress_message = "Rebuild preparation complete. Continuing packet build."
            initial_progress_stage = "builder_handoff"
        else:
            initial_progress_message = "Packet-driven Homebrew build in progress."
            initial_progress_stage = "builder_start"

        initial_progress_fields: Dict[str, Any] = {
            "pipeline_status": "building",
            "progress_message": initial_progress_message,
            "progress_stage": initial_progress_stage,
            "progress_updated_at": _utc_now_iso(),
            "progress_tick": 0,
        }
        if rebuild_prep_result:
            initial_progress_fields["result"] = rebuild_prep_result
            initial_progress_fields["rebuild_backup_path"] = str(
                rebuild_prep_result.get("backup_dir") or ""
            )
            initial_progress_fields["rebuild_mode"] = True

        _set_job_state(job_id, "building", stage="build", **initial_progress_fields)

        build_result = _run_homebrew_packet_build(
            workspace,
            job_id,
            progress_callback=build_progress_callback,
        )
        build_status = str(build_result.get("status") or "failed").lower()
        if rebuild_prep_result:
            build_result["rebuild"] = rebuild_prep_result

        if build_status == "success":
            _set_job_state(
                job_id,
                "build_completed",
                stage="build",
                pipeline_status="success",
                result=build_result,
                build_result_path=str(workspace_files["build_result"]),
                rebuild_mode=bool(build_opts.get("rebuild_mode")),
                rebuild_backup_path=str(rebuild_prep_result.get("backup_dir") or ""),
            )

            def _readiness_state_callback(status: str, payload: Dict[str, Any]) -> None:
                _set_job_state(
                    job_id,
                    status,
                    stage="readiness",
                    pipeline_status=status,
                    result={
                        "status": status,
                        "stage": "readiness",
                        "job_id": job_id,
                        "payload": payload or {},
                    },
                    build_result_path=str(workspace_files["build_result"]),
                )

            readiness_result = _run_homebrew_readiness_gate(
                artifact_workspace=workspace,
                job_id=job_id,
                state_callback=_readiness_state_callback,
            )

            readiness_status = str(
                readiness_result.get("status") or "repair_budget_exhausted"
            )
            final_pipeline_status = (
                "success" if readiness_status == "ready_for_finishing" else "failed"
            )
            _set_job_state(
                job_id,
                readiness_status,
                stage="readiness",
                pipeline_status=final_pipeline_status,
                result=readiness_result,
                build_result_path=str(workspace_files["build_result"]),
                readiness_validation_report_path=str(
                    workspace_files["readiness_validation_report"]
                ),
                readiness_audit_report_path=str(
                    workspace_files["readiness_audit_report"]
                ),
                repair_report_path=str(workspace_files["repair_report"]),
                rebuild_mode=bool(build_opts.get("rebuild_mode")),
                rebuild_backup_path=str(rebuild_prep_result.get("backup_dir") or ""),
            )

            if readiness_status != "ready_for_finishing":
                return

            module_name = _resolve_finisher_module_name(
                workspace=workspace,
                readiness_result=readiness_result,
                build_result=build_result,
                expected_module_name=str(build_opts.get("module_name") or ""),
            )
            finisher_entry = _validate_finisher_entry(
                workspace=workspace,
                module_name=module_name,
                build_result_path=str(workspace_files["build_result"]),
                readiness_validation_report_path=str(
                    workspace_files["readiness_validation_report"]
                ),
                readiness_audit_report_path=str(
                    workspace_files["readiness_audit_report"]
                ),
            )
            if not bool(finisher_entry.get("ok")):
                _set_job_state(
                    job_id,
                    "finishing_failed",
                    stage="finishing",
                    pipeline_status="failed",
                    error=str(
                        finisher_entry.get("error")
                        or "finisher_entry_prerequisites_missing"
                    ),
                    result={
                        "status": "failed",
                        "stage": "finishing",
                        "job_id": job_id,
                        "error": str(
                            finisher_entry.get("error")
                            or "finisher_entry_prerequisites_missing"
                        ),
                        "details": finisher_entry,
                    },
                    build_result_path=str(workspace_files["build_result"]),
                    readiness_validation_report_path=str(
                        workspace_files["readiness_validation_report"]
                    ),
                    readiness_audit_report_path=str(
                        workspace_files["readiness_audit_report"]
                    ),
                    rebuild_mode=bool(build_opts.get("rebuild_mode")),
                    rebuild_backup_path=str(
                        rebuild_prep_result.get("backup_dir") or ""
                    ),
                )
                return

            _set_job_state(
                job_id,
                "finishing",
                stage="finishing",
                pipeline_status="finishing",
                result={
                    "status": "running",
                    "stage": "finishing",
                    "job_id": job_id,
                    "module_name": finisher_entry.get("module_name"),
                },
                build_result_path=str(workspace_files["build_result"]),
                readiness_validation_report_path=str(
                    workspace_files["readiness_validation_report"]
                ),
                readiness_audit_report_path=str(
                    workspace_files["readiness_audit_report"]
                ),
                rebuild_mode=bool(build_opts.get("rebuild_mode")),
                rebuild_backup_path=str(rebuild_prep_result.get("backup_dir") or ""),
            )

            try:
                finishing_report = _run_homebrew_finisher(
                    str(finisher_entry.get("module_name") or "")
                )
            except Exception as finisher_error:
                _set_job_state(
                    job_id,
                    "finishing_failed",
                    stage="finishing",
                    pipeline_status="failed",
                    error=str(finisher_error),
                    result={
                        "status": "failed",
                        "stage": "finishing",
                        "job_id": job_id,
                        "error": str(finisher_error),
                    },
                    build_result_path=str(workspace_files["build_result"]),
                    readiness_validation_report_path=str(
                        workspace_files["readiness_validation_report"]
                    ),
                    readiness_audit_report_path=str(
                        workspace_files["readiness_audit_report"]
                    ),
                    rebuild_mode=bool(build_opts.get("rebuild_mode")),
                    rebuild_backup_path=str(
                        rebuild_prep_result.get("backup_dir") or ""
                    ),
                )
                return

            safe_write_json(
                str(finisher_entry.get("finishing_report_path") or ""), finishing_report
            )

            _set_job_state(
                job_id,
                "publishability_audit",
                stage="finishing",
                pipeline_status="publishability_audit",
                result=finishing_report,
                build_result_path=str(workspace_files["build_result"]),
                readiness_validation_report_path=str(
                    workspace_files["readiness_validation_report"]
                ),
                readiness_audit_report_path=str(
                    workspace_files["readiness_audit_report"]
                ),
                finishing_report_path=str(
                    finisher_entry.get("finishing_report_path") or ""
                ),
                rebuild_mode=bool(build_opts.get("rebuild_mode")),
                rebuild_backup_path=str(rebuild_prep_result.get("backup_dir") or ""),
            )

            ready_status = (
                str(finishing_report.get("ready_status") or "fail").strip().lower()
            )
            publishable_status = (
                str(finishing_report.get("publishable_status") or "fail")
                .strip()
                .lower()
            )
            final_status = (
                str(finishing_report.get("status") or "failed").strip().lower()
            )

            if ready_status == "pass" and publishable_status == "pass":
                _set_job_state(
                    job_id,
                    "completed",
                    stage="finishing",
                    pipeline_status="success",
                    result=finishing_report,
                    build_result_path=str(workspace_files["build_result"]),
                    readiness_validation_report_path=str(
                        workspace_files["readiness_validation_report"]
                    ),
                    readiness_audit_report_path=str(
                        workspace_files["readiness_audit_report"]
                    ),
                    finishing_report_path=str(
                        finisher_entry.get("finishing_report_path") or ""
                    ),
                    rebuild_mode=bool(build_opts.get("rebuild_mode")),
                    rebuild_backup_path=str(
                        rebuild_prep_result.get("backup_dir") or ""
                    ),
                )
                return

            if ready_status == "pass" and publishable_status != "pass":
                _set_job_state(
                    job_id,
                    "not_publishable",
                    stage="finishing",
                    pipeline_status="blocked",
                    result=finishing_report,
                    build_result_path=str(workspace_files["build_result"]),
                    readiness_validation_report_path=str(
                        workspace_files["readiness_validation_report"]
                    ),
                    readiness_audit_report_path=str(
                        workspace_files["readiness_audit_report"]
                    ),
                    finishing_report_path=str(
                        finisher_entry.get("finishing_report_path") or ""
                    ),
                    rebuild_mode=bool(build_opts.get("rebuild_mode")),
                    rebuild_backup_path=str(
                        rebuild_prep_result.get("backup_dir") or ""
                    ),
                )
                return

            _set_job_state(
                job_id,
                "finishing_failed",
                stage="finishing",
                pipeline_status="failed",
                error=str(
                    finishing_report.get("reason") or final_status or "finisher_failed"
                ),
                result=finishing_report,
                build_result_path=str(workspace_files["build_result"]),
                readiness_validation_report_path=str(
                    workspace_files["readiness_validation_report"]
                ),
                readiness_audit_report_path=str(
                    workspace_files["readiness_audit_report"]
                ),
                finishing_report_path=str(
                    finisher_entry.get("finishing_report_path") or ""
                ),
                rebuild_mode=bool(build_opts.get("rebuild_mode")),
                rebuild_backup_path=str(rebuild_prep_result.get("backup_dir") or ""),
            )
            return

        _set_job_state(
            job_id,
            "failed",
            stage="build",
            pipeline_status="failed",
            result=build_result,
            error=str(build_result.get("error") or "packet_build_failed"),
            build_result_path=str(workspace_files["build_result"]),
            rebuild_mode=bool(build_opts.get("rebuild_mode")),
            rebuild_backup_path=str(rebuild_prep_result.get("backup_dir") or ""),
        )
    except Exception as build_error:
        error(
            f"TOOLKIT_HOMEBREW: Build job {job_id} failed: {build_error}",
            exception=build_error,
            category="web_interface",
        )
        failed_status = "finishing_failed" if finishing_only else "failed"
        failed_stage = "finishing" if finishing_only else "build"
        _set_job_state(
            job_id,
            failed_status,
            stage=failed_stage,
            pipeline_status="failed",
            error=str(build_error),
            result={
                "status": "failed",
                "stage": failed_stage,
                "error": str(build_error),
                "job_id": job_id,
            },
        )
    finally:
        with _jobs_lock:
            if _active_job_id == job_id:
                _active_job_id = None


def register_toolkit_homebrew_routes(app: Flask) -> None:
    """Register toolkit Homebrew source upload and job-status routes."""

    @app.route("/api/toolkit/homebrew/upload", methods=["POST"])
    def upload_toolkit_homebrew_markdown() -> Any:
        """Upload one Homebrew source file and start ingest job."""
        global _active_job_id

        try:
            with _jobs_lock:
                if _active_job_id is not None:
                    return jsonify(
                        {
                            "status": "error",
                            "message": "Another Homebrew ingest job is already running",
                            "active_job_id": _active_job_id,
                        }
                    ), 409

            incoming = request.files.get("file")
            if incoming is None:
                return jsonify(
                    {"status": "error", "message": "Missing file field"}
                ), 400

            safe_name = _sanitize_filename(str(incoming.filename or ""))
            if not safe_name:
                return jsonify({"status": "error", "message": "Invalid filename"}), 400

            extension = Path(safe_name).suffix.lower()
            if extension not in ALLOWED_HOME_BREW_EXTENSIONS:
                return jsonify(
                    {
                        "status": "error",
                        "message": "File type not allowed. Upload a .md or .pdf file.",
                        "allowed_extensions": sorted(ALLOWED_HOME_BREW_EXTENSIONS),
                    }
                ), 400

            TOOLKIT_HOMEBREW_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

            job_id = str(uuid.uuid4())
            workspace = TOOLKIT_HOMEBREW_UPLOAD_ROOT / job_id
            ensure_workspace_placeholders(workspace)
            workspace_files = get_workspace_files(workspace)
            destination = workspace_files["source_original"]
            source_kind = "markdown"
            raw_pdf_path = None
            pdf_conversion_report = None

            if extension == ".pdf":
                source_kind = "pdf"
                raw_pdf_path = workspace_files["source_upload_original_pdf"]
                incoming.save(str(raw_pdf_path))

                raw_pdf_size = raw_pdf_path.stat().st_size
                if raw_pdf_size > TOOLKIT_HOMEBREW_MAX_UPLOAD_BYTES:
                    raw_pdf_path.unlink(missing_ok=True)
                    return jsonify(
                        {
                            "status": "error",
                            "message": "File exceeds max upload size",
                            "max_bytes": TOOLKIT_HOMEBREW_MAX_UPLOAD_BYTES,
                        }
                    ), 400

                try:
                    pdf_conversion_report = convert_pdf_upload_to_markdown(
                        raw_pdf_path,
                        destination,
                        source_filename=safe_name,
                    )
                except PdfConversionError as conversion_error:
                    pdf_conversion_report = dict(getattr(conversion_error, "report", {}) or {})
                    report_path = workspace_files["pdf_conversion_report"]
                    if pdf_conversion_report:
                        if not safe_write_json(str(report_path), pdf_conversion_report):
                            warning(
                                (
                                    f"TOOLKIT_HOMEBREW: Failed to persist PDF conversion report for job {job_id}"
                                ),
                                category="web_interface",
                            )
                    return jsonify(
                        {
                            "status": "error",
                            "message": str(conversion_error),
                            "allowed_extensions": sorted(ALLOWED_HOME_BREW_EXTENSIONS),
                            "pdf_conversion_report": pdf_conversion_report,
                        }
                    ), 400
                if pdf_conversion_report and not safe_write_json(
                    str(workspace_files["pdf_conversion_report"]), pdf_conversion_report
                ):
                    warning(
                        (
                            f"TOOLKIT_HOMEBREW: Failed to persist PDF conversion report for job {job_id}"
                        ),
                        category="web_interface",
                    )
            else:
                incoming.save(str(destination))

            raw_rights = str(request.form.get("source_rights_class") or "").strip()
            source_rights_class = raw_rights or SOURCE_RIGHTS_USER_AUTHORED
            if source_rights_class not in VALID_SOURCE_RIGHTS_CLASSES:
                source_rights_class = SOURCE_RIGHTS_USER_AUTHORED

            size_bytes = raw_pdf_path.stat().st_size if raw_pdf_path else destination.stat().st_size
            if size_bytes > TOOLKIT_HOMEBREW_MAX_UPLOAD_BYTES:
                if raw_pdf_path:
                    raw_pdf_path.unlink(missing_ok=True)
                    destination.unlink(missing_ok=True)
                    workspace_files["pdf_conversion_report"].unlink(missing_ok=True)
                else:
                    destination.unlink(missing_ok=True)
                return jsonify(
                    {
                        "status": "error",
                        "message": "File exceeds max upload size",
                        "max_bytes": TOOLKIT_HOMEBREW_MAX_UPLOAD_BYTES,
                    }
                ), 400

            with _jobs_lock:
                _active_job_id = job_id
                _jobs[job_id] = {
                    "job_id": job_id,
                    "job_type": "toolkit_homebrew_md_ingest",
                    "status": "queued",
                    "stage": "queued",
                    "pipeline_status": None,
                    "quarantine_reason": None,
                    "review_decision": None,
                    "created_at": _utc_now_iso(),
                    "updated_at": _utc_now_iso(),
                    "source_path": str(destination),
                    "source_kind": source_kind,
                    "source_filename": safe_name,
                    "source_original_path": str(destination),
                    "source_upload_path": str(raw_pdf_path or destination),
                    "pdf_conversion_report_path": str(workspace_files["pdf_conversion_report"])
                    if raw_pdf_path
                    else None,
                    "pdf_conversion_report": pdf_conversion_report,
                    "artifact_workspace": str(workspace),
                    "source_rights_class": source_rights_class,
                    "size_bytes": size_bytes,
                    "allowed_extensions": sorted(ALLOWED_HOME_BREW_EXTENSIONS),
                }

            worker = threading.Thread(
                target=_run_homebrew_ingest_job,
                args=(job_id, destination, workspace, source_rights_class),
                daemon=True,
                name=f"ToolkitHomebrewIngest-{job_id[:8]}",
            )
            worker.start()

            info(
                (
                    f"TOOLKIT_HOMEBREW: Started {source_kind} ingest job {job_id} for {safe_name}"
                ),
                category="web_interface",
            )
            return jsonify(
                {
                    "status": "success",
                    "job_id": job_id,
                    "allowed_extensions": sorted(ALLOWED_HOME_BREW_EXTENSIONS),
                    "size_bytes": size_bytes,
                    "source_kind": source_kind,
                    "source_path": str(destination),
                    "source_upload_path": str(raw_pdf_path or destination),
                    "pdf_conversion_report_path": str(workspace_files["pdf_conversion_report"])
                    if raw_pdf_path
                    else None,
                }
            )

        except Exception as route_error:
            error(
                f"TOOLKIT_HOMEBREW: Upload failed: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            return jsonify({"status": "error", "message": str(route_error)}), 500

    @app.route("/api/toolkit/homebrew/jobs/<job_id>/review", methods=["GET"])
    def get_toolkit_homebrew_job_review(job_id: str) -> Any:
        """Get review summary payload for one toolkit Homebrew upload job."""
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            job_copy = dict(job)

        workspace_raw = str(job_copy.get("artifact_workspace") or "").strip()
        if not workspace_raw:
            return jsonify(
                {
                    "status": "error",
                    "message": "Job is missing artifact workspace metadata",
                }
            ), 409

        workspace = Path(workspace_raw)
        packet = load_normalized_packet_artifact(workspace)
        packet_valid, packet_error = validate_review_packet(packet)
        if not packet_valid:
            return jsonify(
                {
                    "status": "error",
                    "message": "Review packet unavailable or invalid",
                    "packet_error": packet_error,
                    "job": job_copy,
                }
            ), 409

        workspace_files = get_workspace_files(workspace)
        review_snapshot = load_json_artifact(workspace_files["ui_review_snapshot"])

        artifact_manifest = _build_artifact_manifest(
            workspace, str(job_copy.get("status") or "")
        )

        review_data = {
            "job_id": job_id,
            "job_status": job_copy.get("status"),
            "stage": job_copy.get("stage"),
            "pipeline_status": job_copy.get("pipeline_status"),
            "routing_outcome": job_copy.get("routing_outcome"),
            "review_summary": build_review_summary(packet),
            "normalized_packet": packet,
            "review_snapshot": review_snapshot,
            "can_approve": job_copy.get("status") == "awaiting_review",
            "can_reject": job_copy.get("status") == "awaiting_review",
            "can_start_build": job_copy.get("status")
            in {
                "approved_for_build",
                "awaiting_overwrite_confirmation",
            },
        }

        return jsonify(
            {
                "status": "success",
                "review": review_data,
                "artifact_manifest": artifact_manifest,
            }
        )

    @app.route("/api/toolkit/homebrew/jobs/<job_id>/review", methods=["POST"])
    def apply_toolkit_homebrew_job_review(job_id: str) -> Any:
        """Apply approve/reject decision to one toolkit Homebrew review-gated job."""
        payload = request.get_json(silent=True) or {}
        decision = normalize_review_decision(payload.get("decision"))
        if decision not in VALID_REVIEW_DECISIONS:
            return jsonify(
                {
                    "status": "error",
                    "message": "Invalid review decision",
                    "allowed_decisions": sorted(VALID_REVIEW_DECISIONS),
                }
            ), 400

        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            if job.get("status") != "awaiting_review":
                return jsonify(
                    {
                        "status": "error",
                        "message": "Job is not awaiting review",
                        "job_status": job.get("status"),
                    }
                ), 409
            workspace_raw = str(job.get("artifact_workspace") or "").strip()
            source_rights_class = str(
                job.get("source_rights_class") or SOURCE_RIGHTS_USER_AUTHORED
            )

        if not workspace_raw:
            return jsonify(
                {
                    "status": "error",
                    "message": "Job is missing artifact workspace metadata",
                }
            ), 409

        workspace = Path(workspace_raw)
        packet = load_normalized_packet_artifact(workspace)
        packet_valid, packet_error = validate_review_packet(packet)
        if not packet_valid:
            return jsonify(
                {
                    "status": "error",
                    "message": "Review packet unavailable or invalid",
                    "packet_error": packet_error,
                }
            ), 409

        snapshot = build_review_snapshot(
            job_id=job_id,
            decision=decision,
            packet=packet,
            source_rights_class=source_rights_class,
        )
        if not persist_review_snapshot_artifact(workspace, snapshot):
            return jsonify(
                {
                    "status": "error",
                    "message": "Failed to persist review snapshot",
                }
            ), 500

        next_status = (
            "approved_for_build" if decision == REVIEW_DECISION_APPROVE else "rejected"
        )

        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            if job.get("status") != "awaiting_review":
                return jsonify(
                    {
                        "status": "error",
                        "message": "Job state changed before review decision could be applied",
                        "job_status": job.get("status"),
                    }
                ), 409

            job["status"] = next_status
            job["stage"] = "review"
            job["review_decision"] = decision
            job["review_snapshot"] = snapshot
            job["review_snapshot_path"] = str(
                get_workspace_files(Path(workspace_raw))["ui_review_snapshot"]
            )
            job["updated_at"] = _utc_now_iso()
            job_copy = dict(job)

        info(
            f"TOOLKIT_HOMEBREW: Review decision '{decision}' recorded for job {job_id}",
            category="web_interface",
        )
        return jsonify({"status": "success", "job": job_copy})

    @app.route("/api/toolkit/homebrew/jobs/<job_id>/build", methods=["POST"])
    def start_toolkit_homebrew_job_build(job_id: str) -> Any:
        """Start packet-driven build for one approved toolkit Homebrew upload job."""
        global _active_job_id

        payload = request.get_json(silent=True) or {}
        confirm_overwrite = bool(payload.get("confirm_overwrite"))
        overwrite_policy = (
            str(payload.get("overwrite_policy") or "backup_clean").strip().lower()
        )
        if confirm_overwrite and overwrite_policy != "backup_clean":
            return jsonify(
                {
                    "status": "error",
                    "message": "Unsupported overwrite policy",
                    "allowed_overwrite_policies": ["backup_clean"],
                }
            ), 400

        workspace_raw = ""
        current_status = ""
        job_copy: Dict[str, Any] = {}

        with _jobs_lock:
            if _active_job_id is not None:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Another Homebrew ingest or build job is already running",
                        "active_job_id": _active_job_id,
                    }
                ), 409

            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404

            if job.get("status") not in {
                "approved_for_build",
                "awaiting_overwrite_confirmation",
                "ready_for_finishing",
            }:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Job is not approved for build or finishing",
                        "job_status": job.get("status"),
                    }
                ), 409

            current_status = str(job.get("status") or "")
            workspace_raw = str(job.get("artifact_workspace") or "").strip()
            if not workspace_raw:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Job is missing artifact workspace metadata",
                    }
                ), 409

        module_name = ""
        collision: Dict[str, Any] = {}
        module_dir_exists = False
        build_options: Dict[str, Any] = {}

        if current_status == "ready_for_finishing":
            with _jobs_lock:
                existing_job = _jobs.get(job_id) or {}
                existing_result = (
                    existing_job.get("result")
                    if isinstance(existing_job.get("result"), dict)
                    else {}
                )
                module_name = str(
                    existing_job.get("module_name")
                    or existing_job.get("expected_module_name")
                    or existing_result.get("module_name")
                    or existing_result.get("module_slug")
                    or ""
                ).strip()
                collision = (
                    existing_job.get("rebuild_collision")
                    if isinstance(existing_job.get("rebuild_collision"), dict)
                    else {}
                )

            build_options = {
                "finishing_only": True,
                "rebuild_mode": False,
                "module_name": module_name,
                "module_dir": str((collision or {}).get("module_dir") or ""),
                "overwrite_policy": overwrite_policy,
            }
        else:
            target_info = _resolve_homebrew_build_target(Path(workspace_raw))
            if target_info.get("status") != "success":
                return jsonify(
                    {
                        "status": "error",
                        "message": "Unable to resolve module build target",
                        "details": target_info,
                    }
                ), 409

            module_name = str(target_info.get("module_name") or "").strip()
            collision = (
                target_info.get("collision")
                if isinstance(target_info.get("collision"), dict)
                else {}
            )
            module_dir_exists = bool((collision or {}).get("module_dir_exists"))

            if module_dir_exists and not confirm_overwrite:
                with _jobs_lock:
                    if _active_job_id is not None:
                        return jsonify(
                            {
                                "status": "error",
                                "message": "Another Homebrew ingest or build job is already running",
                                "active_job_id": _active_job_id,
                            }
                        ), 409

                    job = _jobs.get(job_id)
                    if not job:
                        return jsonify(
                            {"status": "error", "message": "Job not found"}
                        ), 404

                    if job.get("status") not in {
                        "approved_for_build",
                        "awaiting_overwrite_confirmation",
                        "ready_for_finishing",
                    }:
                        return jsonify(
                            {
                                "status": "error",
                                "message": "Job is not approved for build or finishing",
                                "job_status": job.get("status"),
                            }
                        ), 409

                    job["status"] = "awaiting_overwrite_confirmation"
                    job["stage"] = "build"
                    job["pipeline_status"] = "awaiting_confirmation"
                    job["rebuild_mode"] = True
                    job["rebuild_collision"] = collision
                    job["expected_module_name"] = module_name
                    job["updated_at"] = _utc_now_iso()
                    job_copy = dict(job)

                return jsonify(
                    {
                        "status": "success",
                        "requires_confirmation": True,
                        "overwrite_policy": "backup_clean",
                        "collision": collision,
                        "job": job_copy,
                    }
                )

            build_options = {
                "finishing_only": False,
                "rebuild_mode": bool(module_dir_exists and confirm_overwrite),
                "module_name": module_name,
                "module_dir": str((collision or {}).get("module_dir") or ""),
                "overwrite_policy": overwrite_policy,
            }

        with _jobs_lock:
            if _active_job_id is not None:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Another Homebrew ingest or build job is already running",
                        "active_job_id": _active_job_id,
                    }
                ), 409

            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404

            if job.get("status") not in {
                "approved_for_build",
                "awaiting_overwrite_confirmation",
                "ready_for_finishing",
            }:
                return jsonify(
                    {
                        "status": "error",
                        "message": "Job is not approved for build or finishing",
                        "job_status": job.get("status"),
                    }
                ), 409

            _active_job_id = job_id
            if bool(build_options.get("finishing_only")):
                job["status"] = "finishing"
                job["stage"] = "finishing"
                job["pipeline_status"] = "finishing"
            else:
                job["status"] = "building"
                job["stage"] = "build"
                job["pipeline_status"] = "building"
            job["build_started_at"] = _utc_now_iso()
            job["rebuild_mode"] = bool(build_options["rebuild_mode"])
            job["rebuild_collision"] = collision
            job["overwrite_policy"] = overwrite_policy
            job["updated_at"] = _utc_now_iso()
            job_copy = dict(job)

        worker = threading.Thread(
            target=_run_homebrew_build_job,
            args=(job_id, build_options),
            daemon=True,
            name=f"ToolkitHomebrewBuild-{job_id[:8]}",
        )
        worker.start()

        info(
            f"TOOLKIT_HOMEBREW: Started packet-driven build job {job_id}",
            category="web_interface",
        )
        return jsonify({"status": "success", "job": job_copy})

    @app.route(
        "/api/toolkit/homebrew/jobs/<job_id>/retry-from-packet", methods=["POST"]
    )
    def retry_toolkit_homebrew_from_packet(job_id: str) -> Any:
        """Retry build from normalized packet for an existing toolkit Homebrew job."""
        global _active_job_id

        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            job_copy = dict(job)
            workspace_raw = str(job_copy.get("artifact_workspace") or "").strip()
            if not workspace_raw:
                return jsonify(
                    {
                        "status": "error",
                        "reason": "workspace_missing",
                        "message": "Job is missing artifact workspace metadata",
                    }
                ), 409

        workspace = Path(workspace_raw)
        artifact_manifest = _build_artifact_manifest(
            workspace, str(job_copy.get("status") or "")
        )

        if (
            not artifact_manifest["artifacts"]
            .get("normalized_packet", {})
            .get("exists", False)
        ):
            return jsonify(
                {
                    "status": "error",
                    "reason": "missing_artifacts",
                    "missing": ["normalized_packet"],
                    "artifact_manifest": artifact_manifest,
                }
            ), 409

        with _jobs_lock:
            if _active_job_id is not None:
                return jsonify(
                    {
                        "status": "error",
                        "reason": "job_already_active",
                        "message": "Another Homebrew build job is already running",
                        "active_job_id": _active_job_id,
                    }
                ), 409

            _active_job_id = job_id

        build_options = {
            "finishing_only": False,
            "rebuild_mode": False,
            "module_name": "",
        }

        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                _active_job_id = None
                return jsonify({"status": "error", "message": "Job not found"}), 404
            job["status"] = "approved_for_build"
            job["stage"] = "build"
            job["pipeline_status"] = "rebuilding_from_packet"
            job["updated_at"] = _utc_now_iso()
            job_copy = dict(job)

        worker = threading.Thread(
            target=_run_homebrew_build_job,
            args=(job_id, build_options),
            daemon=True,
            name=f"ToolkitHomebrewBuild-{job_id[:8]}",
        )
        worker.start()

        info(
            f"TOOLKIT_HOMEBREW: Started retry-from-packet build job {job_id}",
            category="web_interface",
        )
        return jsonify(
            {
                "status": "success",
                "job": job_copy,
                "artifact_manifest": artifact_manifest,
                "hydration_summary": _build_hydration_summary(
                    job_copy.get("result") or {}
                ),
            }
        )

    @app.route(
        "/api/toolkit/homebrew/jobs/<job_id>/retry-from-finishing", methods=["POST"]
    )
    def retry_toolkit_homebrew_from_finishing(job_id: str) -> Any:
        """Retry finishing-only for an existing toolkit Homebrew job that has build artifacts."""
        global _active_job_id

        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            job_copy = dict(job)
            workspace_raw = str(job_copy.get("artifact_workspace") or "").strip()
            if not workspace_raw:
                return jsonify(
                    {
                        "status": "error",
                        "reason": "workspace_missing",
                        "message": "Job is missing artifact workspace metadata",
                    }
                ), 409

        workspace = Path(workspace_raw)
        artifact_manifest = _build_artifact_manifest(
            workspace, str(job_copy.get("status") or "")
        )

        build_input_exists = (
            artifact_manifest["artifacts"].get("builder_input", {}).get("exists", False)
        )
        build_result_exists = (
            artifact_manifest["artifacts"].get("build_result", {}).get("exists", False)
        )

        if not build_input_exists or not build_result_exists:
            missing = []
            if not build_input_exists:
                missing.append("builder_input")
            if not build_result_exists:
                missing.append("build_result")
            return jsonify(
                {
                    "status": "error",
                    "reason": "missing_artifacts",
                    "missing": missing,
                    "artifact_manifest": artifact_manifest,
                }
            ), 409

        with _jobs_lock:
            if _active_job_id is not None:
                return jsonify(
                    {
                        "status": "error",
                        "reason": "job_already_active",
                        "message": "Another Homebrew build job is already running",
                        "active_job_id": _active_job_id,
                    }
                ), 409

            _active_job_id = job_id

        build_options = {
            "finishing_only": True,
            "rebuild_mode": False,
            "module_name": "",
        }

        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                _active_job_id = None
                return jsonify({"status": "error", "message": "Job not found"}), 404
            job["status"] = "ready_for_finishing"
            job["stage"] = "finishing"
            job["pipeline_status"] = "retry_from_finishing"
            job["updated_at"] = _utc_now_iso()
            job_copy = dict(job)

        worker = threading.Thread(
            target=_run_homebrew_build_job,
            args=(job_id, build_options),
            daemon=True,
            name=f"ToolkitHomebrewFinishing-{job_id[:8]}",
        )
        worker.start()

        info(
            f"TOOLKIT_HOMEBREW: Started retry-from-finishing job {job_id}",
            category="web_interface",
        )
        return jsonify(
            {
                "status": "success",
                "job": job_copy,
                "artifact_manifest": artifact_manifest,
                "hydration_summary": _build_hydration_summary(
                    job_copy.get("result") or {}
                ),
            }
        )

    @app.route("/api/toolkit/homebrew/jobs/<job_id>/cleanup", methods=["POST"])
    def cleanup_toolkit_homebrew_job(job_id: str) -> Any:
        """Delete the artifact workspace for a toolkit Homebrew job."""
        request_payload = request.get_json(silent=True) or {}
        force_cleanup = bool(request_payload.get("force"))

        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            job_copy = dict(job)
            workspace_raw = str(job_copy.get("artifact_workspace") or "").strip()
            if not workspace_raw:
                return jsonify(
                    {
                        "status": "error",
                        "reason": "workspace_missing",
                        "message": "Job is missing artifact workspace metadata",
                    }
                ), 409

        workspace = Path(workspace_raw)
        current_status = str(job_copy.get("status") or "")

        if not force_cleanup and current_status not in _TERMINAL_JOB_STATES:
            return jsonify(
                {
                    "status": "error",
                    "reason": "non_terminal_state",
                    "message": "Job is not in a terminal state and force was not specified",
                    "current_status": current_status,
                }
            ), 409

        removal_path = workspace_raw
        try:
            if workspace.exists():
                shutil.rmtree(workspace)
        except Exception:
            pass

        with _jobs_lock:
            job = _jobs.get(job_id)
            if job:
                job["status"] = "cleaned_up"
                job["stage"] = "cleanup"
                job["pipeline_status"] = "cleaned_up"
                job["updated_at"] = _utc_now_iso()
                job_copy = dict(job)

        info(
            f"TOOLKIT_HOMEBREW: Cleaned up job {job_id}",
            category="web_interface",
        )
        return jsonify(
            {
                "status": "success",
                "job": job_copy,
                "removed_path": removal_path,
            }
        )

    @app.route("/api/toolkit/homebrew/jobs/<job_id>", methods=["GET"])
    def get_toolkit_homebrew_job(job_id: str) -> Any:
        """Get toolkit Homebrew ingest job status."""
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            job_copy = dict(job)

        workspace_raw = str(job_copy.get("artifact_workspace") or "").strip()
        artifact_manifest: Dict[str, Any] = {}
        if workspace_raw:
            workspace = Path(workspace_raw)
            artifact_manifest = _build_artifact_manifest(
                workspace, str(job_copy.get("status") or "")
            )

        return jsonify(
            {
                "status": "success",
                "job": job_copy,
                "artifact_manifest": artifact_manifest,
            }
        )

    @app.route("/api/toolkit/homebrew/jobs/active", methods=["GET"])
    def get_active_toolkit_homebrew_job() -> Any:
        """Get currently active toolkit Homebrew job id, if any."""
        global _active_job_id
        with _jobs_lock:
            if _active_job_id is None:
                return jsonify({"status": "success", "active_job_id": None})
            active_job = _jobs.get(_active_job_id)
            if active_job is None:
                warning(
                    "TOOLKIT_HOMEBREW: Active job id missing from state map; repairing state",
                    category="web_interface",
                )
                _active_job_id = None
                return jsonify({"status": "success", "active_job_id": None})
            job_copy = dict(active_job)

        workspace_raw = str(job_copy.get("artifact_workspace") or "").strip()
        artifact_manifest: Dict[str, Any] = {}
        if workspace_raw:
            workspace = Path(workspace_raw)
            artifact_manifest = _build_artifact_manifest(
                workspace, str(job_copy.get("status") or "")
            )

        return jsonify(
            {
                "status": "success",
                "active_job_id": _active_job_id,
                "job": job_copy,
                "artifact_manifest": artifact_manifest,
                "hydration_summary": _build_hydration_summary(
                    job_copy.get("result") or {}
                ),
            }
        )
