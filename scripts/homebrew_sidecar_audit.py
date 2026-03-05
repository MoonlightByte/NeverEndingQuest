#!/usr/bin/env python3
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
from typing import Any, Dict, List, Optional, Tuple

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

    # Primary match: sidecar payload module_slug (watcher nests under result).
    for sidecar in sidecars:
        payload, err = _load_json(sidecar)
        if err or not payload:
            continue
        # Support both watcher format (result.module_slug) and CLI format (module_slug)
        sidecar_slug = payload.get("module_slug") or payload.get("result", {}).get("module_slug")
        if sidecar_slug == slug:
            return sidecar

    # Fallback match: slug in filename.
    slug_lower = slug.lower()
    for sidecar in sidecars:
        if slug_lower in sidecar.name.lower():
            return sidecar

    return None


def _validate_media_section(section_name: str, section_data: Any) -> Tuple[bool, List[str]]:
    """Validate a media section (media_extract, media_handles, portrait_prewarm)."""
    errors = []
    
    if section_data is None:
        # Optional sections are OK to be missing
        return True, []
    
    if not isinstance(section_data, dict):
        errors.append(f"{section_name} must be a dictionary")
        return False, errors
    
    status = section_data.get("status")
    if status not in ["success", "degraded", "skipped", "failed", "planned"]:
        errors.append(f"{section_name}.status has unexpected value: {status}")
    
    # Check for duration_ms if stage was attempted
    if status in ["success", "degraded", "failed"]:
        duration = section_data.get("duration_ms")
        if duration is None:
            errors.append(f"{section_name} missing duration_ms for completed stage")
        elif not isinstance(duration, (int, float)):
            errors.append(f"{section_name}.duration_ms must be numeric")
    
    return len(errors) == 0, errors


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
            "media_sections": {},
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
            "media_sections": {},
            "error": f"Invalid sidecar JSON: {err}",
            "exit_code": 4,
        }

    # Support both watcher format (nested under result) and CLI format (top-level)
    result_payload = payload.get("result", payload)
    status = result_payload.get("status")
    quarantine_reason = result_payload.get("quarantine_reason")
    # Registration may be under ingest.registration (watcher) or top-level (CLI)
    registration = result_payload.get("ingest", {}).get("registration") or result_payload.get("registration", {}) or {}

    valid = True
    exit_code = 0
    errors = []

    if status not in {"success", "quarantined", "dry_run", "error", "degraded"}:
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

    # Validate media sections (fail-open: warn but don't fail overall audit)
    media_sections = {}
    media_warnings = []
    
    # Canonical key names per tasks contract
    canonical_sections = ["media_extraction", "media_handles", "portrait_prewarm"]
    # Legacy key names for backward compatibility
    legacy_map = {"media_extract": "media_extraction"}
    
    # Media sections are inside payload["result"]
    result_section = payload.get("result", {})
    
    for section_name in canonical_sections:
        section_data = result_section.get(section_name)
        
        # Check for legacy key if canonical not found
        if section_data is None and section_name in legacy_map.values():
            legacy_key = [k for k, v in legacy_map.items() if v == section_name][0]
            section_data = result_section.get(legacy_key)
            if section_data is not None:
                media_warnings.append(
                    f"Deprecated key '{legacy_key}' found; use '{section_name}' instead"
                )
        
        if section_data is not None:
            section_valid, section_errors = _validate_media_section(section_name, section_data)
            media_sections[section_name] = {
                "present": True,
                "valid": section_valid,
                "status": section_data.get("status") if isinstance(section_data, dict) else None,
                "errors": section_errors if section_errors else None,
            }
            if section_errors:
                media_warnings.extend(section_errors)
        else:
            media_sections[section_name] = {"present": False}
    
    # Check for aggregated media_warnings field
    payload_media_warnings = payload.get("media_warnings", [])
    if payload_media_warnings:
        media_warnings.extend([
            f"Media warning: {w.get('stage', 'unknown')} - {w.get('message', 'no details')}"
            for w in payload_media_warnings
        ])

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
        "media_sections": media_sections,
        "media_warnings": media_warnings if media_warnings else None,
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
        
        # Media sections summary
        media_sections = payload.get("media_sections", {})
        if media_sections:
            print("\nmedia_sections:")
            for section_name, section_info in media_sections.items():
                present = section_info.get("present", False)
                status = section_info.get("status", "N/A")
                valid = section_info.get("valid", False)
                if present:
                    print(f"  {section_name}: {status} (valid={valid})")
                else:
                    print(f"  {section_name}: not present")
        
        if payload.get("media_warnings"):
            print("\nmedia_warnings:")
            for warning in payload["media_warnings"]:
                print(f"  - {warning}")
        
        if payload.get("errors"):
            print("\nerrors:")
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
