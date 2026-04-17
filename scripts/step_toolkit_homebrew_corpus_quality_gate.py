# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Toolkit Homebrew Corpus Quality Gate Smoke
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Golden-path smoke runner for Phase 8 corpus acceptance.

This script is deterministic and uses mocked uploader stages so operators can
verify outcome classification/parity reporting without provider dependency.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import argparse
import io
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask

sys.path.append(str(Path(__file__).resolve().parents[1]))

import web.routes.toolkit_homebrew_routes as toolkit_homebrew_routes
from scripts.homebrew_preflight import assess_source_readiness
from scripts.toolkit_homebrew_corpus_gate import (
    build_corpus_gate_summary,
    evaluate_developer_upload_parity,
    evaluate_terminal_outcome,
    list_external_corpus_fixtures,
    list_tracked_corpus_fixtures,
)
from utils.toolkit_homebrew_upload_contract import (
    build_normalized_packet_placeholder,
    ensure_workspace_placeholders,
    load_normalized_packet_artifact,
    persist_builder_narrative_artifact,
    persist_normalization_report_artifact,
    persist_normalized_packet_artifact,
)


def _wait_for_terminal_job(client: Any, job_id: str) -> Dict[str, Any]:
    for _ in range(80):
        status_response = client.get(f"/api/toolkit/homebrew/jobs/{job_id}")
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
    return {
        "status": "unknown",
        "error": f"timeout_waiting_for_job:{job_id}",
    }


def _extract_fixture_title(source_path: Path) -> str:
    """Extract a stable fixture title from markdown metadata/header."""
    try:
        text = source_path.read_text(encoding="utf-8")
    except Exception:
        return "Corpus Module"

    in_metadata = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "```metadata":
            in_metadata = True
            continue
        if in_metadata and line == "```":
            in_metadata = False
            continue
        if in_metadata and line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            if title:
                return title

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title

    return "Corpus Module"


def _run_mocked_uploader_for_fixture(
    client: Any,
    fixture_path: Path,
    publishable_status: str,
) -> Dict[str, Any]:
    upload_response = client.post(
        "/api/toolkit/homebrew/upload",
        data={"file": (io.BytesIO(fixture_path.read_bytes()), fixture_path.name)},
        content_type="multipart/form-data",
    )
    if upload_response.status_code != 200:
        return {
            "fixture": fixture_path.name,
            "status": "failed",
            "error": f"upload_http_{upload_response.status_code}",
        }

    payload = upload_response.get_json() or {}
    job_id = str(payload.get("job_id") or "")
    if not job_id:
        return {
            "fixture": fixture_path.name,
            "status": "failed",
            "error": "job_id_missing",
        }

    waiting_job = _wait_for_terminal_job(client, job_id)
    if waiting_job.get("status") != "awaiting_review":
        return {
            "fixture": fixture_path.name,
            "status": str(waiting_job.get("status") or "failed"),
            "error": "expected_awaiting_review",
        }

    review_response = client.post(
        f"/api/toolkit/homebrew/jobs/{job_id}/review",
        json={"decision": "approve"},
    )
    if review_response.status_code != 200:
        return {
            "fixture": fixture_path.name,
            "status": "failed",
            "error": f"review_http_{review_response.status_code}",
        }

    build_response = client.post(
        f"/api/toolkit/homebrew/jobs/{job_id}/build",
        json={},
    )
    if build_response.status_code != 200:
        return {
            "fixture": fixture_path.name,
            "status": "failed",
            "error": f"build_http_{build_response.status_code}",
        }

    final_job = _wait_for_terminal_job(client, job_id)
    final_status = str(final_job.get("status") or "failed")
    parity = evaluate_developer_upload_parity(
        ready_status="pass",
        publishable_status=publishable_status,
        uploader_status=final_status,
    )

    return {
        "fixture": fixture_path.name,
        "status": final_status,
        "parity": parity,
    }


