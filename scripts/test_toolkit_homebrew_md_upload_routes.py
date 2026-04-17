# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew markdown upload routes."""

import io
import json
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
        self.original_normalizer = toolkit_homebrew_routes._run_homebrew_normalization
        self.original_packet_builder = toolkit_homebrew_routes._run_homebrew_packet_build
        self.original_readiness_gate = toolkit_homebrew_routes._run_homebrew_readiness_gate
        self.original_finisher = toolkit_homebrew_routes._run_homebrew_finisher
        self.original_resolve_build_target = toolkit_homebrew_routes._resolve_homebrew_build_target
        self.original_prepare_rebuild_target = toolkit_homebrew_routes._prepare_homebrew_rebuild_target

        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = Path(self.temp_dir.name)

        self.app = Flask(__name__)
        toolkit_homebrew_routes.register_toolkit_homebrew_routes(self.app)
        self.client = self.app.test_client()

        def _normalizer_success(source_path, artifact_workspace, preflight, source_rights_class):
            self._write_reviewable_packet(str(artifact_workspace))
            workspace = Path(artifact_workspace)
            (workspace / "normalization_report.json").write_text(
                json.dumps(
                    {
                        "status": "success",
                        "stage": "normalizing",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (workspace / "builder_narrative.txt").write_text(
                "Module: Reviewable Adventure\nSummary: Packet summary",
                encoding="utf-8",
            )
            return {
                "status": "success",
                "stage": "normalizing",
                "normalized_packet": {
                    "normalization_state": "normalized",
                    "source_path": str(source_path),
                },
                "normalization_report": {
                    "status": "success",
                },
            }

        toolkit_homebrew_routes._run_homebrew_normalization = _normalizer_success
        toolkit_homebrew_routes._run_homebrew_readiness_gate = (
            lambda artifact_workspace, job_id, state_callback=None: {
                "status": "ready_for_finishing",
                "stage": "readiness",
                "job_id": job_id,
            }
        )
        toolkit_homebrew_routes._run_homebrew_finisher = lambda module_slug: {
            "status": "success",
            "module_slug": module_slug,
            "ready_status": "pass",
            "publishable_status": "pass",
        }
        toolkit_homebrew_routes._resolve_homebrew_build_target = lambda artifact_workspace: {
            "status": "success",
            "module_name": "Reviewable_Adventure",
            "collision": {
                "status": "success",
                "module_name": "Reviewable_Adventure",
                "module_dir": "modules/Reviewable_Adventure",
                "module_dir_exists": False,
            },
        }

    def tearDown(self) -> None:
        toolkit_homebrew_routes._run_shared_ingest_pipeline = self.original_runner
        toolkit_homebrew_routes._run_homebrew_normalization = self.original_normalizer
        toolkit_homebrew_routes._run_homebrew_packet_build = self.original_packet_builder
        toolkit_homebrew_routes._run_homebrew_readiness_gate = self.original_readiness_gate
        toolkit_homebrew_routes._run_homebrew_finisher = self.original_finisher
        toolkit_homebrew_routes._resolve_homebrew_build_target = self.original_resolve_build_target
        toolkit_homebrew_routes._prepare_homebrew_rebuild_target = self.original_prepare_rebuild_target
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
            if job.get("status") in {
                "completed",
                "failed",
                "quarantined",
                "awaiting_review",
                "approved_for_build",
                "rejected",
                "build_system_failed",
                "repair_budget_exhausted",
                "awaiting_overwrite_confirmation",
                "rebuild_backup_failed",
                "rebuild_prepare_failed",
                "not_publishable",
                "finishing_failed",
            }:
                return job
            time.sleep(0.05)
        self.fail(f"Job {job_id} did not reach terminal state")

    def _create_reviewable_job(self, source_name: str = "reviewable.md") -> dict:
        def _normalization_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "normalization_required",
                "stage": "routing",
                "routing_outcome": "normalization_required",
                "artifact_workspace": artifact_workspace,
                "source_rights_class": source_rights_class,
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_runner

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), source_name)},
            content_type="multipart/form-data",
        )
        self.assertEqual(start_response.status_code, 200)
        payload = start_response.get_json() or {}
        job = self._wait_for_terminal_job(payload["job_id"])
        self.assertEqual(job.get("status"), "awaiting_review")
        return job

    def _write_reviewable_packet(self, artifact_workspace: str) -> None:
        workspace = Path(artifact_workspace)
        packet_path = workspace / "normalized_packet.json"
        packet_payload = {
            "packet_version": "v1",
            "normalization_state": "normalized",
            "source_hash": "abc123",
            "source_path": str(workspace / "source_original.md"),
            "title": "Reviewable Adventure",
            "author": "Tester",
            "description": "Packet summary",
            "estimated_level_min": 1,
            "estimated_level_max": 3,
            "locations": ["Gatehouse", "Cellar"],
            "npc_seeds": [{"name": "Kira"}],
            "monster_refs": ["Skeleton"],
            "warnings": [{"type": "structure", "message": "Needs normalization"}],
            "assumptions": ["Placeholder assumptions"],
        }
        packet_path.write_text(json.dumps(packet_payload, indent=2), encoding="utf-8")

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
        def _success_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "success",
                "stage": "verify",
                "module_slug": "Toolkit_Test_Module",
                "artifact_workspace": artifact_workspace,
                "source_rights_class": source_rights_class,
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
        def _quarantined_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
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
        def _slow_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
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

    def test_upload_job_maps_normalization_route_to_awaiting_state(self) -> None:
        def _normalization_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "normalization_required",
                "stage": "routing",
                "routing_outcome": "normalization_required",
                "artifact_workspace": artifact_workspace,
                "source_rights_class": source_rights_class,
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_runner

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), "routing.md")},
            content_type="multipart/form-data",
        )
        self.assertEqual(start_response.status_code, 200)
        payload = start_response.get_json() or {}

        job = self._wait_for_terminal_job(payload["job_id"])
        self.assertEqual(job.get("status"), "awaiting_review")
        self.assertEqual(job.get("pipeline_status"), "normalization_ready")
        self.assertEqual(job.get("routing_outcome"), "normalization_required")

    def test_review_get_returns_summary_for_awaiting_review_job(self) -> None:
        def _normalization_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "normalization_required",
                "stage": "routing",
                "routing_outcome": "normalization_required",
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_runner

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), "review.md")},
            content_type="multipart/form-data",
        )
        self.assertEqual(start_response.status_code, 200)
        payload = start_response.get_json() or {}
        job_id = payload["job_id"]
        job = self._wait_for_terminal_job(job_id)
        self.assertEqual(job.get("status"), "awaiting_review")

        review_response = self.client.get(f"/api/toolkit/homebrew/jobs/{job_id}/review")
        self.assertEqual(review_response.status_code, 200)
        review_payload = review_response.get_json() or {}
        self.assertEqual(review_payload.get("status"), "success")
        review = review_payload.get("review") or {}
        summary = review.get("review_summary") or {}
        self.assertEqual(summary.get("title"), "Reviewable Adventure")
        self.assertTrue(review.get("can_approve"))
        self.assertTrue(review.get("can_reject"))

    def test_review_approve_updates_job_and_snapshot(self) -> None:
        def _normalization_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "normalization_required",
                "stage": "routing",
                "routing_outcome": "normalization_required",
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_runner

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), "approve.md")},
            content_type="multipart/form-data",
        )
        payload = start_response.get_json() or {}
        job_id = payload["job_id"]
        job = self._wait_for_terminal_job(job_id)
        self.assertEqual(job.get("status"), "awaiting_review")

        decision_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(decision_response.status_code, 200)
        decision_payload = decision_response.get_json() or {}
        self.assertEqual(decision_payload.get("status"), "success")
        updated_job = decision_payload.get("job") or {}
        self.assertEqual(updated_job.get("status"), "approved_for_build")
        self.assertEqual(updated_job.get("review_decision"), "approve")

        snapshot_path = Path(updated_job.get("review_snapshot_path"))
        self.assertTrue(snapshot_path.exists())
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(snapshot.get("decision"), "approve")
        self.assertEqual(snapshot.get("job_id"), job_id)

    def test_review_reject_updates_job_and_snapshot(self) -> None:
        def _normalization_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "normalization_required",
                "stage": "routing",
                "routing_outcome": "normalization_required",
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_runner

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), "reject.md")},
            content_type="multipart/form-data",
        )
        payload = start_response.get_json() or {}
        job_id = payload["job_id"]
        job = self._wait_for_terminal_job(job_id)
        self.assertEqual(job.get("status"), "awaiting_review")

        decision_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "reject"},
        )
        self.assertEqual(decision_response.status_code, 200)
        decision_payload = decision_response.get_json() or {}
        self.assertEqual(decision_payload.get("status"), "success")
        updated_job = decision_payload.get("job") or {}
        self.assertEqual(updated_job.get("status"), "rejected")
        self.assertEqual(updated_job.get("review_decision"), "reject")

    def test_build_start_requires_approved_for_build_status(self) -> None:
        job = self._create_reviewable_job(source_name="build-guard.md")

        build_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job['job_id']}/build",
            json={},
        )
        self.assertEqual(build_response.status_code, 409)
        payload = build_response.get_json() or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("job_status"), "awaiting_review")

    def test_approved_job_transitions_to_completed_when_publishable(self) -> None:
        job = self._create_reviewable_job(source_name="build-success.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        def _packet_build_success(workspace: Path, build_job_id: str) -> dict:
            self.assertEqual(build_job_id, job_id)
            return {
                "status": "success",
                "stage": "build",
                "job_id": build_job_id,
                "module_name": "Reviewable_Adventure",
                "output_directory": "./modules/Reviewable_Adventure",
            }

        toolkit_homebrew_routes._run_homebrew_packet_build = _packet_build_success

        def _readiness_success(artifact_workspace: Path, job_id: str, state_callback=None) -> dict:
            self.assertEqual(job_id, job["job_id"])
            self.assertEqual(toolkit_homebrew_routes._jobs[job_id]["status"], "build_completed")
            return {
                "status": "ready_for_finishing",
                "stage": "readiness",
                "job_id": job_id,
                "module_name": "Reviewable_Adventure",
            }

        toolkit_homebrew_routes._run_homebrew_readiness_gate = _readiness_success

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(build_start.status_code, 200)
        start_payload = build_start.get_json() or {}
        self.assertEqual(start_payload.get("status"), "success")
        self.assertEqual((start_payload.get("job") or {}).get("status"), "building")

        final_job = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_job.get("status"), "completed")
        self.assertEqual(final_job.get("stage"), "finishing")
        self.assertEqual(final_job.get("pipeline_status"), "success")

    def test_publishability_block_maps_to_not_publishable(self) -> None:
        job = self._create_reviewable_job(source_name="build-blocked.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        toolkit_homebrew_routes._run_homebrew_packet_build = lambda workspace, build_job_id: {
            "status": "success",
            "stage": "build",
            "job_id": build_job_id,
            "module_name": "Reviewable_Adventure",
            "output_directory": "./modules/Reviewable_Adventure",
        }
        toolkit_homebrew_routes._run_homebrew_finisher = lambda module_slug: {
            "status": "degraded",
            "module_slug": module_slug,
            "ready_status": "pass",
            "publishable_status": "fail",
        }

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(build_start.status_code, 200)

        final_job = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_job.get("status"), "not_publishable")
        self.assertEqual(final_job.get("stage"), "finishing")
        self.assertEqual(final_job.get("pipeline_status"), "blocked")

    def test_finisher_exception_maps_to_finishing_failed(self) -> None:
        job = self._create_reviewable_job(source_name="build-finisher-fail.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        toolkit_homebrew_routes._run_homebrew_packet_build = lambda workspace, build_job_id: {
            "status": "success",
            "stage": "build",
            "job_id": build_job_id,
            "module_name": "Reviewable_Adventure",
            "output_directory": "./modules/Reviewable_Adventure",
        }

        def _raise_finisher_error(module_slug: str) -> dict:
            raise RuntimeError("finisher_boom")

        toolkit_homebrew_routes._run_homebrew_finisher = _raise_finisher_error

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(build_start.status_code, 200)

        final_job = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_job.get("status"), "finishing_failed")
        self.assertEqual(final_job.get("stage"), "finishing")
        self.assertEqual(final_job.get("pipeline_status"), "failed")
        self.assertIn("finisher_boom", str(final_job.get("error") or ""))

    def test_ready_for_finishing_job_can_resume_finisher_without_rebuild(self) -> None:
        job = self._create_reviewable_job(source_name="build-resume-finisher.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        toolkit_homebrew_routes._run_homebrew_packet_build = lambda workspace, build_job_id: {
            "status": "success",
            "stage": "build",
            "job_id": build_job_id,
            "module_name": "Reviewable_Adventure",
            "output_directory": "./modules/Reviewable_Adventure",
        }

        toolkit_homebrew_routes._run_homebrew_finisher = lambda module_slug: {
            "status": "success",
            "module_slug": module_slug,
            "ready_status": "pass",
            "publishable_status": "pass",
        }

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(build_start.status_code, 200)
        final_job = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_job.get("status"), "completed")

        toolkit_homebrew_routes._run_homebrew_packet_build = lambda workspace, build_job_id: {
            "status": "failed",
            "stage": "build",
            "job_id": build_job_id,
            "error": "should_not_rebuild",
        }

        resume_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(resume_start.status_code, 409)

        with toolkit_homebrew_routes._jobs_lock:
            resume_job = toolkit_homebrew_routes._jobs.get(job_id) or {}
            resume_job["status"] = "ready_for_finishing"
            resume_job["stage"] = "readiness"
            resume_job["pipeline_status"] = "success"

        toolkit_homebrew_routes._run_homebrew_finisher = lambda module_slug: {
            "status": "success",
            "module_slug": module_slug,
            "ready_status": "pass",
            "publishable_status": "pass",
        }

        resume_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(resume_start.status_code, 200)
        resume_payload = resume_start.get_json() or {}
        self.assertEqual((resume_payload.get("job") or {}).get("status"), "finishing")

        final_resume = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_resume.get("status"), "completed")

    def test_approved_job_build_failure_transitions_to_failed(self) -> None:
        job = self._create_reviewable_job(source_name="build-fail.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        def _packet_build_failed(workspace: Path, build_job_id: str) -> dict:
            self.assertEqual(build_job_id, job_id)
            return {
                "status": "failed",
                "stage": "build",
                "job_id": build_job_id,
                "error": "builder_failed",
            }

        toolkit_homebrew_routes._run_homebrew_packet_build = _packet_build_failed

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(build_start.status_code, 200)

        final_job = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_job.get("status"), "failed")
        self.assertEqual(final_job.get("stage"), "build")
        self.assertEqual(final_job.get("pipeline_status"), "failed")
        self.assertEqual((final_job.get("result") or {}).get("error"), "builder_failed")

    def test_build_start_existing_module_requires_confirmation(self) -> None:
        job = self._create_reviewable_job(source_name="build-collision.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        toolkit_homebrew_routes._resolve_homebrew_build_target = lambda artifact_workspace: {
            "status": "success",
            "module_name": "Reviewable_Adventure",
            "collision": {
                "status": "success",
                "module_name": "Reviewable_Adventure",
                "module_dir": "modules/Reviewable_Adventure",
                "module_dir_exists": True,
            },
        }

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(build_start.status_code, 200)
        payload = build_start.get_json() or {}
        self.assertEqual(payload.get("status"), "success")
        self.assertTrue(payload.get("requires_confirmation"))
        self.assertEqual((payload.get("job") or {}).get("status"), "awaiting_overwrite_confirmation")

        active_status = self.client.get("/api/toolkit/homebrew/jobs/active")
        active_payload = active_status.get_json() or {}
        self.assertEqual(active_payload.get("active_job_id"), None)

    def test_confirmed_overwrite_starts_backup_clean_rebuild(self) -> None:
        job = self._create_reviewable_job(source_name="build-confirmed-rebuild.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        toolkit_homebrew_routes._resolve_homebrew_build_target = lambda artifact_workspace: {
            "status": "success",
            "module_name": "Reviewable_Adventure",
            "collision": {
                "status": "success",
                "module_name": "Reviewable_Adventure",
                "module_dir": "modules/Reviewable_Adventure",
                "module_dir_exists": True,
            },
        }
        toolkit_homebrew_routes._prepare_homebrew_rebuild_target = lambda module_name, overwrite_policy: {
            "status": "success",
            "reason": "backup_created_and_target_cleaned",
            "module_name": module_name,
            "module_dir": f"modules/{module_name}",
            "backup_dir": f"modules/_rebuild_backups/{module_name}__pre_rebuild__20260413T000000Z",
            "overwrite_policy": overwrite_policy,
            "rebuild_mode": True,
        }
        toolkit_homebrew_routes._run_homebrew_packet_build = lambda workspace, build_job_id: {
            "status": "success",
            "stage": "build",
            "job_id": build_job_id,
            "module_name": "Reviewable_Adventure",
            "output_directory": "./modules/Reviewable_Adventure",
        }

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={
                "confirm_overwrite": True,
                "overwrite_policy": "backup_clean",
            },
        )
        self.assertEqual(build_start.status_code, 200)
        start_payload = build_start.get_json() or {}
        self.assertEqual(start_payload.get("status"), "success")
        self.assertEqual((start_payload.get("job") or {}).get("status"), "building")
        self.assertTrue((start_payload.get("job") or {}).get("rebuild_mode"))

        final_job = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_job.get("status"), "completed")
        self.assertTrue(final_job.get("rebuild_mode"))
        self.assertIn("_rebuild_backups", str(final_job.get("rebuild_backup_path") or ""))

    def test_confirmed_overwrite_backup_failure_stops_build(self) -> None:
        job = self._create_reviewable_job(source_name="build-rebuild-fail.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        toolkit_homebrew_routes._resolve_homebrew_build_target = lambda artifact_workspace: {
            "status": "success",
            "module_name": "Reviewable_Adventure",
            "collision": {
                "status": "success",
                "module_name": "Reviewable_Adventure",
                "module_dir": "modules/Reviewable_Adventure",
                "module_dir_exists": True,
            },
        }

        build_called = {"value": False}

        def _unexpected_build(workspace: Path, build_job_id: str) -> dict:
            build_called["value"] = True
            return {
                "status": "failed",
                "error": "should_not_run",
            }

        toolkit_homebrew_routes._run_homebrew_packet_build = _unexpected_build
        toolkit_homebrew_routes._prepare_homebrew_rebuild_target = lambda module_name, overwrite_policy: {
            "status": "rebuild_backup_failed",
            "reason": "backup_creation_failed",
            "module_name": module_name,
            "module_dir": f"modules/{module_name}",
            "backup_dir": f"modules/_rebuild_backups/{module_name}__pre_rebuild__20260413T000000Z",
            "overwrite_policy": overwrite_policy,
            "rebuild_mode": True,
        }

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={
                "confirm_overwrite": True,
                "overwrite_policy": "backup_clean",
            },
        )
        self.assertEqual(build_start.status_code, 200)

        final_job = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_job.get("status"), "rebuild_backup_failed")
        self.assertEqual(final_job.get("pipeline_status"), "failed")
        self.assertFalse(build_called["value"])

    def test_confirm_overwrite_rejects_unsupported_policy(self) -> None:
        job = self._create_reviewable_job(source_name="build-invalid-policy.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={
                "confirm_overwrite": True,
                "overwrite_policy": "delete_only",
            },
        )
        self.assertEqual(build_start.status_code, 400)
        payload = build_start.get_json() or {}
        self.assertEqual(payload.get("status"), "error")

    def test_builder_defect_readiness_maps_to_build_system_failed(self) -> None:
        job = self._create_reviewable_job(source_name="build-system-fail.md")
        job_id = job["job_id"]

        approve_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(approve_response.status_code, 200)

        toolkit_homebrew_routes._run_homebrew_packet_build = (
            lambda workspace, build_job_id: {
                "status": "success",
                "stage": "build",
                "job_id": build_job_id,
                "module_name": "Reviewable_Adventure",
            }
        )

        toolkit_homebrew_routes._run_homebrew_readiness_gate = (
            lambda artifact_workspace, job_id, state_callback=None: {
                "status": "build_system_failed",
                "stage": "readiness",
                "job_id": job_id,
                "reason": "builder_runtime_exception",
            }
        )

        build_start = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/build",
            json={},
        )
        self.assertEqual(build_start.status_code, 200)

        final_job = self._wait_for_terminal_job(job_id)
        self.assertEqual(final_job.get("status"), "build_system_failed")
        self.assertEqual(final_job.get("stage"), "readiness")
        self.assertEqual(final_job.get("pipeline_status"), "failed")

    def test_normalization_validation_fails_closed_when_packet_invalid(self) -> None:
        def _normalization_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "normalization_required",
                "stage": "routing",
                "routing_outcome": "normalization_required",
            }

        def _normalizer_invalid_packet(source_path, artifact_workspace, preflight, source_rights_class):
            # Return success without updating placeholder packet to force review validation failure.
            return {
                "status": "success",
                "stage": "normalizing",
                "normalized_packet": {
                    "normalization_state": "placeholder",
                },
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_runner
        toolkit_homebrew_routes._run_homebrew_normalization = _normalizer_invalid_packet

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), "invalid-review.md")},
            content_type="multipart/form-data",
        )
        payload = start_response.get_json() or {}
        job_id = payload["job_id"]
        job = self._wait_for_terminal_job(job_id)
        self.assertEqual(job.get("status"), "failed")
        self.assertEqual(job.get("stage"), "normalizing")
        self.assertEqual(job.get("pipeline_status"), "failed")
        validation_result = ((job.get("result") or {}).get("normalization_validation") or {})
        self.assertEqual(validation_result.get("status"), "failed")
        self.assertIn("normalized_packet_invalid", validation_result.get("error", ""))

        decision_response = self.client.post(
            f"/api/toolkit/homebrew/jobs/{job_id}/review",
            json={"decision": "approve"},
        )
        self.assertEqual(decision_response.status_code, 409)
        decision_payload = decision_response.get_json() or {}
        self.assertEqual(decision_payload.get("status"), "error")

        status_response = self.client.get(f"/api/toolkit/homebrew/jobs/{job_id}")
        status_payload = status_response.get_json() or {}
        current_job = (status_payload.get("job") or {})
        self.assertEqual(current_job.get("status"), "failed")

    def test_normalization_failure_maps_job_to_failed(self) -> None:
        def _normalization_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "normalization_required",
                "stage": "routing",
                "routing_outcome": "normalization_required",
            }

        def _normalizer_failure(source_path, artifact_workspace, preflight, source_rights_class):
            return {
                "status": "failed",
                "stage": "normalizing",
                "error": "normalizer_provider_failed",
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_runner
        toolkit_homebrew_routes._run_homebrew_normalization = _normalizer_failure

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Homebrew\n\ncontent"), "normalizer-fail.md")},
            content_type="multipart/form-data",
        )
        payload = start_response.get_json() or {}
        job = self._wait_for_terminal_job(payload["job_id"])
        self.assertEqual(job.get("status"), "failed")
        self.assertEqual(job.get("stage"), "normalizing")
        result = job.get("result") or {}
        self.assertEqual((result.get("normalization") or {}).get("status"), "failed")

    def test_upload_writes_canonical_workspace_source_file(self) -> None:
        def _success_runner(
            _source_path,
            artifact_workspace=None,
            source_rights_class="user_authored",
        ) -> dict:
            return {
                "status": "success",
                "stage": "verify",
                "module_slug": "Workspace_Module",
                "artifact_workspace": artifact_workspace,
                "source_rights_class": source_rights_class,
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _success_runner

        start_response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(b"# Canonical\n\nsource"), "workspace.md")},
            content_type="multipart/form-data",
        )
        self.assertEqual(start_response.status_code, 200)
        payload = start_response.get_json() or {}

        job = self._wait_for_terminal_job(payload["job_id"])
        workspace = Path(job.get("artifact_workspace"))
        self.assertTrue((workspace / "source_original.md").exists())
        self.assertTrue((workspace / "source_preflight.json").exists())

    def test_module_toolkit_template_has_review_controls(self) -> None:
        template_source = Path("web/templates/module_toolkit.html").read_text(encoding="utf-8")
        self.assertIn("homebrew-review-panel", template_source)
        self.assertIn("homebrew-review-approve-btn", template_source)
        self.assertIn("homebrew-review-reject-btn", template_source)
        self.assertIn("homebrew-build-start-btn", template_source)
        self.assertIn("awaiting_review", template_source)
        self.assertIn("approved_for_build", template_source)
        self.assertIn("awaiting_overwrite_confirmation", template_source)
        self.assertIn("rebuild_backup_running", template_source)
        self.assertIn("rebuild_clean_running", template_source)
        self.assertIn("rebuild_backup_failed", template_source)
        self.assertIn("rebuild_prepare_failed", template_source)
        self.assertIn("build_completed", template_source)
        self.assertIn("ready_for_finishing", template_source)
        self.assertIn("finishing", template_source)
        self.assertIn("publishability_audit", template_source)
        self.assertIn("not_publishable", template_source)
        self.assertIn("finishing_failed", template_source)
        self.assertIn("repairing_deterministic", template_source)
        self.assertIn("repairing_semantic", template_source)
        self.assertIn("building", template_source)

    def test_route_uses_shared_finisher_helper(self) -> None:
        source = Path("web/routes/toolkit_homebrew_routes.py").read_text(encoding="utf-8")
        self.assertIn("def _run_homebrew_finisher", source)
        self.assertIn("run_toolkit_module_postbuild_finishing", source)
        self.assertIn("publishability_audit", source)
        self.assertIn("not_publishable", source)
        self.assertIn("finishing_failed", source)


if __name__ == "__main__":
    unittest.main()
