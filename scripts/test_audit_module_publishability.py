#!/usr/bin/env python3
"""Tests for layered module publishability audit."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parent / "audit_module_publishability.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_module_publishability", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
publishability = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publishability)


class TestAuditModulePublishability(unittest.TestCase):
    def test_publishable_pass_requires_all_layers(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={"overall_status": "pass", "fix_list": [], "gates": {}},
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertEqual(report["ready_status"], "pass")
        self.assertEqual(report["publishable_status"], "pass")
        self.assertEqual(report["exit_code"], 0)

    def test_ready_can_pass_while_publishable_fails(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={"overall_status": "pass", "fix_list": [], "gates": {}},
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={
                    "status": "fail",
                    "blocking_errors": ["semantic issue"],
                    "warnings": [],
                },
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertEqual(report["ready_status"], "pass")
        self.assertEqual(report["publishable_status"], "fail")
        self.assertIn("semantic issue", report["blocking_errors"])
        self.assertEqual(report["exit_code"], 1)

    def test_readiness_failure_forces_publishable_failure(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={
                    "overall_status": "fail",
                    "fix_list": ["fix ready"],
                    "gates": {},
                },
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertEqual(report["ready_status"], "fail")
        self.assertEqual(report["publishable_status"], "fail")
        self.assertIn("readiness_gate_failed", " ".join(report["blocking_errors"]))
        self.assertIn("fix ready", report["fix_list"])


if __name__ == "__main__":
    unittest.main()