def _configure_mocked_toolkit_routes() -> Dict[str, Any]:
    originals = {
        "upload_root": toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT,
        "runner": toolkit_homebrew_routes._run_shared_ingest_pipeline,
        "normalizer": toolkit_homebrew_routes._run_homebrew_normalization,
        "packet_builder": toolkit_homebrew_routes._run_homebrew_packet_build,
        "readiness_gate": toolkit_homebrew_routes._run_homebrew_readiness_gate,
        "finisher": toolkit_homebrew_routes._run_homebrew_finisher,
        "resolve_target": toolkit_homebrew_routes._resolve_homebrew_build_target,
    }

    temp_dir = tempfile.TemporaryDirectory()
    toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
    toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = Path(temp_dir.name)

    def _normalization_required(_source_path, artifact_workspace=None, source_rights_class="user_authored") -> Dict[str, Any]:
        return {
            "status": "normalization_required",
            "stage": "routing",
            "routing_outcome": "normalization_required",
            "artifact_workspace": artifact_workspace,
            "source_rights_class": source_rights_class,
        }

    def _normalizer_success(source_path, artifact_workspace, preflight, source_rights_class) -> Dict[str, Any]:
        workspace = Path(str(artifact_workspace))
        source_file = Path(str(source_path))
        ensure_workspace_placeholders(workspace)
        packet = build_normalized_packet_placeholder(
            source_path=source_file,
            source_hash="smoke_fixture_hash",
            preflight=preflight,
            source_rights_class=source_rights_class,
        )
        packet["normalization_state"] = "normalized"
        packet["title"] = _extract_fixture_title(source_file)
        packet["author"] = "Smoke Runner"
        packet["description"] = "Smoke fixture normalization output"
        packet["locations"] = [{"name": "Entry"}]
        packet["npc_seeds"] = [{"name": "Guide"}]
        packet["monster_refs"] = ["Skeleton"]

        report = {
            "status": "success",
            "stage": "normalizing",
        }

        persist_normalized_packet_artifact(workspace, packet)
        persist_normalization_report_artifact(workspace, report)
        persist_builder_narrative_artifact(workspace, "Smoke narrative")

        return {
            "status": "success",
            "stage": "normalizing",
            "normalized_packet": packet,
            "normalization_report": report,
        }

    def _finisher(module_slug: str) -> Dict[str, Any]:
        lowered = module_slug.lower()
        if "pumpkin" in lowered:
            publishable_status = "pass"
        else:
            publishable_status = "fail"
        return {
            "status": "success",
            "module_slug": module_slug,
            "ready_status": "pass",
            "publishable_status": publishable_status,
        }

    toolkit_homebrew_routes._run_shared_ingest_pipeline = _normalization_required
    toolkit_homebrew_routes._run_homebrew_normalization = _normalizer_success
    def _derive_module_name(artifact_workspace: Path) -> str:
        packet = load_normalized_packet_artifact(artifact_workspace)
        title = str(packet.get("title") or "Corpus Module").strip()
        safe = "_".join(title.split())
        return safe or "Corpus_Module"

    toolkit_homebrew_routes._run_homebrew_packet_build = lambda workspace, job_id: {
        "status": "success",
        "stage": "build",
        "job_id": job_id,
        "module_name": _derive_module_name(Path(str(workspace))),
        "output_directory": "./modules/" + _derive_module_name(Path(str(workspace))),
    }
    toolkit_homebrew_routes._run_homebrew_readiness_gate = (
        lambda artifact_workspace, job_id, state_callback=None: {
            "status": "ready_for_finishing",
            "stage": "readiness",
            "job_id": job_id,
        }
    )
    toolkit_homebrew_routes._run_homebrew_finisher = _finisher
    toolkit_homebrew_routes._resolve_homebrew_build_target = lambda artifact_workspace: {
        "status": "success",
        "module_name": _derive_module_name(Path(str(artifact_workspace))),
        "collision": {
            "status": "success",
            "module_name": _derive_module_name(Path(str(artifact_workspace))),
            "module_dir": "modules/" + _derive_module_name(Path(str(artifact_workspace))),
            "module_dir_exists": False,
        },
    }

    return {
        "temp_dir": temp_dir,
        "originals": originals,
    }


def _restore_mocked_toolkit_routes(state: Dict[str, Any]) -> None:
    originals = state["originals"]
    toolkit_homebrew_routes._run_shared_ingest_pipeline = originals["runner"]
    toolkit_homebrew_routes._run_homebrew_normalization = originals["normalizer"]
    toolkit_homebrew_routes._run_homebrew_packet_build = originals["packet_builder"]
    toolkit_homebrew_routes._run_homebrew_readiness_gate = originals["readiness_gate"]
    toolkit_homebrew_routes._run_homebrew_finisher = originals["finisher"]
    toolkit_homebrew_routes._resolve_homebrew_build_target = originals["resolve_target"]
    toolkit_homebrew_routes.TOOLKIT_HOMEBREW_UPLOAD_ROOT = originals["upload_root"]
    toolkit_homebrew_routes.reset_toolkit_homebrew_jobs_for_tests()
    state["temp_dir"].cleanup()


