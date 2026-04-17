# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew retry-from-finishing route."""

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


class TestRetryFromFinishingRoute(unittest.TestCase):
    """Verify retry-from-finishing route contracts."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_upload_root = toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT
        self.original_build = toolkit_homebrew_routes._run_homebrew_build_job

        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = Path(self.temp_dir.name)

        self.app = Flask(__name__)
        toolkit_homebrew_routes.register_toolkit_homebrew_routes(self.app)
        self.client = self.app.test_client()

        toolkit_homebrew_routes._run_homebrew_build_job = lambda *a, **kw: None

    def tearDown(self) -> None:
        toolkit_homebrew_routes._run_homebrew_build_job = self.original_build
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = self.original_upload_root
        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        self.temp_dir.cleanup()

    def _seed_job_with_build_artifacts(
        self, job_id: str, status: str = "completed"
    ) -> Path:
        workspace = Path(self.temp_dir.name) / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "builder_input.json").write_text(
            json.dumps({"module_name": "TestModule", "areas": []}), encoding="utf-8"
        )
        (workspace / "build_result.json").write_text(
            json.dumps({"status": "success", "module_slug": "test-module"}), encoding="utf-8"
        )
        with toolkit_homebrew_routes._jobs_lock:
            toolkit_homebrew_routes._jobs[job_id] = {
                "job_id": job_id,
                "job_type": "toolkit_homebrew_md_ingest",
                "status": status,
                "stage": "finishing",
                "artifact_workspace": str(workspace),
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
        return workspace

    def test_success_job_not_found_returns_404(self) -> None:
        response = self.client.post(
            "/api/toolkit/homebrew/jobs/nonexistent/retry-from-finishing"
        )
        self.assertEqual(response.status_code, 404)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("message"), "Job not found")

    def test_success_build_artifacts_present_returns_200(self) -> None:
        job_id = "finishing-retry-success"
        self._seed_job_with_build_artifacts(job_id, status="completed")
        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-finishing"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "success")
        job = payload.get("job") or {}
        self.assertEqual(job.get("status"), "ready_for_finishing")
        self.assertEqual(job.get("stage"), "finishing")
        self.assertEqual(job.get("pipeline_status"), "retry_from_finishing")

    def test_success_missing_builder_input_returns_409(self) -> None:
        job_id = "finishing-retry-missing-input"
        workspace = Path(self.temp_dir.name) / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "build_result.json").write_text(
            json.dumps({"status": "success"}), encoding="utf-8"
        )
        with toolkit_homebrew_routes._jobs_lock:
            toolkit_homebrew_routes._jobs[job_id] = {
                "job_id": job_id,
                "status": "completed",
                "artifact_workspace": str(workspace),
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }

        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-finishing"
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("reason"), "missing_artifacts")
        self.assertIn("builder_input", payload.get("missing", []))

    def test_success_missing_build_result_returns_409(self) -> None:
        job_id = "finishing-retry-missing-result"
        workspace = Path(self.temp_dir.name) / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "builder_input.json").write_text(
            json.dumps({"module_name": "Test"}), encoding="utf-8"
        )
        with toolkit_homebrew_routes._jobs_lock:
            toolkit_homebrew_routes._jobs[job_id] = {
                "job_id": job_id,
                "status": "completed",
                "artifact_workspace": str(workspace),
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }

        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-finishing"
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("reason"), "missing_artifacts")
        self.assertIn("build_result", payload.get("missing", []))

    def test_success_missing_workspace_returns_409(self) -> None:
        job_id = "finishing-retry-no-workspace"
        with toolkit_homebrew_routes._jobs_lock:
            toolkit_homebrew_routes._jobs[job_id] = {
                "job_id": job_id,
                "status": "completed",
                "artifact_workspace": "",
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }

        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-finishing"
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("reason"), "workspace_missing")

    def test_success_concurrent_active_job_returns_409(self) -> None:
        job_id_1 = "finishing-retry-concurrent-1"
        job_id_2 = "finishing-retry-concurrent-2"
        self._seed_job_with_build_artifacts(job_id_2, status="completed")

        toolkit_homebrew_routes._active_job_id = job_id_1

        try:
            response = self.client.post(
                f"/api/toolkit/homebrew/jobs/{job_id_2}/retry-from-finishing"
            )
            self.assertEqual(response.status_code, 409)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("status"), "error")
            self.assertEqual(payload.get("reason"), "job_already_active")
            self.assertEqual(payload.get("active_job_id"), job_id_1)
        finally:
            toolkit_homebrew_routes._active_job_id = None

    def test_response_includes_job_copy(self) -> None:
        job_id = "finishing-retry-job-copy"
        self._seed_job_with_build_artifacts(job_id, status="completed")
        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-finishing"
        )
        payload = response.get_json() or {}
        job = payload.get("job") or {}
        self.assertIn("job_id", job)
        self.assertIn("status", job)
        self.assertIn("stage", job)
        self.assertIn("artifact_workspace", job)

    def test_artifact_manifest_included_in_success_response(self) -> None:
        job_id = "finishing-retry-manifest"
        self._seed_job_with_build_artifacts(job_id, status="completed")
        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/retry-from-finishing"
        )
        payload = response.get_json() or {}
        manifest = payload.get("artifact_manifest") or {}
        self.assertIn("artifacts", manifest)
        self.assertIn("rebuild_eligible", manifest)
        self.assertIn("cleanup_allowed", manifest)


if __name__ == "__main__":
    unittest.main()
