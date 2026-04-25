# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew packet-to-builder facade."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.toolkit_homebrew_upload_contract import ensure_workspace_placeholders, get_workspace_files
from web.extensions.toolkit_homebrew_packet_builder import run_toolkit_homebrew_packet_build


class TestToolkitHomebrewPacketBuilder(unittest.TestCase):
    """Verify packet build transform and result artifact contracts."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        ensure_workspace_placeholders(self.workspace)
        self.files = get_workspace_files(self.workspace)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_valid_packet(self) -> None:
        packet = {
            "packet_version": "v1",
            "normalization_state": "normalized",
            "source_hash": "abc123",
            "source_path": str(self.files["source_original"]),
            "title": "Packet Build Adventure",
            "author": "Tester",
            "description": "A packet-driven build test.",
            "adventure_summary": "One-shot summary.",
            "acts": [{"name": "Act I"}, {"name": "Act II"}],
            "locations": ["Gatehouse", "Crypt", "Tower"],
        }
        self.files["normalized_packet"].write_text(json.dumps(packet, indent=2), encoding="utf-8")

    def _write_approved_snapshot(self) -> None:
        snapshot = {
            "status": "recorded",
            "stage": "review",
            "job_id": "job-1",
            "decision": "approve",
            "packet_identity": {
                "packet_version": "v1",
                "source_hash": "abc123",
                "source_path": str(self.files["source_original"]),
                "title": "Packet Build Adventure",
            },
        }
        self.files["ui_review_snapshot"].write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    def test_persists_builder_input_and_build_result_on_success(self) -> None:
        self._write_valid_packet()
        self._write_approved_snapshot()
        self.files["builder_narrative"].write_text("Module: Packet Build Adventure", encoding="utf-8")

        def _executor(builder_input):
            self.assertEqual(builder_input["packet_identity"]["source_hash"], "abc123")

        result = run_toolkit_homebrew_packet_build(
            workspace=self.workspace,
            job_id="job-1",
            builder_executor=_executor,
        )

        self.assertEqual(result.get("status"), "success")
        self.assertTrue(result.get("build_result_persisted"))
        self.assertTrue(self.files["builder_input"].exists())
        self.assertTrue(self.files["build_result"].exists())

        builder_input = json.loads(self.files["builder_input"].read_text(encoding="utf-8"))
        self.assertEqual(builder_input.get("build_mode"), "packet_workspace_v1")
        self.assertEqual((builder_input.get("packet_identity") or {}).get("source_hash"), "abc123")

        build_result = json.loads(self.files["build_result"].read_text(encoding="utf-8"))
        self.assertEqual(build_result.get("status"), "success")
        self.assertEqual((build_result.get("packet_identity") or {}).get("source_hash"), "abc123")

    def test_rejects_build_when_review_snapshot_is_not_approved(self) -> None:
        self._write_valid_packet()
        self.files["ui_review_snapshot"].write_text(
            json.dumps(
                {
                    "status": "recorded",
                    "stage": "review",
                    "job_id": "job-1",
                    "decision": "reject",
                    "packet_identity": {"source_hash": "abc123"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        result = run_toolkit_homebrew_packet_build(
            workspace=self.workspace,
            job_id="job-1",
            builder_executor=lambda _builder_input: None,
        )

        self.assertEqual(result.get("status"), "failed")
        self.assertEqual(result.get("error"), "review_snapshot_not_approved")

    def test_persists_failed_build_result_when_builder_raises(self) -> None:
        self._write_valid_packet()
        self._write_approved_snapshot()

        def _failing_executor(_builder_input):
            raise RuntimeError("builder exploded")

        result = run_toolkit_homebrew_packet_build(
            workspace=self.workspace,
            job_id="job-1",
            builder_executor=_failing_executor,
        )

        self.assertEqual(result.get("status"), "failed")
        self.assertEqual(result.get("error"), "builder exploded")
        self.assertTrue(self.files["build_result"].exists())

        build_result = json.loads(self.files["build_result"].read_text(encoding="utf-8"))
        self.assertEqual(build_result.get("status"), "failed")
        self.assertEqual(build_result.get("error"), "builder exploded")

    def test_forwards_progress_callback_to_executor(self) -> None:
        self._write_valid_packet()
        self._write_approved_snapshot()
        self.files["builder_narrative"].write_text("Module: Packet Build Adventure", encoding="utf-8")

        progress_events = []

        def _executor(builder_input, progress_callback=None):
            self.assertIsNotNone(progress_callback)
            progress_callback("base_structure", "Creating directory structure...")
            progress_callback("log", "Step 3: Generating locations for each area...")
            progress_events.append(builder_input["job_id"])

        result = run_toolkit_homebrew_packet_build(
            workspace=self.workspace,
            job_id="job-1",
            builder_executor=_executor,
            progress_callback=lambda status, message: progress_events.append((status, message)),
        )

        self.assertEqual(result.get("status"), "success")
        self.assertTrue(self.files["build_result"].exists())
        self.assertIn(("base_structure", "Creating directory structure..."), progress_events)
        self.assertIn(("log", "Step 3: Generating locations for each area..."), progress_events)

    def test_module_toolkit_template_prefers_progress_message_for_building(self) -> None:
        template_path = Path(__file__).resolve().parents[1] / "web" / "templates" / "module_toolkit.html"
        template = template_path.read_text(encoding="utf-8")

        self.assertIn("job.progress_message", template)
        self.assertIn("progress_updated_at", template)


if __name__ == "__main__":
    unittest.main()