def run_corpus_gate(external_corpus_path: str = "") -> Dict[str, Any]:
    tracked_catalog = list_tracked_corpus_fixtures()
    external_catalog = list_external_corpus_fixtures(external_corpus_path)

    all_fixtures = []
    skipped = []

    for fixture in tracked_catalog.get("fixtures") or []:
        if fixture.get("exists"):
            all_fixtures.append(fixture)
        else:
            skipped.append(
                {
                    "fixture_id": fixture.get("fixture_id"),
                    "source": "tracked",
                    "reason": "tracked_fixture_missing",
                    "path": fixture.get("path"),
                }
            )

    skipped.extend(tracked_catalog.get("skipped") or [])
    skipped.extend(external_catalog.get("skipped") or [])

    for fixture in external_catalog.get("fixtures") or []:
        if fixture.get("exists"):
            all_fixtures.append(fixture)

    app = Flask(__name__)
    toolkit_homebrew_routes.register_toolkit_homebrew_routes(app)
    client = app.test_client()

    state = _configure_mocked_toolkit_routes()
    run_results = []
    parity_results = []

    try:
        for fixture in all_fixtures:
            fixture_path = Path(str(fixture.get("path") or ""))
            preflight = assess_source_readiness(str(fixture_path))
            if not bool(preflight.get("source_readable")):
                run_results.append(
                    {
                        "fixture": fixture_path.name,
                        "status": "failed",
                        "classification": "unclassified_error",
                        "pass": False,
                        "reason": "source_not_readable",
                    }
                )
                continue

            expected_publishable = "pass" if fixture_path.stem == "the_pumpkin_king" else "fail"
            uploader_result = _run_mocked_uploader_for_fixture(
                client=client,
                fixture_path=fixture_path,
                publishable_status=expected_publishable,
            )

            outcome = evaluate_terminal_outcome(str(uploader_result.get("status") or ""))
            run_results.append(
                {
                    "fixture": fixture_path.name,
                    "source": fixture.get("source"),
                    "classification": outcome.get("classification"),
                    "status": outcome.get("status"),
                    "pass": outcome.get("pass"),
                    "reason": outcome.get("reason"),
                }
            )

            parity = evaluate_developer_upload_parity(
                ready_status="pass",
                publishable_status=expected_publishable,
                uploader_status=str(uploader_result.get("status") or ""),
            )
            parity_results.append(
                {
                    "fixture": fixture_path.name,
                    "source": fixture.get("source"),
                    **parity,
                }
            )

        summary = build_corpus_gate_summary(
            run_results=run_results,
            skipped_fixtures=skipped,
            parity_results=parity_results,
        )
        return summary
    finally:
        _restore_mocked_toolkit_routes(state)


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="step_toolkit_homebrew_corpus_quality_gate",
        description="Run Phase 8 toolkit Homebrew corpus quality gate smoke checks.",
    )
    parser.add_argument(
        "--external-corpus",
        type=str,
        default="",
        help="Optional operator-supplied external corpus directory (no default).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit JSON summary output.",
    )
    return parser


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    summary = run_corpus_gate(external_corpus_path=args.external_corpus)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("=" * 60)
        print("TOOLKIT HOMEBREW CORPUS QUALITY GATE")
        print("=" * 60)
        print(f"Overall status: {summary.get('status')}")
        print(f"Attempted fixtures: {summary.get('attempted')}")
        print(f"Skipped fixtures: {summary.get('skipped')}")
        print("Classification counts:")
        for key, value in sorted((summary.get("classification_counts") or {}).items()):
            print(f"- {key}: {value}")
        if summary.get("failed_runs"):
            print("Failed run classifications:")
            for item in summary.get("failed_runs"):
                print(f"- {item}")
        if summary.get("failed_parity"):
            print("Failed parity checks:")
            for item in summary.get("failed_parity"):
                print(f"- {item}")

    if str(summary.get("status") or "").lower() != "pass":
        sys.exit(1)


if __name__ == "__main__":
    main()
