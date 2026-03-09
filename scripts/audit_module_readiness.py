#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Module Readiness Audit
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Strict NEQ module validator that aggregates required gates:
1) Gameplay parity audit
2) Ingest sidecar audit
3) Continuity contract audit
4) Schema validation

A module is ready only when ALL enabled gates pass.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
GAMEPLAY_AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_module_gameplay.py"
SIDECAR_AUDIT_SCRIPT = REPO_ROOT / "scripts" / "homebrew_sidecar_audit.py"
SCHEMA_VALIDATOR_SCRIPT = REPO_ROOT / "core" / "validation" / "validate_module_files.py"
CONTINUITY_AUDIT_SCRIPT = REPO_ROOT / "scripts" / "module_continuity_audit.py"


def _safe_json_load(text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON if possible, otherwise return None. Handles mixed text+JSON output."""
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    
    lines = text.strip().split('\n')
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith('{'):
            try:
                candidate = '\n'.join(lines[i:])
                payload = json.loads(candidate)
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue
    
    return None


def run_gate_command(command: List[str]) -> Dict[str, Any]:
    """Execute a gate command and capture structured output."""
    completed = subprocess.run(command, capture_output=True, text=True)
    stdout_text = completed.stdout.strip()
    stderr_text = completed.stderr.strip()
    parsed = _safe_json_load(stdout_text)

    return {
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "json": parsed,
    }


def evaluate_gameplay_gate(result: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate gameplay parity gate result."""
    payload = result.get("json") or {}
    blocking_errors = payload.get("blocking_errors", []) if isinstance(payload, dict) else []
    warnings = payload.get("warnings", []) if isinstance(payload, dict) else []

    passed = result["exit_code"] == 0 and len(blocking_errors) == 0
    reason = "pass"

    if result["exit_code"] != 0:
        reason = "gameplay_audit_exit_nonzero"
    if len(blocking_errors) > 0:
        reason = "gameplay_blocking_errors"
    if result.get("json") is None:
        reason = "gameplay_output_not_json"

    return {
        "status": "pass" if passed else "fail",
        "reason": reason,
        "exit_code": result["exit_code"],
        "blocking_error_count": len(blocking_errors),
        "warning_count": len(warnings),
        "raw": result,
    }


def evaluate_sidecar_gate(result: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate ingest sidecar gate result."""
    payload = result.get("json") or {}
    valid = bool(payload.get("valid", False)) if isinstance(payload, dict) else False
    sidecar_found = bool(payload.get("sidecar_found", False)) if isinstance(payload, dict) else False

    passed = result["exit_code"] == 0 and valid and sidecar_found
    reason = "pass"

    if result.get("json") is None:
        reason = "sidecar_output_not_json"
    elif not sidecar_found:
        reason = "sidecar_missing"
    elif not valid:
        reason = "sidecar_invalid"
    elif result["exit_code"] != 0:
        reason = "sidecar_exit_nonzero"

    return {
        "status": "pass" if passed else "fail",
        "reason": reason,
        "exit_code": result["exit_code"],
        "sidecar_found": sidecar_found,
        "valid": valid,
        "raw": result,
    }


def evaluate_schema_gate(result: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate schema validation gate result."""
    payload = result.get("json") or {}

    any_failed = None
    if isinstance(payload, dict):
        summary = payload.get("summary", {})
        any_failed = summary.get("any_failed") if isinstance(summary, dict) else None

    stdout_text = result.get("stdout", "")
    stderr_text = result.get("stderr", "")
    combined = f"{stdout_text}\n{stderr_text}".lower()

    missing_jsonschema = "jsonschema is not installed" in combined
    passed = result["exit_code"] == 0 and (any_failed is False or any_failed is None)

    reason = "pass"
    if missing_jsonschema:
        reason = "schema_dependency_missing_jsonschema"
        passed = False
    elif result.get("json") is None:
        reason = "schema_output_not_json"
        passed = False
    elif any_failed is True:
        reason = "schema_validation_failures"
        passed = False
    elif result["exit_code"] != 0:
        reason = "schema_exit_nonzero"
        passed = False

    return {
        "status": "pass" if passed else "fail",
        "reason": reason,
        "exit_code": result["exit_code"],
        "any_failed": any_failed,
        "missing_jsonschema": missing_jsonschema,
        "raw": result,
    }


def evaluate_continuity_gate(result: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate continuity contract gate result."""
    payload = result.get("json") or {}
    blocking_errors = payload.get("blocking_errors", []) if isinstance(payload, dict) else []
    warnings = payload.get("warnings", []) if isinstance(payload, dict) else []
    required_keys_present = payload.get("required_keys_present", []) if isinstance(payload, dict) else []
    continuity_version = payload.get("continuity_version") if isinstance(payload, dict) else None

    passed = result["exit_code"] == 0 and len(blocking_errors) == 0
    reason = "pass"

    if result.get("json") is None:
        reason = "continuity_output_not_json"
    elif len(blocking_errors) > 0:
        reason = "continuity_blocking_errors"
    elif result["exit_code"] != 0:
        reason = "continuity_exit_nonzero"

    return {
        "status": "pass" if passed else "fail",
        "reason": reason,
        "exit_code": result["exit_code"],
        "blocking_error_count": len(blocking_errors),
        "warning_count": len(warnings),
        "required_keys_present": required_keys_present,
        "continuity_version": continuity_version,
        "raw": result,
    }


def _build_fix_list(gates: Dict[str, Dict[str, Any]]) -> List[str]:
    """Generate deterministic fix recommendations for failed gates."""
    fixes: List[str] = []

    gameplay = gates.get("gameplay", {})
    if gameplay.get("status") == "fail":
        fixes.append("Resolve gameplay blocking errors from scripts/audit_module_gameplay.py output")

    sidecar = gates.get("sidecar", {})
    if sidecar.get("status") == "fail":
        if sidecar.get("reason") == "sidecar_missing":
            fixes.append("Generate ingest sidecar artifact for slug via homebrew ingest pipeline")
        else:
            fixes.append("Fix sidecar contract issues reported by scripts/homebrew_sidecar_audit.py")

    schema = gates.get("schema", {})
    if schema.get("status") == "fail":
        if schema.get("reason") == "schema_dependency_missing_jsonschema":
            fixes.append("Install jsonschema in active environment: pip install jsonschema")
        else:
            fixes.append("Fix schema validation failures from core/validation/validate_module_files.py")

    continuity = gates.get("continuity", {})
    if continuity.get("status") == "fail":
        fixes.append("Fix continuity contract issues reported by scripts/module_continuity_audit.py")
    elif continuity.get("status") == "pass":
        raw_json = (((continuity.get("raw") or {}).get("json")) or {})
        warnings = raw_json.get("warnings", []) if isinstance(raw_json, dict) else []
        if any("cross_module_refs is empty" in str(item) for item in warnings):
            fixes.append(
                "Seed narrative cross-module refs: "
                "python3 scripts/enrich_module_cross_refs.py --module <slug> --apply"
            )

    return fixes


def audit_module_readiness(
    module_slug: str,
    include_sidecar_gate: bool = True,
    include_continuity_gate: bool = True,
    include_schema_gate: bool = True,
    strict_gameplay: bool = True,
    strict_continuity: bool = True,
) -> Dict[str, Any]:
    """Run strict module readiness audit across configured gates."""
    python_exec = sys.executable
    gates: Dict[str, Dict[str, Any]] = {}
    blocking_errors: List[str] = []

    gameplay_cmd = [
        python_exec,
        str(GAMEPLAY_AUDIT_SCRIPT),
        "--module",
        module_slug,
        "--json",
    ]
    if strict_gameplay:
        gameplay_cmd.append("--strict-instructions")

    gameplay_raw = run_gate_command(gameplay_cmd)
    gates["gameplay"] = evaluate_gameplay_gate(gameplay_raw)

    if include_sidecar_gate:
        sidecar_cmd = [
            python_exec,
            str(SIDECAR_AUDIT_SCRIPT),
            "--slug",
            module_slug,
            "--require-success",
            "--json",
        ]
        sidecar_raw = run_gate_command(sidecar_cmd)
        gates["sidecar"] = evaluate_sidecar_gate(sidecar_raw)
    else:
        gates["sidecar"] = {
            "status": "skipped",
            "reason": "gate_disabled",
            "exit_code": None,
        }

    if include_schema_gate:
        schema_cmd = [
            python_exec,
            str(SCHEMA_VALIDATOR_SCRIPT),
            "--module",
            module_slug,
            "--json",
        ]
        schema_raw = run_gate_command(schema_cmd)
        gates["schema"] = evaluate_schema_gate(schema_raw)
    else:
        gates["schema"] = {
            "status": "skipped",
            "reason": "gate_disabled",
            "exit_code": None,
        }

    if include_continuity_gate:
        continuity_cmd = [
            python_exec,
            str(CONTINUITY_AUDIT_SCRIPT),
            "--module",
            module_slug,
            "--json",
        ]
        if strict_continuity:
            continuity_cmd.append("--strict")
        continuity_raw = run_gate_command(continuity_cmd)
        gates["continuity"] = evaluate_continuity_gate(continuity_raw)
    else:
        gates["continuity"] = {
            "status": "skipped",
            "reason": "gate_disabled",
            "exit_code": None,
        }

    for gate_name in ["gameplay", "sidecar", "schema", "continuity"]:
        gate = gates.get(gate_name, {})
        if gate.get("status") == "fail":
            blocking_errors.append(f"{gate_name}_gate_failed: {gate.get('reason')}")

    fix_list = _build_fix_list(gates)

    overall_pass = True
    for gate_name in ["gameplay", "sidecar", "schema", "continuity"]:
        gate = gates.get(gate_name, {})
        if gate.get("status") == "fail":
            overall_pass = False

    return {
        "module": module_slug,
        "overall_status": "pass" if overall_pass else "fail",
        "gates": gates,
        "blocking_errors": blocking_errors,
        "fix_list": fix_list,
        "strict_contract": {
            "requires_gameplay": True,
            "requires_sidecar": include_sidecar_gate,
            "requires_continuity": include_continuity_gate,
            "requires_schema": include_schema_gate,
            "strict_gameplay": strict_gameplay,
            "strict_continuity": strict_continuity,
        },
        "exit_code": 0 if overall_pass else 1,
    }


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit_module_readiness",
        description="Strict module readiness validator for NEQ modules",
    )
    parser.add_argument("--module", type=str, required=True, help="Module slug to validate")
    parser.add_argument("--json", action="store_true", default=False, help="Output JSON report")
    parser.add_argument(
        "--no-sidecar-gate",
        action="store_true",
        default=False,
        help="Disable sidecar gate (development only)",
    )
    parser.add_argument(
        "--no-continuity-gate",
        action="store_true",
        default=False,
        help="Disable continuity gate (development only)",
    )
    parser.add_argument(
        "--no-schema-gate",
        action="store_true",
        default=False,
        help="Disable schema gate (development only)",
    )
    parser.add_argument(
        "--continuity-warn-mode",
        action="store_true",
        default=False,
        help="Run continuity gate in warn-first mode (development only)",
    )
    parser.add_argument(
        "--gameplay-dev-mode",
        action="store_true",
        default=False,
        help="Disable strict gameplay heuristic blocking (development only)",
    )
    return parser


def _print_text_report(report: Dict[str, Any]) -> None:
    print("=" * 70)
    print("NEQ MODULE READINESS AUDIT")
    print("=" * 70)
    print(f"module: {report.get('module')}")
    print(f"overall_status: {report.get('overall_status')}")
    print("")

    gates = report.get("gates", {})
    for gate_name in ["gameplay", "sidecar", "schema", "continuity"]:
        gate = gates.get(gate_name, {})
        print(f"{gate_name}: status={gate.get('status')} reason={gate.get('reason')} exit={gate.get('exit_code')}")

    if report.get("blocking_errors"):
        print("\nblocking_errors:")
        for item in report["blocking_errors"]:
            print(f"- {item}")

    if report.get("fix_list"):
        print("\nfix_list:")
        for item in report["fix_list"]:
            print(f"- {item}")


def main() -> int:
    parser = _create_parser()
    args = parser.parse_args()

    report = audit_module_readiness(
        module_slug=args.module,
        include_sidecar_gate=not args.no_sidecar_gate,
        include_continuity_gate=not args.no_continuity_gate,
        include_schema_gate=not args.no_schema_gate,
        strict_gameplay=not args.gameplay_dev_mode,
        strict_continuity=not args.continuity_warn_mode,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_text_report(report)

    return int(report.get("exit_code", 1))


if __name__ == "__main__":
    sys.exit(main())
