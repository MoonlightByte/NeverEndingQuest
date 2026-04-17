# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew retry-from-packet route."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web.routes.toolkit_homebrew_routes as toolkit_homebrew_routes


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TestRetryFromPacketRoute(unittest.TestCase):
    """Verify retry-from-packet route contracts."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_upload_root = toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT
        self.original_runner = toolkit_homebrew_routes._run_shared_ingest_pipeline
        self.original_build = toolkit_homebrew_routes._run_homebrew_build_job

        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = Path(self.temp_dir.name)

        self.app = Flask(__name__)
        toolkit_homebrew_routes.register_toolkit_homebrew_routes(self.app)
        self.client = self.app.test_client()

        toolkit_homebrew_routes._run_homebrew_build_job = lambda *a, **kw: None

    def tearDown(self) -> None:
        toolkit_homebrew_routes._run_shared_ingest_pipeline = self.original_runner
        toolkit_homebrew_routes._run_homebrew_build_job = self.original_build
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = self.original_upload_root
        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        self.temp_dir.cleanup()

    def _seed_job_with_packet(self, job_id: str, status: str = "completed") -> Path:
        workspace = Path(self.temp_dir.name) / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        packet = {
            "packet_version": "v1",
            "normalization_state": "normalized",
            "title": "Retry Adventure",
            "author": "Tester",
        }
        (workspace / "normalized_packet.json").write_text(json.dumps(packet), encoding="utf-8")
        with toolkit_homebrew_routes._jobs_lock:
            toolkit_homebrew_routes._jobs[job_id] = {
                "job_id": job_id,
                "job_type": "toolkit_homebrew_md_ingest",
                "status": status,
                "stage": "pipeline",
                "artifact_workspace": str(workspace),
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
        return workspace

    def test_success_job_not_found_returns_404(self) -> None:
        response = self.client.post("/api/toolkit/homebrew/jobs/nonexistent/retry-from-packet")
        self.assertEqual(response.status_code, 404)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("message"), "Job not found")

    def test_success_normalized_packet_present_returns_200(self) -> None:
        job_id = "retry-test-success"
        self._seed_job_with_packet(job_id, status="completed")
        response = self.client.post(f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-packet")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "success")
        job = payload.get("job") or {}
        self.assertEqual(job.get("status"), "approved_for_build")
        self.assertEqual(job.get("stage"), "build")
        self.assertEqual(job.get("pipeline_status"), "rebuilding_from_packet")

    def test_success_missing_normalized_packet_returns_409(self) -> None:
        job_id = "retry-test-missing-packet"
        workspace = Path(self.temp_dir.name) / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        with toolkit_homebrew_routes._jobs_lock:
            toolkit_homebrew_routes._jobs[job_id] = {
                "job_id": job_id,
                "status": "completed",
                "artifact_workspace": str(workspace),
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }

        response = self.client.post(f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-packet")
        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("reason"), "missing_artifacts")
        self.assertIn("normalized_packet", payload.get("missing", []))
        manifest = payload.get("artifact_manifest") or {}
        self.assertFalse(manifest.get("artifacts", {}).get("normalized_packet", {}).get("exists"))

    def test_success_missing_workspace_returns_409(self) -> None:
        job_id = "retry-test-no-workspace"
        with toolkit_homebrew_routes._jobs_lock:
            toolkit_homebrew_routes._jobs[job_id] = {
                "job_id": job_id,
                "status": "completed",
                "artifact_workspace": "",
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }

        response = self.client.post(f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-packet")
        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("reason"), "workspace_missing")

    def test_success_concurrent_active_job_returns_409(self) -> None:
        job_id_1 = "retry-test-concurrent-1"
        job_id_2 = "retry-test-concurrent-2"
        self._seed_job_with_packet(job_id_2, status="completed")

        toolkit_homebrew_routes._active_job_id = job_id_1

        try:
            response = self.client.post(f"/api/toolkit/homebrew/jobs/{job_id_2}/retry-from-packet")
            self.assertEqual(response.status_code, 409)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("status"), "error")
            self.assertEqual(payload.get("reason"), "job_already_active")
            self.assertEqual(payload.get("active_job_id"), job_id_1)
        finally:
            toolkit_homebrew_routes._active_job_id = None

    def test_success_active_job_self_returns_409(self) -> None:
        job_id = "retry-test-self-active"
        self._seed_job_with_packet(job_id, status="completed")

        toolkit_homebrew_routes._active_job_id = job_id

        try:
            response = self.client.post(f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-packet")
            self.assertEqual(response.status_code, 409)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("status"), "error")
            self.assertEqual(payload.get("reason"), "job_already_active")
        finally:
            toolkit_homebrew_routes._active_job_id = None

    def test_response_includes_job_copy(self) -> None:
        job_id = "retry-test-job-copy"
        self._seed_job_with_packet(job_id, status="completed")
        response = self.client.post(f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-packet")
        payload = response.get_json() or {}
        job = payload.get("job") or {}
        self.assertIn("job_id", job)
        self.assertIn("status", job)
        self.assertIn("stage", job)
        self.assertIn("artifact_workspace", job)

    def test_artifact_manifest_included_in_success_response(self) -> None:
        job_id = "retry-test-manifest"
        self._seed_job_with_packet(job_id, status="completed")
        response = self.client.post(f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-packet")
        payload = response.get_json() or {}
        manifest = payload.get("artifact_manifest") or {}
        self.assertIn("artifacts", manifest)
        self.assertIn("rebuild_eligible", manifest)
        self.assertIn("cleanup_allowed", manifest)

    def test_normalized_packet_exists_in_manifest_on_success(self) -> None:
        job_id = "retry-test-packet-in-manifest"
        self._seed_job_with_packet(job_id, status="completed")
        response = self.client.post(f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-packet")
        payload = response.get_json() or {}
        manifest = payload.get("artifact_manifest") or {}
        packet_artifact = manifest.get("artifacts", {}).get("normalized_packet") or {}
        self.assertTrue(packet_artifact.get("exists"))
        self.assertIn("path", packet_artifact)


if __name__ == "__main__":
    unittest.main()
