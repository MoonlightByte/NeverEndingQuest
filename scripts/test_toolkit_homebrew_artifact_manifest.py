# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew artifact manifest helper."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.routes.toolkit_homebrew_routes import _build_artifact_manifest


class TestBuildArtifactManifest(unittest.TestCase):
    """Verify build_artifact_manifest helper returns correct structure."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_artifact(self, name: str, content: str = "content") -> None:
        (self.workspace / name).write_text(content, encoding="utf-8")

    def test_all_artifact_keys_present_when_none_exist(self) -> None:
        manifest = _build_artifact_manifest(self.workspace, "completed")
        self.assertIn("workspace", manifest)
        self.assertIn("artifacts", manifest)
        self.assertIn("rebuild_eligible", manifest)
        self.assertIn("cleanup_allowed", manifest)

        expected_keys = [
            "source_original",
            "normalized_packet",
            "normalization_report",
            "ui_review_snapshot",
            "builder_input",
            "build_result",
            "readiness_validation_report",
            "readiness_audit_report",
            "repair_report",
            "finishing_report",
        ]
        self.assertEqual(sorted(manifest["artifacts"].keys()), sorted(expected_keys))

    def test_artifact_exists_true_when_file_present(self) -> None:
        self._write_artifact("normalized_packet.json")
        manifest = _build_artifact_manifest(self.workspace, "completed")
        self.assertEqual(
            manifest["artifacts"]["normalized_packet"],
            {"exists": True, "path": str(self.workspace / "normalized_packet.json"), "size_bytes": 7},
        )

    def test_artifact_exists_false_when_file_missing(self) -> None:
        manifest = _build_artifact_manifest(self.workspace, "completed")
        self.assertEqual(
            manifest["artifacts"]["normalized_packet"],
            {"exists": False},
        )

    def test_artifact_size_bytes_returns_file_size(self) -> None:
        self._write_artifact("source_original.md", "hello world")
        manifest = _build_artifact_manifest(self.workspace, "queued")
        self.assertEqual(
            manifest["artifacts"]["source_original"]["size_bytes"],
            11,
        )

    def test_artifact_path_absent_when_file_missing(self) -> None:
        manifest = _build_artifact_manifest(self.workspace, "completed")
        artifact = manifest["artifacts"]["source_original"]
        self.assertFalse(artifact["exists"])
        self.assertNotIn("path", artifact)
        self.assertNotIn("size_bytes", artifact)

    def test_rebuild_eligible_from_packet_true_in_terminal_state(self) -> None:
        self._write_artifact("normalized_packet.json")
        for terminal_status in ("completed", "not_publishable", "quarantined", "failed", "rejected", "awaiting_overwrite_confirmation"):
            manifest = _build_artifact_manifest(self.workspace, terminal_status)
            self.assertTrue(
                manifest["rebuild_eligible"]["from_packet"],
                f"Expected from_packet=True for status={terminal_status}",
            )

    def test_rebuild_eligible_from_packet_false_in_non_terminal_state(self) -> None:
        self._write_artifact("normalized_packet.json")
        for non_terminal_status in ("queued", "running", "awaiting_review", "approved_for_build", "building", "ready_for_finishing", "finishing", "publishability_audit"):
            manifest = _build_artifact_manifest(self.workspace, non_terminal_status)
            self.assertFalse(
                manifest["rebuild_eligible"]["from_packet"],
                f"Expected from_packet=False for status={non_terminal_status}",
            )

    def test_rebuild_eligible_from_packet_false_when_normalized_missing(self) -> None:
        manifest = _build_artifact_manifest(self.workspace, "completed")
        self.assertFalse(manifest["rebuild_eligible"]["from_packet"])

    def test_rebuild_eligible_from_finishing_true_when_build_artifacts_and_finishing_state(self) -> None:
        self._write_artifact("builder_input.json")
        self._write_artifact("build_result.json")
        for finishing_status in ("ready_for_finishing", "finishing", "publishability_audit", "completed", "not_publishable", "quarantined", "failed"):
            manifest = _build_artifact_manifest(self.workspace, finishing_status)
            self.assertTrue(
                manifest["rebuild_eligible"]["from_finishing"],
                f"Expected from_finishing=True for status={finishing_status}",
            )

    def test_rebuild_eligible_from_finishing_false_when_builder_input_missing(self) -> None:
        self._write_artifact("build_result.json")
        manifest = _build_artifact_manifest(self.workspace, "ready_for_finishing")
        self.assertFalse(manifest["rebuild_eligible"]["from_finishing"])

    def test_rebuild_eligible_from_finishing_false_when_build_result_missing(self) -> None:
        self._write_artifact("builder_input.json")
        manifest = _build_artifact_manifest(self.workspace, "ready_for_finishing")
        self.assertFalse(manifest["rebuild_eligible"]["from_finishing"])

    def test_rebuild_eligible_from_finishing_false_in_non_finishing_state(self) -> None:
        self._write_artifact("builder_input.json")
        self._write_artifact("build_result.json")
        for non_finishing_status in ("queued", "running", "awaiting_review", "approved_for_build", "building"):
            manifest = _build_artifact_manifest(self.workspace, non_finishing_status)
            self.assertFalse(
                manifest["rebuild_eligible"]["from_finishing"],
                f"Expected from_finishing=False for status={non_finishing_status}",
            )

    def test_cleanup_allowed_true_in_terminal_state(self) -> None:
        for terminal_status in ("completed", "not_publishable", "quarantined", "failed", "rejected", "awaiting_overwrite_confirmation"):
            manifest = _build_artifact_manifest(self.workspace, terminal_status)
            self.assertTrue(
                manifest["cleanup_allowed"],
                f"Expected cleanup_allowed=True for status={terminal_status}",
            )

    def test_cleanup_allowed_false_in_non_terminal_state(self) -> None:
        for non_terminal_status in ("queued", "running", "awaiting_review", "approved_for_build", "building", "ready_for_finishing", "finishing", "publishability_audit"):
            manifest = _build_artifact_manifest(self.workspace, non_terminal_status)
            self.assertFalse(
                manifest["cleanup_allowed"],
                f"Expected cleanup_allowed=False for status={non_terminal_status}",
            )

    def test_workspace_path_in_manifest(self) -> None:
        manifest = _build_artifact_manifest(self.workspace, "completed")
        self.assertEqual(manifest["workspace"], str(self.workspace))

    def test_all_ten_artifacts_tracked_independently(self) -> None:
        self._write_artifact("source_original.md")
        self._write_artifact("normalized_packet.json")
        self._write_artifact("normalization_report.json")
        self._write_artifact("ui_review_snapshot.json")
        self._write_artifact("builder_input.json")
        self._write_artifact("build_result.json")
        self._write_artifact("readiness_validation_report.json")
        self._write_artifact("readiness_audit_report.json")
        self._write_artifact("repair_report.json")
        self._write_artifact("finishing_report.json")

        manifest = _build_artifact_manifest(self.workspace, "completed")

        for key in manifest["artifacts"]:
            self.assertTrue(
                manifest["artifacts"][key]["exists"],
                f"Expected exists=True for {key}",
            )
            self.assertIn("path", manifest["artifacts"][key])
            self.assertIn("size_bytes", manifest["artifacts"][key])


if __name__ == "__main__":
    unittest.main()
