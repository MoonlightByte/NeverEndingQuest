#!/usr/bin/env python3
"""Regression tests for toolkit Homebrew normalization service."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils.toolkit_homebrew_normalizer import normalize_homebrew_upload
from utils.toolkit_homebrew_upload_contract import ensure_workspace_placeholders


class _FakeChoice:
    def __init__(self, content):
        self.message = type("Msg", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


class TestToolkitHomebrewNormalizer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        ensure_workspace_placeholders(self.workspace)
        self.source_path = Path(self.temp_dir.name) / "source.md"
        self.source_path.write_text("# Test Adventure\n\nA crypt and ruined gatehouse.", encoding="utf-8")
        self.preflight = {
            "source_readable": True,
            "structure_class": "unknown",
            "routing_outcome": "normalization_required",
            "ready": False,
            "can_auto_transform": False,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("utils.toolkit_homebrew_normalizer.get_model_config")
    @patch("utils.toolkit_homebrew_normalizer.create_chat_client")
    def test_successful_normalization_persists_artifacts(self, mock_client_factory, mock_model_config):
        payload = {
            "title": "Crypt of Ash",
            "author": "Unknown",
            "description": "A short ruin crawl.",
            "estimated_level_min": 1,
            "estimated_level_max": 2,
            "locations": [
                {"name": "Ruined Gate", "summary": "Collapsed outer wall"},
            ],
            "npc_seeds": [{"name": "Caretaker Noll", "role": "Guide"}],
            "monster_refs": ["Skeleton"],
            "assumptions": ["Author inferred from style clues."],
            "warnings": [{"type": "metadata_inferred", "message": "Author not explicit."}],
            "grounded_facts": ["The adventure references a crypt and gatehouse."],
            "builder_narrative": "Grounded builder summary.",
        }
        mock_client_factory.return_value = _FakeClient(json.dumps(payload))
        mock_model_config.return_value = {
            "model": "fake-model",
            "temperature": 0.3,
            "extra_body": {},
        }

        result = normalize_homebrew_upload(
            source_path=self.source_path,
            workspace=self.workspace,
            preflight=self.preflight,
            source_rights_class="user_authored",
        )

        self.assertEqual(result.get("status"), "success")
        packet_path = self.workspace / "normalized_packet.json"
        report_path = self.workspace / "normalization_report.json"
        narrative_path = self.workspace / "builder_narrative.txt"
        self.assertTrue(packet_path.exists())
        self.assertTrue(report_path.exists())
        self.assertTrue(narrative_path.exists())

        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        self.assertEqual(packet.get("normalization_state"), "normalized")
        self.assertEqual(packet.get("title"), "Crypt of Ash")
        self.assertEqual(packet.get("confidence_notes", {}).get("grounded_facts", [])[0],
                         "The adventure references a crypt and gatehouse.")
        self.assertGreater(len(packet.get("assumptions", [])), 0)

    @patch("utils.toolkit_homebrew_normalizer.get_model_config")
    @patch("utils.toolkit_homebrew_normalizer.create_chat_client")
    def test_malformed_model_output_fails_closed(self, mock_client_factory, mock_model_config):
        mock_client_factory.return_value = _FakeClient("This is not JSON")
        mock_model_config.return_value = {
            "model": "fake-model",
            "temperature": 0.3,
            "extra_body": {},
        }

        result = normalize_homebrew_upload(
            source_path=self.source_path,
            workspace=self.workspace,
            preflight=self.preflight,
            source_rights_class="user_authored",
        )

        self.assertEqual(result.get("status"), "failed")
        self.assertEqual(result.get("stage"), "normalizing")
        self.assertIn("invalid_json", str(result.get("error")))

        report = json.loads((self.workspace / "normalization_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report.get("status"), "failed")

    @patch("utils.toolkit_homebrew_normalizer.get_model_config")
    @patch("utils.toolkit_homebrew_normalizer.create_chat_client")
    @patch("utils.toolkit_homebrew_normalizer.persist_builder_narrative_artifact")
    def test_persistence_failure_rewrites_report_as_failed(
        self,
        mock_narrative_persist,
        mock_client_factory,
        mock_model_config,
    ):
        payload = {
            "title": "Crypt of Ash",
            "description": "A short ruin crawl.",
            "locations": [{"name": "Ruined Gate"}],
        }
        mock_narrative_persist.return_value = False
        mock_client_factory.return_value = _FakeClient(json.dumps(payload))
        mock_model_config.return_value = {
            "model": "fake-model",
            "temperature": 0.3,
            "extra_body": {},
        }

        result = normalize_homebrew_upload(
            source_path=self.source_path,
            workspace=self.workspace,
            preflight=self.preflight,
            source_rights_class="user_authored",
        )

        self.assertEqual(result.get("status"), "failed")
        report = json.loads((self.workspace / "normalization_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report.get("status"), "failed")
        self.assertEqual(report.get("error"), "normalization_artifact_persistence_failed")
        self.assertFalse(report.get("builder_narrative_persisted"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
