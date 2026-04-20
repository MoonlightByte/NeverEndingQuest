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

    semantic_audit_has_blocking = bool(semantic_audit.get("blocking_errors") or [])
    semantic_probes_has_blocking = bool(semantic_probes.get("blocking_errors") or [])

    if semantic_audit_has_blocking:
        fixes.append(
            "Fix semantic publication audit findings from scripts/module_semantic_authority_audit.py"
        )
    elif semantic_audit.get("status") != "pass":
        fixes.append(
            "Review semantic audit warnings/tooling debt and remediate if needed"
        )

    if semantic_probes_has_blocking:
        fixes.append(
            "Fix semantic probe harness findings from scripts/module_semantic_probe_harness.py"
        )
    elif semantic_probes.get("status") != "pass":
        fixes.append(
            "Review semantic probe warnings/tooling debt and remediate if needed"
        )

    readiness_toolkit_policy = readiness_report.get("toolkit_media_policy", {})
    if isinstance(readiness_toolkit_policy, dict):
        debt_count = int(readiness_toolkit_policy.get("structural_media_debt_count") or 0)
        if debt_count > 0:
            fixes.append(
                "Manual toolkit remediation required: Monster Management & Generator -> Generate Monster Images"
            )
            fixes.append(
                "Optional batch remediation: Module Media Generator -> one-click monster media generation"
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


def _collect_remediation_categories(
    *,
    source: str,
    readiness_report: Dict[str, Any],
    semantic_audit: Dict[str, Any],
    semantic_probes: Dict[str, Any],
    combined_blocking_errors: List[str],
    combined_warnings: List[str],
) -> List[str]:
    """Classify remediation paths for deterministic operator follow-up."""
    categories: List[str] = []

    readiness_gates = readiness_report.get("gates", {})
    sidecar_gate = readiness_gates.get("sidecar", {})
    sidecar_reason = str(sidecar_gate.get("reason", "") or "")

    if source == "toolkit" and sidecar_reason == "toolkit_provenance_missing":
        categories.append("provenance_ordering_bug")

    if (
        (source == "watcher" and sidecar_reason == "sidecar_missing")
        or (source == "toolkit" and sidecar_reason == "toolkit_provenance_module_mismatch")
        or (source == "toolkit" and sidecar_reason == "toolkit_provenance_invalid_shape")
    ):
        categories.append("legacy_provenance_gap")

    lowered_blocking = [str(item or "").lower() for item in combined_blocking_errors]
    lowered_warnings = [str(item or "").lower() for item in combined_warnings]

    if any(
        (
            "missing base media files" in item
            or "media/monsters" in item
            or "gameplay_gate_failed" in item
        )
        for item in lowered_blocking
    ):
        categories.append("structured_monster_media_missing")
        if source == "toolkit":
            categories.append("toolkit_manual_media_generation_required")

    readiness_toolkit_policy = readiness_report.get("toolkit_media_policy", {})
    readiness_media_debt_count = 0
    if isinstance(readiness_toolkit_policy, dict):
        readiness_media_debt_count = int(
            readiness_toolkit_policy.get("structural_media_debt_count") or 0
        )
    if readiness_media_debt_count > 0:
        categories.append("structured_monster_media_missing")
        if source == "toolkit":
            categories.append("toolkit_manual_media_generation_required")

    semantic_audit_has_blocking = bool(semantic_audit.get("blocking_errors") or [])
    semantic_probes_has_blocking = bool(semantic_probes.get("blocking_errors") or [])
    semantic_has_blocking = semantic_audit_has_blocking or semantic_probes_has_blocking

    if semantic_has_blocking:
        categories.append("semantic_publishability_blocking")

    if not semantic_has_blocking and (
        semantic_audit.get("status") != "pass" or semantic_probes.get("status") != "pass"
    ):
        categories.append("semantic_warning_only")

    if any(
        (
            "fixture_missing" in item
            or "probe_fixture" in item
            or "tooling debt" in item
            or "tooling_debt" in item
        )
        for item in lowered_warnings
    ):
        categories.append("semantic_tooling_debt")

    if (
        "structured_monster_media_missing" in categories
        and semantic_has_blocking
    ):
        categories.append("mixed_media_semantic_blocking")

    if (
        "structured_monster_media_missing" in categories
        and "semantic_warning_only" in categories
    ):
        categories.append("scene_entity_modeling_candidate")

    deduped: List[str] = []
    seen = set()
    for item in categories:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def audit_module_publishability(
    module_slug: str, module_path: str = "", source: str = "watcher"
) -> Dict[str, Any]:
    """Audit one module for layered readiness and publishability."""
    resolved_module_path = _resolve_module_path(
        module=module_slug, module_path=module_path
    )
    resolved_slug = module_slug or resolved_module_path.name

    readiness_report = audit_module_readiness(resolved_slug, source=source)
    semantic_audit = audit_module_semantic_authority(resolved_module_path)
    semantic_probes = run_module_semantic_probes(resolved_module_path)

    normalized_source = str(source or "watcher").strip().lower()
    ready_status = str(readiness_report.get("overall_status", "fail") or "fail")

    semantic_audit_blocking: List[str] = list(semantic_audit.get("blocking_errors", []))
    semantic_probe_blocking: List[str] = list(semantic_probes.get("blocking_errors", []))
    semantic_has_blocking = bool(semantic_audit_blocking or semantic_probe_blocking)

    blocking_errors: List[str] = []
    if ready_status != "pass":
        blocking_errors.append(
            "readiness_gate_failed: module is not structurally ready"
        )
    blocking_errors.extend(semantic_audit_blocking)
    blocking_errors.extend(semantic_probe_blocking)

    publishable_pass = ready_status == "pass" and not semantic_has_blocking
    publishable_status = "pass" if publishable_pass else "fail"

    warnings: List[str] = []
    warnings.extend(semantic_audit.get("warnings", []))
    warnings.extend(semantic_probes.get("warnings", []))

    remediation_categories = _collect_remediation_categories(
        source=normalized_source,
        readiness_report=readiness_report,
        semantic_audit=semantic_audit,
        semantic_probes=semantic_probes,
        combined_blocking_errors=blocking_errors,
        combined_warnings=warnings,
    )

    return {
        "module": resolved_slug,
        "module_path": str(resolved_module_path),
        "source": normalized_source,
        "ready_status": ready_status,
        "publishable_status": publishable_status,
        "readiness": readiness_report,
        "publication_gates": {
            "semantic_audit": semantic_audit,
            "semantic_probes": semantic_probes,
        },
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "remediation_categories": remediation_categories,
        "toolkit_media_policy": readiness_report.get("toolkit_media_policy", {}),
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
        "--source",
        default="watcher",
        help="Readiness provenance source: watcher or toolkit",
    )
    parser.add_argument(
        "--json", action="store_true", default=False, help="Output JSON report"
    )
    args = parser.parse_args()

    try:
        report = audit_module_publishability(
            module_slug=args.module,
            module_path=args.module_path,
            source=args.source,
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
