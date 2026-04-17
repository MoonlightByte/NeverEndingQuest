# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew cleanup route."""

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


class TestCleanupRoute(unittest.TestCase):
    """Verify cleanup route contracts."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_upload_root = toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT

        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = Path(self.temp_dir.name)

        self.app = Flask(__name__)
        toolkit_homebrew_routes.register_toolkit_homebrew_routes(self.app)
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = self.original_upload_root
        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        self.temp_dir.cleanup()

    def _seed_job(self, job_id: str, status: str, workspace: Path) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "builder_input.json").write_text(
            json.dumps({"module_name": "Test"}), encoding="utf-8"
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

    def test_success_job_not_found_returns_404(self) -> None:
        response = self.client.post(
            "/api/toolkit/homebrew/jobs/nonexistent/cleanup"
        )
        self.assertEqual(response.status_code, 404)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("message"), "Job not found")

    def test_success_terminal_state_cleanup_removes_workspace(self) -> None:
        job_id = "cleanup-terminal"
        workspace = Path(self.temp_dir.name) / job_id
        self._seed_job(job_id, "completed", workspace)
        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/cleanup"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "success")
        self.assertEqual(payload.get("removed_path"), str(workspace))
        self.assertFalse(Path(workspace).exists())

    def test_success_force_cleanup_removes_non_terminal_workspace(self) -> None:
        job_id = "cleanup-force"
        workspace = Path(self.temp_dir.name) / job_id
        self._seed_job(job_id, "pending", workspace)
        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/cleanup",
            json={"force": True},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "success")
        self.assertEqual(payload.get("removed_path"), str(workspace))
        self.assertFalse(Path(workspace).exists())

    def test_rejection_non_terminal_without_force_returns_409(self) -> None:
        job_id = "cleanup-no-force"
        workspace = Path(self.temp_dir.name) / job_id
        self._seed_job(job_id, "pending", workspace)
        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/cleanup"
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("reason"), "non_terminal_state")
        self.assertEqual(payload.get("current_status"), "pending")
        self.assertTrue(Path(workspace).exists())

    def test_success_includes_job_copy(self) -> None:
        job_id = "cleanup-job-copy"
        workspace = Path(self.temp_dir.name) / job_id
        self._seed_job(job_id, "completed", workspace)
        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/cleanup"
        )
        payload = response.get_json() or {}
        job = payload.get("job") or {}
        self.assertIn("job_id", job)
        self.assertEqual(job.get("status"), "cleaned_up")
        self.assertEqual(job.get("stage"), "cleanup")

    def test_success_missing_workspace_returns_409(self) -> None:
        job_id = "cleanup-no-workspace"
        with toolkit_homebrew_routes._jobs_lock:
            toolkit_homebrew_routes._jobs[job_id] = {
                "job_id": job_id,
                "status": "completed",
                "artifact_workspace": "",
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }

        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/cleanup"
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("reason"), "workspace_missing")

    def test_success_already_gone_workspace_returns_200(self) -> None:
        job_id = "cleanup-already-gone"
        workspace = Path(self.temp_dir.name) / job_id
        self._seed_job(job_id, "completed", workspace)
        shutil.rmtree(workspace)

        response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/cleanup"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "success")
        self.assertEqual(payload.get("removed_path"), str(workspace))


if __name__ == "__main__":
    import shutil
    unittest.main()
