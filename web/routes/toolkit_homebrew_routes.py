# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Routes - Toolkit Homebrew markdown ingest routes.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

from utils.enhanced_logger import error, info, warning


ALLOWED_HOME_BREW_EXTENSIONS = {".md"}
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
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_filename(raw_name: str) -> str:
    """Return a safe basename without path traversal."""
    base_name = Path(str(raw_name or "")).name
    safe = "".join(ch for ch in base_name if ch.isalnum() or ch in {"_", "-", ".", " "}).strip()
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


def _run_shared_ingest_pipeline(source_path: str) -> Dict[str, Any]:
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
    )


def _run_homebrew_ingest_job(job_id: str, source_path: Path) -> None:
    """Run one toolkit Homebrew ingest job in background."""
    global _active_job_id

    try:
        _set_job_state(job_id, "running", stage="preflight")

        _set_job_state(job_id, "running", stage="pipeline")
        result = _run_shared_ingest_pipeline(str(source_path))

        pipeline_status = str(result.get("status") or "failed")
        pipeline_stage = str(result.get("stage") or "unknown")
        quarantine_reason = _extract_quarantine_reason(result)

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


def register_toolkit_homebrew_routes(app: Flask) -> None:
    """Register toolkit Homebrew markdown upload and job-status routes."""

    @app.route('/api/toolkit/homebrew/upload', methods=['POST'])
    def upload_toolkit_homebrew_markdown() -> Any:
        """Upload one Homebrew markdown file and start ingest job."""
        global _active_job_id

        try:
            with _jobs_lock:
                if _active_job_id is not None:
                    return jsonify({
                        "status": "error",
                        "message": "Another Homebrew ingest job is already running",
                        "active_job_id": _active_job_id,
                    }), 409

            incoming = request.files.get("file")
            if incoming is None:
                return jsonify({"status": "error", "message": "Missing file field"}), 400

            safe_name = _sanitize_filename(str(incoming.filename or ""))
            if not safe_name:
                return jsonify({"status": "error", "message": "Invalid filename"}), 400

            extension = Path(safe_name).suffix.lower()
            if extension not in ALLOWED_HOME_BREW_EXTENSIONS:
                return jsonify({
                    "status": "error",
                    "message": "File type not allowed. Upload a .md file.",
                    "allowed_extensions": sorted(ALLOWED_HOME_BREW_EXTENSIONS),
                }), 400

            TOOLKIT_HOMEBREW_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

            job_id = str(uuid.uuid4())
            destination = TOOLKIT_HOMEBREW_UPLOAD_ROOT / f"{job_id}_{safe_name}"
            incoming.save(str(destination))

            size_bytes = destination.stat().st_size
            if size_bytes > TOOLKIT_HOMEBREW_MAX_UPLOAD_BYTES:
                destination.unlink(missing_ok=True)
                return jsonify({
                    "status": "error",
                    "message": "File exceeds max upload size",
                    "max_bytes": TOOLKIT_HOMEBREW_MAX_UPLOAD_BYTES,
                }), 400

            with _jobs_lock:
                _active_job_id = job_id
                _jobs[job_id] = {
                    "job_id": job_id,
                    "job_type": "toolkit_homebrew_md_ingest",
                    "status": "queued",
                    "stage": "queued",
                    "pipeline_status": None,
                    "quarantine_reason": None,
                    "created_at": _utc_now_iso(),
                    "updated_at": _utc_now_iso(),
                    "source_path": str(destination),
                    "source_filename": safe_name,
                    "size_bytes": size_bytes,
                    "allowed_extensions": sorted(ALLOWED_HOME_BREW_EXTENSIONS),
                }

            worker = threading.Thread(
                target=_run_homebrew_ingest_job,
                args=(job_id, destination),
                daemon=True,
                name=f"ToolkitHomebrewIngest-{job_id[:8]}",
            )
            worker.start()

            info(
                f"TOOLKIT_HOMEBREW: Started markdown ingest job {job_id} for {safe_name}",
                category="web_interface",
            )
            return jsonify({
                "status": "success",
                "job_id": job_id,
                "allowed_extensions": sorted(ALLOWED_HOME_BREW_EXTENSIONS),
                "size_bytes": size_bytes,
            })

        except Exception as route_error:
            error(
                f"TOOLKIT_HOMEBREW: Upload failed: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            return jsonify({"status": "error", "message": str(route_error)}), 500

    @app.route('/api/toolkit/homebrew/jobs/<job_id>', methods=['GET'])
    def get_toolkit_homebrew_job(job_id: str) -> Any:
        """Get toolkit Homebrew ingest job status."""
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            return jsonify({"status": "success", "job": job})

    @app.route('/api/toolkit/homebrew/jobs/active', methods=['GET'])
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
            return jsonify({"status": "success", "active_job_id": _active_job_id, "job": active_job})
