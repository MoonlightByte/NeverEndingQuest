# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Tests for strict NEQ module readiness audit.
"""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parent / "audit_module_readiness.py"
SPEC = importlib.util.spec_from_file_location("audit_module_readiness", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readiness)


def _result(exit_code, payload=None, stdout="", stderr=""):
    return {
        "command": "cmd",
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "json": payload,
    }


class TestAuditModuleReadiness(unittest.TestCase):
    def test_all_gates_pass(self):
        gameplay_payload = {"blocking_errors": [], "warnings": []}
        sidecar_payload = {"valid": True, "sidecar_found": True}
        schema_payload = {"summary": {"any_failed": False}}
        continuity_payload = {"blocking_errors": [], "warnings": [], "required_keys_present": [], "continuity_version": "v1"}

        with patch.object(
            readiness,
            "run_gate_command",
            side_effect=[
                _result(0, gameplay_payload),
                _result(0, sidecar_payload),
                _result(0, schema_payload),
                _result(0, continuity_payload),
            ],
        ):
            report = readiness.audit_module_readiness("example_module")

        self.assertEqual(report["overall_status"], "pass")
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["gates"]["gameplay"]["status"], "pass")
        self.assertEqual(report["gates"]["sidecar"]["status"], "pass")
        self.assertEqual(report["gates"]["schema"]["status"], "pass")
        self.assertEqual(report["gates"]["continuity"]["status"], "pass")

    def test_sidecar_missing_fails(self):
        gameplay_payload = {"blocking_errors": [], "warnings": []}
        sidecar_payload = {
            "valid": False,
            "sidecar_found": False,
            "error": "No sidecar found for slug",
        }
        schema_payload = {"summary": {"any_failed": False}}
        continuity_payload = {"blocking_errors": [], "warnings": [], "required_keys_present": [], "continuity_version": "v1"}

        with patch.object(
            readiness,
            "run_gate_command",
            side_effect=[
                _result(0, gameplay_payload),
                _result(1, sidecar_payload),
                _result(0, schema_payload),
                _result(0, continuity_payload),
            ],
        ):
            report = readiness.audit_module_readiness("example_module")

        self.assertEqual(report["overall_status"], "fail")
        self.assertEqual(report["gates"]["sidecar"]["status"], "fail")
        self.assertEqual(report["gates"]["sidecar"]["reason"], "sidecar_missing")
        self.assertIn("Generate ingest sidecar artifact", " ".join(report["fix_list"]))

    def test_schema_missing_jsonschema_fails(self):
        gameplay_payload = {"blocking_errors": [], "warnings": []}
        sidecar_payload = {"valid": True, "sidecar_found": True}
        schema_stdout = "[ERROR] jsonschema is not installed. Install it via 'pip install jsonschema'."
        continuity_payload = {"blocking_errors": [], "warnings": [], "required_keys_present": [], "continuity_version": "v1"}

        with patch.object(
            readiness,
            "run_gate_command",
            side_effect=[
                _result(0, gameplay_payload),
                _result(0, sidecar_payload),
                _result(2, None, stdout=schema_stdout),
                _result(0, continuity_payload),
            ],
        ):
            report = readiness.audit_module_readiness("example_module")

        self.assertEqual(report["overall_status"], "fail")
        self.assertEqual(report["gates"]["schema"]["status"], "fail")
        self.assertEqual(
            report["gates"]["schema"]["reason"],
            "schema_dependency_missing_jsonschema",
        )
        self.assertIn("Install jsonschema", " ".join(report["fix_list"]))

    def test_gameplay_blockers_fail(self):
        gameplay_payload = {
            "blocking_errors": ["missing monster JSON"],
            "warnings": [],
        }
        sidecar_payload = {"valid": True, "sidecar_found": True}
        schema_payload = {"summary": {"any_failed": False}}
        continuity_payload = {"blocking_errors": [], "warnings": [], "required_keys_present": [], "continuity_version": "v1"}

        with patch.object(
            readiness,
            "run_gate_command",
            side_effect=[
                _result(1, gameplay_payload),
                _result(0, sidecar_payload),
                _result(0, schema_payload),
                _result(0, continuity_payload),
            ],
        ):
            report = readiness.audit_module_readiness("example_module")

        self.assertEqual(report["overall_status"], "fail")
        self.assertEqual(report["gates"]["gameplay"]["status"], "fail")
        self.assertEqual(report["gates"]["gameplay"]["reason"], "gameplay_blocking_errors")

    def test_dev_mode_skips_optional_gates(self):
        gameplay_payload = {"blocking_errors": [], "warnings": []}

        with patch.object(
            readiness,
            "run_gate_command",
            side_effect=[_result(0, gameplay_payload)],
        ):
            report = readiness.audit_module_readiness(
                "example_module",
                include_sidecar_gate=False,
                include_continuity_gate=False,
                include_schema_gate=False,
                strict_gameplay=False,
            )

        self.assertEqual(report["overall_status"], "pass")
        self.assertEqual(report["gates"]["sidecar"]["status"], "skipped")
        self.assertEqual(report["gates"]["continuity"]["status"], "skipped")
        self.assertEqual(report["gates"]["schema"]["status"], "skipped")
        self.assertFalse(report["strict_contract"]["strict_gameplay"])

    def test_continuity_blockers_fail(self):
        gameplay_payload = {"blocking_errors": [], "warnings": []}
        sidecar_payload = {"valid": True, "sidecar_found": True}
        schema_payload = {"summary": {"any_failed": False}}
        continuity_payload = {
            "blocking_errors": ["Missing required continuity keys: ['entry_state_variants']"],
            "warnings": [],
            "required_keys_present": ["continuity_version"],
            "continuity_version": "v1",
        }

        with patch.object(
            readiness,
            "run_gate_command",
            side_effect=[
                _result(0, gameplay_payload),
                _result(0, sidecar_payload),
                _result(0, schema_payload),
                _result(1, continuity_payload),
            ],
        ):
            report = readiness.audit_module_readiness("example_module")

        self.assertEqual(report["overall_status"], "fail")
        self.assertEqual(report["gates"]["continuity"]["status"], "fail")
        self.assertEqual(report["gates"]["continuity"]["reason"], "continuity_blocking_errors")


if __name__ == "__main__":
    unittest.main()
