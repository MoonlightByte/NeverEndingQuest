# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for Phase 8 toolkit Homebrew corpus quality gate."""

import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

sys.path.append(str(Path(__file__).resolve().parents[1]))

import web.routes.toolkit_homebrew_routes as toolkit_homebrew_routes
from scripts.homebrew_preflight import assess_source_readiness
from scripts.step_toolkit_homebrew_corpus_quality_gate import run_corpus_gate
from scripts.toolkit_homebrew_corpus_gate import (
    build_corpus_gate_summary,
    evaluate_developer_upload_parity,
    evaluate_terminal_outcome,
    list_external_corpus_fixtures,
    list_tracked_corpus_fixtures,
)
from utils.toolkit_homebrew_normalizer import normalize_homebrew_upload
from utils.toolkit_homebrew_upload_contract import (
    build_normalized_packet_placeholder,
    build_review_summary,
    ensure_workspace_placeholders,
    persist_builder_narrative_artifact,
    persist_normalization_report_artifact,
    persist_normalized_packet_artifact,
    validate_review_packet,
)


class _FakeChoice:
    def __init__(self, content: str):
        self.message = type("Msg", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str):
        self.chat = _FakeChat(content)


class TestCorpusFixtureContract(unittest.TestCase):
    def test_tracked_fixture_catalog_is_repo_portable(self) -> None:
        catalog = list_tracked_corpus_fixtures()
        fixtures = catalog.get("fixtures") or []
        self.assertGreaterEqual(len(fixtures), 4)
        for fixture in fixtures:
            self.assertTrue(fixture.get("exists"), msg=f"Missing tracked fixture: {fixture}")
            self.assertNotIn("Local_Docs", str(fixture.get("path") or ""))
            self.assertEqual(fixture.get("source"), "tracked")

    def test_external_corpus_requires_explicit_operator_input(self) -> None:
        result = list_external_corpus_fixtures(None)
        self.assertEqual(result.get("fixtures"), [])
        self.assertEqual(result.get("skipped"), [])
        self.assertEqual(result.get("external_path"), "")

    def test_missing_external_corpus_reports_skip_reason(self) -> None:
        result = list_external_corpus_fixtures("/tmp/does-not-exist-corpus")
        skipped = result.get("skipped") or []
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0].get("reason"), "external_corpus_path_missing")


class TestNormalizationAndReviewContractCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        ensure_workspace_placeholders(self.workspace)
        self.preflight = {
            "ready": False,
            "source_readable": True,
            "structure_class": "unknown",
            "can_auto_transform": False,
            "routing_outcome": "normalization_required",
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("utils.toolkit_homebrew_normalizer.get_model_config")
    @patch("utils.toolkit_homebrew_normalizer.create_chat_client")
    def test_tracked_fixtures_produce_reviewable_packet_shape(self, mock_client_factory, mock_model_config) -> None:
        fixtures = list_tracked_corpus_fixtures().get("fixtures") or []
        mock_model_config.return_value = {
            "model": "fake-model",
            "temperature": 0.3,
            "extra_body": {},
        }

        for fixture in fixtures:
            source_path = Path(str(fixture["path"]))
            payload = {
                "title": str(fixture.get("label") or source_path.stem),
                "author": "Corpus Author",
                "description": "Normalized from tracked corpus fixture.",
                "estimated_level_min": 1,
                "estimated_level_max": 3,
                "locations": [{"name": "Entry", "summary": "Start location"}],
                "npc_seeds": [{"name": "Guide", "role": "Ally"}],
                "monster_refs": ["Skeleton"],
                "assumptions": ["Fixture-level assumption"],
                "warnings": [],
                "grounded_facts": ["Source text is readable"],
                "builder_narrative": "Builder seed narrative.",
            }
            mock_client_factory.return_value = _FakeClient(json.dumps(payload))

            result = normalize_homebrew_upload(
                source_path=source_path,
                workspace=self.workspace,
                preflight=self.preflight,
                source_rights_class="user_authored",
            )
            self.assertEqual(result.get("status"), "success")

            packet = result.get("normalized_packet") or {}
            packet_ok, packet_error = validate_review_packet(packet)
            self.assertTrue(packet_ok, msg=packet_error)
            review_summary = build_review_summary(packet)
            self.assertTrue(str(review_summary.get("title") or "").strip())
            self.assertIsInstance(review_summary.get("locations"), list)
            self.assertIsInstance(review_summary.get("npc_seeds"), list)
            self.assertIsInstance(review_summary.get("monster_refs"), list)

    def test_readable_corpus_fixture_routes_to_normalization_not_blocked(self) -> None:
        fixtures = list_tracked_corpus_fixtures().get("fixtures") or []
        self.assertGreater(len(fixtures), 0)

        for fixture in fixtures:
            path = str(fixture.get("path") or "")
            result = assess_source_readiness(path)
            self.assertTrue(result.get("source_readable"), msg=path)
            self.assertNotEqual(result.get("routing_outcome"), "blocked_unreadable", msg=path)


class TestOutcomeClassificationAndParity(unittest.TestCase):
    def test_allowed_terminal_outcomes_are_bounded(self) -> None:
        statuses = ["completed", "not_publishable", "finishing_failed", "quarantined"]
        for status in statuses:
            result = evaluate_terminal_outcome(status)
            self.assertTrue(result.get("pass"), msg=status)
            self.assertNotEqual(result.get("classification"), "unclassified_error")

    def test_unclassified_terminal_outcome_fails_gate(self) -> None:
        result = evaluate_terminal_outcome("failed")
        self.assertFalse(result.get("pass"))
        self.assertEqual(result.get("classification"), "unclassified_error")

    def test_parity_publishable_maps_to_completed(self) -> None:
        parity = evaluate_developer_upload_parity("pass", "pass", "completed")
        self.assertTrue(parity.get("applicable"))
        self.assertTrue(parity.get("pass"))

    def test_parity_blocked_publishability_maps_to_not_publishable(self) -> None:
        parity = evaluate_developer_upload_parity("pass", "fail", "not_publishable")
        self.assertTrue(parity.get("applicable"))
        self.assertTrue(parity.get("pass"))

    def test_parity_mismatch_fails(self) -> None:
        parity = evaluate_developer_upload_parity("pass", "pass", "not_publishable")
        self.assertTrue(parity.get("applicable"))
        self.assertFalse(parity.get("pass"))


class TestFixtureDrivenUploaderOutcomes(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_upload_root = toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT
        self.original_runner = toolkit_homebrew_routes._run_shared_ingest_pipeline
        self.original_normalizer = toolkit_homebrew_routes._run_homebrew_normalization
        self.original_packet_builder = toolkit_homebrew_routes._run_homebrew_packet_build
        self.original_readiness_gate = toolkit_homebrew_routes._run_homebrew_readiness_gate
        self.original_finisher = toolkit_homebrew_routes._run_homebrew_finisher
        self.original_resolve_target = toolkit_homebrew_routes._resolve_homebrew_build_target

        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = Path(self.temp_dir.name)

        self.app = Flask(__name__)
        toolkit_homebrew_routes.register_toolkit_homebrew_routes(self.app)
        self.client = self.app.test_client()

        def _normalization_required(_source_path, artifact_workspace=None, source_rights_class="user_authored") -> dict:
            return {
                "status": "normalization_required",
                "stage": "routing",
                "routing_outcome": "normalization_required",
                "artifact_workspace": artifact_workspace,
                "source_rights_class": source_rights_class,
            }

        def _normalizer_success(source_path, artifact_workspace, preflight, source_rights_class) -> dict:
            workspace = Path(str(artifact_workspace))
            ensure_workspace_placeholders(workspace)
            packet = build_normalized_packet_placeholder(
                source_path=Path(str(source_path)),
                source_hash="fixture_hash",
                preflight=preflight,
                source_rights_class=source_rights_class,
            )
            packet["normalization_state"] = "normalized"
            packet["title"] = Path(str(source_path)).stem.replace("_", " ").title()
            packet["author"] = "Fixture Author"
            packet["description"] = "Fixture description"
            packet["locations"] = [{"name": "Entry"}]
            packet["npc_seeds"] = [{"name": "Guide"}]
            packet["monster_refs"] = ["Skeleton"]

            report = {
                "status": "success",
                "stage": "normalizing",
            }

            persist_normalized_packet_artifact(workspace, packet)
            persist_normalization_report_artifact(workspace, report)
            persist_builder_narrative_artifact(workspace, "Fixture builder narrative")

            return {
                "status": "success",
                "stage": "normalizing",
                "normalized_packet": packet,
                "normalization_report": report,
            }

        toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_required
        toolkit_homebrew_routes._run_homebrew_normalization = _normalizer_success
        toolkit_homebrew_routes._run_homebrew_packet_build = lambda workspace, job_id: {
            "status": "success",
            "stage": "build",
            "job_id": job_id,
            "module_name": "Corpus_Module",
            "output_directory": "./modules/Corpus_Module",
        }
        toolkit_homebrew_routes._run_homebrew_readiness_gate = (
            lambda artifact_workspace, job_id, state_callback=None: {
                "status": "ready_for_finishing",
                "stage": "readiness",
                "job_id": job_id,
            }
        )
        toolkit_homebrew_routes._resolve_homebrew_build_target = lambda artifact_workspace: {
            "status": "success",
            "module_name": "Corpus_Module",
            "collision": {
                "status": "success",
                "module_name": "Corpus_Module",
                "module_dir": "modules/Corpus_Module",
                "module_dir_exists": False,
            },
        }

    def tearDown(self) -> None:
        toolkit_homebrew_routes._run_shared_ingest_pipeline = self.original_runner
        toolkit_homebrew_routes._run_homebrew_normalization = self.original_normalizer
        toolkit_homebrew_routes._run_homebrew_packet_build = self.original_packet_builder
        toolkit_homebrew_routes._run_homebrew_readiness_gate = self.original_readiness_gate
        toolkit_homebrew_routes._run_homebrew_finisher = self.original_finisher
        toolkit_homebrew_routes._resolve_homebrew_build_target = self.original_resolve_target
        toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = self.original_upload_root
        toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
        self.temp_dir.cleanup()

    def _wait_for_terminal_job(self, job_id: str) -> dict:
        for _ in range(80):
            status_response = self.client.get(f"/api/toolkit/homebrew/jobs/{job_id}")
            payload = status_response.get_json() or {}
            if payload.get("status") != "success":
                time.sleep(0.05)
                continue
            job = payload.get("job") or {}
            if job.get("status") in {
                "awaiting_review",
                "completed",
                "not_publishable",
                "finishing_failed",
                "quarantined",
                "failed",
            }:
                return job
            time.sleep(0.05)
        self.fail(f"Job {job_id} did not reach a terminal state")

    def _start_upload_from_fixture(self, fixture_path: Path) -> str:
        response = self.client.post(
            "/api/toolkit/homebrew/upload",
            data={"file": (io.BytesIO(fixture_path.read_bytes()), fixture_path.name)},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        return str(payload.get("job_id") or "")

    def test_fixture_driven_clean_success_and_bounded_blocked_outcome(self) -> None:
        fixtures = list_tracked_corpus_fixtures().get("fixtures") or []
        self.assertGreaterEqual(len(fixtures), 2)

        first_fixture = Path(str(fixtures[0]["path"]))
        second_fixture = Path(str(fixtures[1]["path"]))

        finisher_by_filename = {
            first_fixture.name: {"ready_status": "pass", "publishable_status": "pass", "expected": "completed"},
            second_fixture.name: {"ready_status": "pass", "publishable_status": "fail", "expected": "not_publishable"},
        }

        run_results = []
        parity_results = []

        for fixture_path in (first_fixture, second_fixture):
            fixture_outcome = finisher_by_filename[fixture_path.name]

            toolkit_homebrew_routes._run_homebrew_finisher = lambda module_slug, outcome=fixture_outcome: {
                "status": "success",
                "module_slug": module_slug,
                "ready_status": outcome["ready_status"],
                "publishable_status": outcome["publishable_status"],
            }

            job_id = self._start_upload_from_fixture(fixture_path)
            waiting_job = self._wait_for_terminal_job(job_id)
            self.assertEqual(waiting_job.get("status"), "awaiting_review")

            review_response = self.client.post(
                f"/api/toolkit/homebrew/jobs/{job_id}/review",
                json={"decision": "approve"},
            )
            self.assertEqual(review_response.status_code, 200)

            build_response = self.client.post(
                f"/api/toolkit/homebrew/jobs/{job_id}/build",
                json={},
            )
            self.assertEqual(build_response.status_code, 200)

            final_job = self._wait_for_terminal_job(job_id)
            self.assertEqual(final_job.get("status"), fixture_outcome["expected"])

            run_eval = evaluate_terminal_outcome(str(final_job.get("status") or ""))
            run_results.append(run_eval)
            parity_results.append(
                evaluate_developer_upload_parity(
                    fixture_outcome["ready_status"],
                    fixture_outcome["publishable_status"],
                    str(final_job.get("status") or ""),
                )
            )

        summary = build_corpus_gate_summary(run_results, skipped_fixtures=[], parity_results=parity_results)
        self.assertEqual(summary.get("status"), "pass")
        self.assertEqual(summary.get("attempted"), 2)
        self.assertEqual(summary.get("classification_counts", {}).get("publishable_pass"), 1)
        self.assertEqual(summary.get("classification_counts", {}).get("not_publishable_bounded"), 1)


class TestCorpusSmokeSummary(unittest.TestCase):
    def test_smoke_script_summary_is_bounded_and_reports_skips(self) -> None:
        summary = run_corpus_gate(external_corpus_path="/tmp/nonexistent-external-corpus")
        self.assertIn(summary.get("status"), {"pass", "fail"})
        self.assertIsInstance(summary.get("attempted"), int)
        self.assertIsInstance(summary.get("skipped"), int)
        self.assertIsInstance(summary.get("classification_counts"), dict)
        self.assertIsInstance(summary.get("run_results"), list)
        self.assertIsInstance(summary.get("parity_results"), list)
        self.assertGreaterEqual(summary.get("skipped", 0), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
