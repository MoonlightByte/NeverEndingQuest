# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew markdown upload routes."""

import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web.routes.toolkit_homebrew_routes as toolkit_homebrew_routes


class TestToolkitHomebrewUploadRoutes(unittest.TestCase):
    """Verify markdown upload contracts and job state mapping."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_upload_root = toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT
        self.original_runner = toolkit_homebrew_routes._run_shared_ingest_pipeline

        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = Path(self.temp_dir.name)

        self.app = Flask(__name__)
        toolkit_homebrew_routes.register_toolkit_homebrew_routes(self.app)
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        toolkit_homebrew_routes._run_shared_ingest_pipeline = self.original_runner
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = self.original_upload_root
        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        self.temp_dir.cleanup()

    def _wait_for_terminal_job(self, job_id: str) -> dict:
        for _ in range(80):
            response = self.client.get(f"/api/toolkit/homebrew/jobs/{job_id}")
            payload = response.get_json() or {}
            if payload.get("status") != "success":
                time.sleep(0.05)
                continue

            job = payload.get("job") or {}
            if job.get("status") in {"completed", "failed", "quarantined"}:
                return job
            time.sleep(0.05)
        self.fail(f"Job {job_id} did not reach terminal state")

    def test_upload_rejects_non_markdown(self) -> None:
        response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"not markdown"), "sample.txt")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertIn(".md", payload.get("message", ""))

    def test_upload_job_completes_success(self) -> None:
        def _success_runner(_source_path: str) -> dict:
            return {
                "status": "success",
                "stage": "verify",
                "module_slug": "Toolkit_Test_Module",
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _success_runner

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), "import.md")},
            content_type="multipart/form-data",
        )
        self.assertEqual(start_response.status_code, 200)
        payload = start_response.get_json() or {}
        self.assertEqual(payload.get("status"), "success")

        job = self._wait_for_terminal_job(payload["job_id"])
        self.assertEqual(job.get("status"), "completed")
        self.assertEqual(job.get("pipeline_status"), "success")
        self.assertEqual((job.get("result") or {}).get("module_slug"), "Toolkit_Test_Module")

    def test_failed_pipeline_with_quarantine_reason_maps_to_quarantined(self) -> None:
        def _quarantined_runner(_source_path: str) -> dict:
            return {
                "status": "failed",
                "stage": "dry_run",
                "dry_run": {
                    "quarantine_reason": "schema_validation_failed",
                },
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _quarantined_runner

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), "quarantine.md")},
            content_type="multipart/form-data",
        )
        self.assertEqual(start_response.status_code, 200)
        payload = start_response.get_json() or {}

        job = self._wait_for_terminal_job(payload["job_id"])
        self.assertEqual(job.get("status"), "quarantined")
        self.assertEqual(job.get("quarantine_reason"), "schema_validation_failed")
        self.assertEqual(job.get("stage"), "dry_run")

    def test_second_upload_is_rejected_while_active_job_running(self) -> None:
        def _slow_runner(_source_path: str) -> dict:
            time.sleep(0.3)
            return {
                "status": "success",
                "stage": "verify",
                "module_slug": "Slow_Module",
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _slow_runner

        first_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\nfirst"), "first.md")},
            content_type="multipart/form-data",
        )
        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\nsecond"), "second.md")},
            content_type="multipart/form-data",
        )
        self.assertEqual(second_response.status_code, 409)
        second_payload = second_response.get_json() or {}
        self.assertEqual(second_payload.get("status"), "error")
        self.assertIn("already running", second_payload.get("message", ""))


if __name__ == "__main__":
    unittest.main()
