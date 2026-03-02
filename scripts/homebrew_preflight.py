# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Preflight
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Developer-only readiness checks for Homebrew markdown ingest.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


TITLE_PREFIX_PATTERNS = [
    r"^CLONE\s*-\s*ADVENTURE:\s*",
    r"^CLONE\s*-\s*",
    r"^CLONE:\s*",
]


def _extract_metadata_block(source_text: str) -> Dict[str, str]:
    """Extract key-value pairs from fenced metadata block."""
    match = re.search(r"```metadata\s*(.*?)```", source_text, re.IGNORECASE | re.DOTALL)
    if not match:
        return {}

    metadata: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip('"').strip("'")
    return metadata


def _extract_title(source_text: str, source_file: Path) -> str:
    """Best-effort title extraction from metadata, H1, or filename."""
    metadata = _extract_metadata_block(source_text)
    if metadata.get("title"):
        return metadata["title"]

    h1_match = re.search(r"^#\s+(.+)$", source_text, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()

    return source_file.stem


def _strip_title_prefix(title: str) -> str:
    """Return title with known clone prefixes removed."""
    cleaned = title.strip()
    for pattern in TITLE_PREFIX_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or title.strip()


def _classify_structure(source_text: str) -> str:
    """Classify source structure for deterministic ingest readiness."""
    if re.search(r"^##\s+Room\s+\d+:\s*.+$", source_text, re.MULTILINE | re.IGNORECASE):
        return "room_based"

    has_act = re.search(r"^##\s*ACT\b", source_text, re.MULTILINE | re.IGNORECASE) is not None
    has_locations_header = re.search(
        r"^###\s+LOCATIONS\b", source_text, re.MULTILINE | re.IGNORECASE
    ) is not None
    if has_act and has_locations_header:
        return "act_location"

    return "unknown"


def _has_parseable_location_bullets(source_text: str) -> bool:
    """Detect if source has bullet locations that transform can parse."""
    return re.search(
        r"^\s*[-*]\s+(\*\*[^*]+\*\*|[^\n:]+)\s*(?:-|:)\s*.+$",
        source_text,
        re.MULTILINE,
    ) is not None


def assess_source_readiness(source_path: str) -> Dict[str, Any]:
    """Run preflight checks and return structured readiness report."""
    source_file = Path(source_path)
    if not source_file.exists() or not source_file.is_file():
        return {
            "ready": False,
            "issues": [
                {
                    "type": "source_missing",
                    "severity": "blocked",
                    "current": source_path,
                    "recommended": "Provide an existing markdown/text file",
                }
            ],
            "structure_class": "unknown",
            "can_auto_transform": False,
        }

    try:
        source_text = source_file.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "ready": False,
            "issues": [
                {
                    "type": "read_error",
                    "severity": "blocked",
                    "current": str(exc),
                    "recommended": "Fix file encoding/permissions and retry",
                }
            ],
            "structure_class": "unknown",
            "can_auto_transform": False,
        }

    issues: List[Dict[str, Any]] = []
    metadata = _extract_metadata_block(source_text)
    title = _extract_title(source_text, source_file)
    normalized_title = _strip_title_prefix(title)

    if normalized_title != title:
        issues.append(
            {
                "type": "title_hygiene",
                "severity": "fixable",
                "current": title,
                "recommended": normalized_title,
            }
        )

    for required_field in ["title", "author", "description"]:
        if not metadata.get(required_field):
            issues.append(
                {
                    "type": "metadata_missing",
                    "severity": "fixable",
                    "field": required_field,
                    "current": "",
                    "recommended": f"Add metadata field '{required_field}'",
                }
            )

    structure_class = _classify_structure(source_text)
    can_auto_transform = False

    if structure_class == "room_based":
        can_auto_transform = True
    elif structure_class == "act_location":
        can_auto_transform = _has_parseable_location_bullets(source_text)
        if not can_auto_transform:
            issues.append(
                {
                    "type": "structure_parseability",
                    "severity": "manual_required",
                    "current": "ACT/LOCATION without parseable location bullets",
                    "recommended": "Add '- **Location** - description' bullets under LOCATIONS",
                }
            )
    else:
        issues.append(
            {
                "type": "structure_unknown",
                "severity": "manual_required",
                "current": "No deterministic room or ACT/LOCATION structure found",
                "recommended": "Convert source to room-based or ACT/LOCATION format",
            }
        )

    blocking_issue_types = {"source_missing", "read_error", "structure_unknown", "structure_parseability"}
    has_blocking = any(issue.get("type") in blocking_issue_types for issue in issues)
    ready = not has_blocking and structure_class == "room_based" and not any(
        issue.get("type") == "metadata_missing" for issue in issues
    ) and not any(issue.get("type") == "title_hygiene" for issue in issues)

    return {
        "ready": ready,
        "issues": issues,
        "structure_class": structure_class,
        "can_auto_transform": can_auto_transform,
        "source": str(source_file),
        "title": title,
        "normalized_title": normalized_title,
    }


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_preflight",
        description="Assess Homebrew source readiness for deterministic NEQ ingest",
    )
    parser.add_argument("--source", type=str, required=True, help="Source markdown/text path")
    parser.add_argument("--json", action="store_true", default=False, help="Output JSON")
    return parser


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    result = assess_source_readiness(args.source)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("HOMEBREW PREFLIGHT")
        print("=" * 60)
        print(f"Source: {result['source']}")
        print(f"Structure: {result['structure_class']}")
        print(f"Ready: {result['ready']}")
        print(f"Can auto-transform: {result['can_auto_transform']}")
        if result["issues"]:
            print("Issues:")
            for issue in result["issues"]:
                print(f"- {issue.get('type')}: {issue.get('recommended', '')}")

    if any(issue.get("type") == "source_missing" for issue in result["issues"]):
        sys.exit(1)
    if any(issue.get("type") == "read_error" for issue in result["issues"]):
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
