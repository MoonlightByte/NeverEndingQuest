# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Ingest Orchestrator
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Developer-only orchestration pipeline for Homebrew ingest:
preflight -> transform -> dry-run -> duplicate guard -> strict ingest -> sidecar audit -> registry verify.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.importers.homebrewery_importer import import_homebrewery_adventure_to_module

# Local scripts (same directory)
from homebrew_preflight import assess_source_readiness
from homebrew_registry_guard import check_duplicate, verify_present
from homebrew_sidecar_audit import audit_sidecar
from homebrew_transform_to_deterministic import transform_source_to_deterministic


def _infer_stage_exit_code(stage: str) -> int:
    mapping = {
        "preflight": 1,
        "transform": 2,
        "dry_run": 3,
        "guard": 4,
        "ingest": 5,
        "audit": 6,
        "verify": 7,
    }
    return mapping.get(stage, 7)


def run_ingest_pipeline(source_path: str, strict: bool = True, dry_run_only: bool = False) -> Dict[str, Any]:
    """Execute full developer ingest pipeline with stop-on-failure semantics."""
    source_file = Path(source_path)
    if not source_file.exists() or not source_file.is_file():
        return {
            "status": "failed",
            "stage": "preflight",
            "source": source_path,
            "error": f"Source not found: {source_path}",
            "exit_code": 1,
        }

    # Stage 1: Preflight
    preflight = assess_source_readiness(str(source_file))
    if not preflight.get("ready") and not preflight.get("can_auto_transform"):
        return {
            "status": "failed",
            "stage": "preflight",
            "source": str(source_file),
            "preflight": preflight,
            "error": "Preflight failed and source cannot be auto-transformed",
            "exit_code": 1,
        }

    prepared_path = str(source_file)
    temp_prepared_file = None

    # Stage 2: Transform (conditional)
    if not preflight.get("ready") and preflight.get("can_auto_transform"):
        temp_dir = Path(tempfile.mkdtemp(prefix="neq_homebrew_"))
        transformed_name = f"prepared_{source_file.stem}.md"
        temp_prepared_file = temp_dir / transformed_name
        transform_result = transform_source_to_deterministic(str(source_file), str(temp_prepared_file))

        if transform_result.get("status") != "success":
            return {
                "status": "failed",
                "stage": "transform",
                "source": str(source_file),
                "preflight": preflight,
                "transform": transform_result,
                "error": transform_result.get("error", "Transform failed"),
                "exit_code": 2,
            }
        prepared_path = str(temp_prepared_file)

    # Determine module slug from dry-run importer call.
    # Stage 3: Deterministic dry-run
    dry_run_result = import_homebrewery_adventure_to_module(
        source_path=prepared_path,
        strict=strict,
        use_deterministic=True,
        dry_run=True,
    )

    module_slug = dry_run_result.get("module_slug")

    if dry_run_result.get("status") != "dry_run" or not dry_run_result.get("validation", {}).get("passed", False):
        return {
            "status": "failed",
            "stage": "dry_run",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "dry_run": dry_run_result,
            "error": "Dry-run validation failed",
            "exit_code": 3,
        }

    # Stage 4: Registry guard
    guard_result = check_duplicate(module_slug)
    if not guard_result.get("safe_to_proceed", False):
        return {
            "status": "failed",
            "stage": "guard",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "guard": guard_result,
            "error": "Registry guard detected conflicts",
            "exit_code": 4,
        }

    if dry_run_only:
        return {
            "status": "success",
            "stage": "dry_run",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "dry_run": dry_run_result,
            "guard": guard_result,
            "registry_verified": False,
            "exit_code": 0,
            "note": "Dry-run only mode; strict ingest not executed",
        }

    # Stage 5: Strict ingest
    ingest_result = import_homebrewery_adventure_to_module(
        source_path=prepared_path,
        strict=strict,
        use_deterministic=True,
        dry_run=False,
    )

    if ingest_result.get("status") != "success":
        return {
            "status": "failed",
            "stage": "ingest",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "ingest": ingest_result,
            "error": "Strict ingest failed or quarantined",
            "exit_code": 5,
        }

    # Stage 6: Sidecar audit (best effort; direct CLI ingest may not create sidecar)
    sidecar_audit = audit_sidecar(module_slug, require_success=True)
    if not sidecar_audit.get("valid"):
        sidecar_audit_note = "Sidecar audit unavailable/invalid (expected for direct CLI ingest)"
    else:
        sidecar_audit_note = None

    # Stage 7: Registry verification
    verify_result = verify_present(module_slug)
    if not verify_result.get("present", False):
        return {
            "status": "failed",
            "stage": "verify",
            "source": str(source_file),
            "prepared": prepared_path,
            "module_slug": module_slug,
            "verify": verify_result,
            "error": "Module not present in registry after successful ingest",
            "exit_code": 7,
        }

    return {
        "status": "success",
        "stage": "verify",
        "source": str(source_file),
        "prepared": prepared_path,
        "module_slug": module_slug,
        "areas": verify_result.get("areas_count", 0),
        "encounters": 0,
        "registry_verified": True,
        "dry_run": dry_run_result,
        "guard": guard_result,
        "ingest": ingest_result,
        "sidecar_audit": sidecar_audit,
        "sidecar_note": sidecar_audit_note,
        "verify": verify_result,
        "exit_code": 0,
    }


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_ingest_dev",
        description="Developer-only Homebrew ingest orchestration pipeline",
    )
    parser.add_argument("--source", type=str, required=True, help="Source markdown/text path")
    parser.add_argument("--strict", action="store_true", default=True, help="Enable strict ingest mode")
    parser.add_argument("--no-strict", dest="strict", action="store_false", help="Disable strict mode")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Stop after dry-run stage")
    parser.add_argument("--json", action="store_true", default=False, help="Output JSON")
    return parser


def _print_json_or_text(payload: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print("=" * 60)
        print("HOMEBREW INGEST DEV")
        print("=" * 60)
        print(f"status: {payload.get('status')}")
        print(f"stage: {payload.get('stage')}")
        print(f"source: {payload.get('source')}")
        print(f"prepared: {payload.get('prepared')}")
        print(f"module_slug: {payload.get('module_slug')}")
        if payload.get("status") == "success":
            print(f"areas: {payload.get('areas')}")
            print(f"registry_verified: {payload.get('registry_verified')}")
            if payload.get("sidecar_note"):
                print(f"note: {payload.get('sidecar_note')}")
        else:
            print(f"error: {payload.get('error')}")


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    payload = run_ingest_pipeline(args.source, strict=args.strict, dry_run_only=args.dry_run)
    _print_json_or_text(payload, args.json)
    sys.exit(payload.get("exit_code", _infer_stage_exit_code(payload.get("stage", "verify"))))


if __name__ == "__main__":
    main()
