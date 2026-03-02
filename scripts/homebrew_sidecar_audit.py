# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Sidecar Audit
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Developer-only validator for ingest sidecar result contracts.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = REPO_ROOT / "modules" / "ingest" / "archive"


def _load_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def find_latest_sidecar_for_slug(slug: str) -> Optional[Path]:
    """Find latest result sidecar by module_slug first, filename fallback second."""
    if not ARCHIVE_ROOT.exists() or not ARCHIVE_ROOT.is_dir():
        return None

    sidecars = sorted(ARCHIVE_ROOT.glob("*.result.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    # Primary match: sidecar payload module_slug.
    for sidecar in sidecars:
        payload, err = _load_json(sidecar)
        if err or not payload:
            continue
        if payload.get("module_slug") == slug:
            return sidecar

    # Fallback match: slug in filename.
    slug_lower = slug.lower()
    for sidecar in sidecars:
        if slug_lower in sidecar.name.lower():
            return sidecar

    return None


def audit_sidecar(slug: str, require_success: bool = False) -> Dict[str, Any]:
    """Audit latest sidecar for slug against status/registration contract."""
    sidecar_path = find_latest_sidecar_for_slug(slug)
    if not sidecar_path:
        return {
            "valid": False,
            "sidecar_found": False,
            "sidecar_path": None,
            "status": None,
            "quarantine_reason": None,
            "registration": {},
            "error": f"No sidecar found for slug: {slug}",
            "exit_code": 1,
        }

    payload, err = _load_json(sidecar_path)
    if err or payload is None:
        return {
            "valid": False,
            "sidecar_found": True,
            "sidecar_path": str(sidecar_path),
            "status": None,
            "quarantine_reason": None,
            "registration": {},
            "error": f"Invalid sidecar JSON: {err}",
            "exit_code": 4,
        }

    status = payload.get("status")
    quarantine_reason = payload.get("quarantine_reason")
    registration = payload.get("registration", {}) or {}

    valid = True
    exit_code = 0
    errors = []

    if status not in {"success", "quarantined", "dry_run", "error"}:
        valid = False
        exit_code = 4
        errors.append(f"Unexpected status value: {status}")

    if require_success:
        if status != "success":
            valid = False
            exit_code = 2
            errors.append(f"Status must be success (got: {status})")

        if not registration.get("registration_attempted", False):
            valid = False
            if exit_code == 0:
                exit_code = 3
            errors.append("registration.registration_attempted is false")

        if not registration.get("registry_module_present", False):
            valid = False
            if exit_code == 0:
                exit_code = 3
            errors.append("registration.registry_module_present is false")

    result = {
        "valid": valid,
        "sidecar_found": True,
        "sidecar_path": str(sidecar_path),
        "status": status,
        "quarantine_reason": quarantine_reason,
        "registration": {
            "registration_attempted": registration.get("registration_attempted", False),
            "registration_success": registration.get("registration_success", False),
            "registry_module_present": registration.get("registry_module_present", False),
            "registration_errors": registration.get("registration_errors", []),
        },
        "errors": errors,
        "exit_code": exit_code,
    }

    return result


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_sidecar_audit",
        description="Audit ingest sidecar contract for module slug",
    )
    parser.add_argument("--slug", type=str, required=True, help="Module slug")
    parser.add_argument(
        "--require-success",
        action="store_true",
        default=False,
        help="Require sidecar status=success and successful registration",
    )
    parser.add_argument("--json", action="store_true", default=False, help="Output JSON")
    return parser


def _print_json_or_text(payload: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print("=" * 60)
        print("SIDECAR AUDIT")
        print("=" * 60)
        print(f"valid: {payload.get('valid')}")
        print(f"sidecar_found: {payload.get('sidecar_found')}")
        print(f"sidecar_path: {payload.get('sidecar_path')}")
        print(f"status: {payload.get('status')}")
        print(f"quarantine_reason: {payload.get('quarantine_reason')}")
        print(f"registration: {payload.get('registration')}")
        if payload.get("errors"):
            print("errors:")
            for err in payload["errors"]:
                print(f"- {err}")


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    payload = audit_sidecar(args.slug, require_success=args.require_success)
    _print_json_or_text(payload, args.json)
    sys.exit(payload.get("exit_code", 4))


if __name__ == "__main__":
    main()
