# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Routes - World narrative ingestion endpoints.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

from flask import Flask, jsonify, request

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH, DEFAULT_WORLD_NARRATIVE_SEED_DB_PATH
from core.memory.world_narrative_ingest import ingest_source_anonymous_atoms, validate_source_anonymous_payload
from utils.enhanced_logger import error, info, warning


ALLOWED_SOURCE_EXTENSIONS: Set[str] = {".pdf"}
USER_UPLOADS_ROOT = Path("user_uploads") / "text"
INGESTION_ROOT = USER_UPLOADS_ROOT / "ingestion"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
BANNED_TERMS_FILE = USER_UPLOADS_ROOT / "banned_terms.txt"


_jobs_lock = threading.Lock()
_jobs: Dict[str, Dict[str, Any]] = {}
_active_job_id: Optional[str] = None


def reset_world_jobs_for_tests() -> None:
    """Reset in-memory world ingestion job state (tests only)."""
    global _active_job_id
    with _jobs_lock:
        _jobs.clear()
        _active_job_id = None


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_filename(raw_name: str) -> str:
    """Return a safe basename without path traversal."""
    name = os.path.basename((raw_name or "").strip())
    if not name:
        return ""
    safe = "".join(ch for ch in name if ch.isalnum() or ch in {"_", "-", ".", " "}).strip()
    return safe.replace(" ", "_")


def _load_local_banned_terms() -> Set[str]:
    """Load optional local banned term overrides."""
    terms: Set[str] = set()
    if not BANNED_TERMS_FILE.exists():
        return terms
    try:
        for line in BANNED_TERMS_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip().lower()
            if stripped and not stripped.startswith("#"):
                terms.add(stripped)
    except Exception as load_error:
        warning(f"WORLD_NARRATIVE: Failed to load banned terms file: {load_error}", category="web_interface")
    return terms


def _is_within_upload_root(path: Path) -> bool:
    """Return True when path is under the hard-cutover upload root."""
    uploads_root = USER_UPLOADS_ROOT.resolve()
    candidate = path.resolve()
    return candidate == uploads_root or uploads_root in candidate.parents


