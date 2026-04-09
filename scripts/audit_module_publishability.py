#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Standalone publishability audit layered over readiness and publication semantics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_module_readiness import audit_module_readiness
from scripts.module_semantic_authority_audit import audit_module_semantic_authority
from scripts.module_semantic_probe_harness import run_module_semantic_probes


def _resolve_module_path(module: str = "", module_path: str = "") -> Path:
    """Resolve module path from slug or explicit path."""
    if module_path:
        return Path(module_path)
    if module:
        return Path("modules") / module
    raise ValueError("Provide --module or --module-path")


def _build_fix_list(
    readiness_report: Dict[str, Any],
    semantic_audit: Dict[str, Any],
    semantic_probes: Dict[str, Any],
) -> List[str]:
    """Generate deterministic fix guidance for non-publishable modules."""
    fixes: List[str] = list(readiness_report.get("fix_list", []))

    if semantic_audit.get("status") != "pass":
        fixes.append(
            "Fix semantic publication audit findings from scripts/module_semantic_authority_audit.py"
        )

    if semantic_probes.get("status") != "pass":
        fixes.append(
            "Fix semantic probe harness findings from scripts/module_semantic_probe_harness.py"
        )

    deduped: List[str] = []
    seen = set()
    for item in fixes:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def audit_module_publishability(
    module_slug: str, module_path: str = ""
) -> Dict[str, Any]:
    """Audit one module for layered readiness and publishability."""
    resolved_module_path = _resolve_module_path(
        module=module_slug, module_path=module_path
    )
    resolved_slug = module_slug or resolved_module_path.name

    readiness_report = audit_module_readiness(resolved_slug)
    semantic_audit = audit_module_semantic_authority(resolved_module_path)
    semantic_probes = run_module_semantic_probes(resolved_module_path)

    ready_status = str(readiness_report.get("overall_status", "fail") or "fail")
    publishable_pass = (
        ready_status == "pass"
        and str(semantic_audit.get("status", "fail") or "fail") == "pass"
        and str(semantic_probes.get("status", "fail") or "fail") == "pass"
    )
    publishable_status = "pass" if publishable_pass else "fail"

    blocking_errors: List[str] = []
    if ready_status != "pass":
        blocking_errors.append(
            "readiness_gate_failed: module is not structurally ready"
        )
    if str(semantic_audit.get("status", "fail") or "fail") != "pass":
        blocking_errors.extend(semantic_audit.get("blocking_errors", []))
        if semantic_audit.get("status") == "degraded" and not semantic_audit.get(
            "blocking_errors"
        ):
            blocking_errors.append(
                "semantic_publication_audit_nonpass: semantic audit returned degraded status"
            )
    if str(semantic_probes.get("status", "fail") or "fail") != "pass":
        blocking_errors.extend(semantic_probes.get("blocking_errors", []))
        if semantic_probes.get("status") == "degraded" and not semantic_probes.get(
            "blocking_errors"
        ):
            blocking_errors.append(
                "semantic_probe_harness_nonpass: semantic probes returned degraded status"
            )

    warnings: List[str] = []
    warnings.extend(semantic_audit.get("warnings", []))
    warnings.extend(semantic_probes.get("warnings", []))

    return {
        "module": resolved_slug,
        "module_path": str(resolved_module_path),
        "ready_status": ready_status,
        "publishable_status": publishable_status,
        "readiness": readiness_report,
        "publication_gates": {
            "semantic_audit": semantic_audit,
            "semantic_probes": semantic_probes,
        },
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "fix_list": _build_fix_list(readiness_report, semantic_audit, semantic_probes),
        "exit_code": 0 if publishable_pass else 1,
    }


def _print_text_report(report: Dict[str, Any]) -> None:
    """Emit human-readable layered readiness/publishability report."""
    print("=" * 70)
    print("NEQ MODULE PUBLISHABILITY AUDIT")
    print("=" * 70)
    print(f"module: {report.get('module')}")
    print(f"ready_status: {report.get('ready_status')}")
    print(f"publishable_status: {report.get('publishable_status')}")
    print("")

    readiness = report.get("readiness", {})
    print(f"readiness.overall_status: {readiness.get('overall_status')}")
    publication_gates = report.get("publication_gates", {})
    print(
        f"semantic_audit: {publication_gates.get('semantic_audit', {}).get('status')}"
    )
    print(
        f"semantic_probes: {publication_gates.get('semantic_probes', {}).get('status')}"
    )

    if report.get("blocking_errors"):
        print("\nblocking_errors:")
        for item in report["blocking_errors"]:
            print(f"- {item}")

    if report.get("fix_list"):
        print("\nfix_list:")
        for item in report["fix_list"]:
            print(f"- {item}")


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Audit module publishability")
    parser.add_argument("--module", default="", help="Module slug (under modules/)")
    parser.add_argument("--module-path", default="", help="Explicit module path")
    parser.add_argument(
        "--json", action="store_true", default=False, help="Output JSON report"
    )
    args = parser.parse_args()

    try:
        report = audit_module_publishability(
            module_slug=args.module, module_path=args.module_path
        )
    except ValueError as exc:
        report = {
            "ready_status": "fail",
            "publishable_status": "fail",
            "blocking_errors": [str(exc)],
            "warnings": [],
            "fix_list": [],
            "exit_code": 1,
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"[ERROR] {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_text_report(report)

    return int(report.get("exit_code", 1))


if __name__ == "__main__":
    sys.exit(main())
