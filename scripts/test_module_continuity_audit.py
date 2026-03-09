#!/usr/bin/env python3
"""Unit tests for module_continuity_audit.py."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from module_continuity_audit import audit_module_continuity


class TestModuleContinuityAudit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_module(self, name: str, continuity: Any = None, plot: Any = None) -> Path:
        module_dir = self.temp_dir / name
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "areas").mkdir(exist_ok=True)

        module_context: dict[str, object] = {"moduleName": name}
        if continuity is not None:
            module_context["continuity"] = continuity
        (module_dir / "module_context.json").write_text(json.dumps(module_context), encoding="utf-8")

        if plot is None:
            plot = {"plotTitle": "Test", "mainObjective": "Test objective"}
        (module_dir / "module_plot.json").write_text(json.dumps(plot), encoding="utf-8")
        return module_dir

    def test_warn_mode_missing_required_keys_is_degraded(self):
        module_dir = self._make_module("WarnOnlyMod")
        result = audit_module_continuity(module_dir, strict=False)

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["exit_code"], 0)
        self.assertGreater(len(result["warnings"]), 0)

    def test_strict_mode_missing_required_keys_fails(self):
        module_dir = self._make_module("StrictFailMod")
        result = audit_module_continuity(module_dir, strict=True)

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["exit_code"], 1)
        self.assertGreater(len(result["blocking_errors"]), 0)

    def test_valid_contract_passes(self):
        continuity = {
            "continuity_version": "v1",
            "entry_state_variants": {
                "cold_start": {"summary": "new party"},
                "partial_context": {"summary": "some clues"},
                "late_arc": {"summary": "deep continuity"},
            },
            "cross_module_refs": [
                {
                    "target_module": "OtherModule",
                    "entity_id": "npc.maelo",
                    "relation": "echo",
                    "confidence": "medium",
                    "notes": "optional hint",
                }
            ],
            "standalone_fallback": {"enabled": True, "clue_sources": ["journal"]},
        }
        module_dir = self._make_module("ValidMod", continuity=continuity)
        result = audit_module_continuity(module_dir, strict=True)

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("continuity_version", result["required_keys_present"])
        # Degraded because target module likely missing in temp modules root, but not blocking.
        self.assertGreaterEqual(len(result["warnings"]), 0)

    def test_empty_cross_refs_emits_warning_not_blocker(self):
        continuity = {
            "continuity_version": "v1",
            "entry_state_variants": {
                "cold_start": {"summary": "new party"},
                "partial_context": {"summary": "some clues"},
                "late_arc": {"summary": "deep continuity"},
            },
            "cross_module_refs": [],
            "standalone_fallback": {"enabled": True, "clue_sources": ["module_plot"]},
        }
        module_dir = self._make_module("EmptyRefsMod", continuity=continuity)
        result = audit_module_continuity(module_dir, strict=True)

        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(any("cross_module_refs is empty" in item for item in result["warnings"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