def _set_job_state(job_id: str, status: str, **fields: Any) -> None:
    """Update one job state."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = status
        job["updated_at"] = _utc_now_iso()
        for key, value in fields.items():
            job[key] = value


def _start_background_job(job_id: str, target) -> None:
    """Start one daemon worker thread."""
    thread = threading.Thread(target=target, daemon=True)
    thread.start()


def _run_extract_job(job_id: str, source_path: Path) -> None:
    """Run chunk extraction script in background."""
    global _active_job_id
    try:
        script_path = Path("scripts") / "extract_book_pdf_for_ingestion.py"
        output_dir = INGESTION_ROOT
        output_dir.mkdir(parents=True, exist_ok=True)

        command = [
            sys.executable,
            str(script_path),
            "--input",
            str(source_path),
            "--output-dir",
            str(output_dir),
            "--max-chars",
            "6000",
            "--overlap-chars",
            "400",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            _set_job_state(
                job_id,
                "failed",
                error="Extraction failed",
                stderr=result.stderr[-4000:],
                stdout=result.stdout[-4000:],
            )
            return

        _set_job_state(
            job_id,
            "completed",
            stdout=result.stdout[-4000:],
            stderr=result.stderr[-4000:],
        )
    except Exception as job_error:
        _set_job_state(job_id, "failed", error=str(job_error))
    finally:
        with _jobs_lock:
            if _active_job_id == job_id:
                _active_job_id = None


def register_world_narrative_routes(app: Flask) -> None:
    """Register toolkit world narrative upload/extract/ingest routes."""

    @app.route('/api/toolkit/world/sources/upload', methods=['POST'])
    def upload_world_source() -> Any:
        """Upload one local world narrative source file to /user_uploads/text/."""
        try:
            if request.form.get("attest_copyright", "false").lower() != "true":
                return jsonify({
                    "status": "error",
                    "message": "Copyright attestation required",
                }), 400

            if "file" not in request.files:
                return jsonify({"status": "error", "message": "Missing file field"}), 400

            incoming = request.files["file"]
            safe_name = _sanitize_filename(str(incoming.filename or ""))
            if not safe_name:
                return jsonify({"status": "error", "message": "Invalid filename"}), 400

            extension = Path(safe_name).suffix.lower()
            if extension not in ALLOWED_SOURCE_EXTENSIONS:
                return jsonify({"status": "error", "message": "File type not allowed"}), 400

            USER_UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
            destination = USER_UPLOADS_ROOT / safe_name
            incoming.save(str(destination))

            size_bytes = destination.stat().st_size
            if size_bytes > MAX_UPLOAD_BYTES:
                destination.unlink(missing_ok=True)
                return jsonify({"status": "error", "message": "File exceeds max upload size"}), 400

            info(f"WORLD_NARRATIVE: Uploaded source file {destination}", category="web_interface")
            return jsonify({
                "status": "success",
                "path": str(destination),
                "size_bytes": size_bytes,
                "allowed_extensions": sorted(ALLOWED_SOURCE_EXTENSIONS),
            })
        except Exception as route_error:
            error(
                f"WORLD_NARRATIVE: Upload failed: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            return jsonify({"status": "error", "message": str(route_error)}), 500

    @app.route('/api/toolkit/world/sources/extract', methods=['POST'])
    def extract_world_source() -> Any:
        """Start one extraction job for a previously uploaded PDF file."""
        global _active_job_id
        try:
            data = request.get_json(silent=True) or {}
            source_path = Path(str(data.get("path") or "")).resolve()
            if not str(source_path).endswith(".pdf"):
                return jsonify({"status": "error", "message": "Extraction currently supports PDF only"}), 400

            if not source_path.exists():
                return jsonify({"status": "error", "message": "Source file not found"}), 404

            if not _is_within_upload_root(source_path):
                return jsonify({"status": "error", "message": "Source file must be inside /user_uploads/text/"}), 400

            with _jobs_lock:
                if _active_job_id is not None:
                    return jsonify({
                        "status": "error",
                        "message": "Another world ingestion job is already running",
                        "active_job_id": _active_job_id,
                    }), 409

                job_id = str(uuid.uuid4())
                _active_job_id = job_id
                _jobs[job_id] = {
                    "job_id": job_id,
                    "job_type": "extract",
                    "status": "running",
                    "created_at": _utc_now_iso(),
                    "updated_at": _utc_now_iso(),
                    "source_path": str(source_path),
                }

            _start_background_job(job_id, lambda: _run_extract_job(job_id, source_path))
            return jsonify({"status": "success", "job_id": job_id})
        except Exception as route_error:
            error(
                f"WORLD_NARRATIVE: Extract job start failed: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            return jsonify({"status": "error", "message": str(route_error)}), 500

    @app.route('/api/toolkit/world/sources/build-atoms', methods=['POST'])
    def build_world_atoms() -> Any:
        """Build source-anonymous atoms from chunk JSONL output."""
        try:
            data = request.get_json(silent=True) or {}
            chunks_path = Path(str(data.get("chunks_path") or "")).resolve()
            output_path_raw = str(data.get("output_path") or "").strip()
            if not chunks_path.exists():
                return jsonify({"status": "error", "message": "Chunks file not found"}), 404

            if not _is_within_upload_root(chunks_path):
                return jsonify({"status": "error", "message": "Chunks file must be inside /user_uploads/text/"}), 400

            output_path = Path(output_path_raw).resolve() if output_path_raw else (INGESTION_ROOT / "anonymous_atoms.json").resolve()
            if not _is_within_upload_root(output_path):
                return jsonify({"status": "error", "message": "Output path must be inside /user_uploads/text/"}), 400

            output_path.parent.mkdir(parents=True, exist_ok=True)
            script_path = Path("scripts") / "build_source_anonymous_atoms.py"
            command = [
                sys.executable,
                str(script_path),
                "--chunks",
                str(chunks_path),
                "--output",
                str(output_path),
                "--strict",
            ]

            banned_terms_file = BANNED_TERMS_FILE.resolve()
            if banned_terms_file.exists():
                command.extend(["--banned-terms-file", str(banned_terms_file)])

            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return jsonify({
                    "status": "error",
                    "message": "Atom build failed",
                    "stdout": result.stdout[-4000:],
                    "stderr": result.stderr[-4000:],
                }), 400

            return jsonify({
                "status": "success",
                "output_path": str(output_path),
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            })
        except Exception as route_error:
            error(
                f"WORLD_NARRATIVE: Build atoms failed: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            return jsonify({"status": "error", "message": str(route_error)}), 500

    @app.route('/api/toolkit/world/sources/ingest', methods=['POST'])
    def ingest_world_atoms() -> Any:
        """Ingest source-anonymous atom payload into memory DB."""
        try:
            data = request.get_json(silent=True) or {}
            atoms_path = Path(str(data.get("atoms_path") or "")).resolve()
            if not atoms_path.exists():
                return jsonify({"status": "error", "message": "Atoms file not found"}), 404

            if not _is_within_upload_root(atoms_path):
                return jsonify({"status": "error", "message": "Atoms file must be inside /user_uploads/text/"}), 400

            payload = json.loads(atoms_path.read_text(encoding="utf-8"))
            banned_terms = _load_local_banned_terms()
            compliance = validate_source_anonymous_payload(payload, banned_terms)
            if not compliance.get("ok"):
                return jsonify({
                    "status": "error",
                    "message": "Compliance check failed",
                    "key_hits": compliance.get("key_hits", []),
                    "term_hits": compliance.get("term_hits", []),
                }), 400

            db_path = str(data.get("db_path") or DEFAULT_MEMORY_DB_PATH)
            ingest_result = ingest_source_anonymous_atoms(payload, db_path=db_path)
            return jsonify({
                "status": "success",
                "db_path": db_path,
                "seed_db_path": DEFAULT_WORLD_NARRATIVE_SEED_DB_PATH,
                "ingest": ingest_result,
            })
        except Exception as route_error:
            error(
                f"WORLD_NARRATIVE: Ingest failed: {route_error}",
                exception=route_error,
                category="web_interface",
            )
            return jsonify({"status": "error", "message": str(route_error)}), 500

    @app.route('/api/toolkit/world/jobs/<job_id>', methods=['GET'])
    def get_world_job_status(job_id: str) -> Any:
        """Return job status for one world ingestion job."""
        with _jobs_lock:
            job = _jobs.get(job_id)
            if not job:
                return jsonify({"status": "error", "message": "Job not found"}), 404
            return jsonify({"status": "success", "job": job})
