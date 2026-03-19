# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Helpers for derived location-context provenance and runtime hygiene."""

import re
from typing import Any, Dict, Optional

_PROVENANCE_PATTERN = re.compile(
    r"\[LOCATION_PROVENANCE\s+module=(?P<module>[^\s]+)\s+area=(?P<area>[^\s]+)\s+location=(?P<location>[^\s]+)\s+kind=(?P<kind>[^\]]+)\]"
)


def build_location_provenance_line(module_name: str, area_id: str, location_id: str, source_kind: str) -> str:
    module_value = str(module_name or "unknown").replace(" ", "_")
    area_value = str(area_id or "unknown")
    location_value = str(location_id or "unknown")
    kind_value = str(source_kind or "unknown")
    return (
        f"[LOCATION_PROVENANCE module={module_value} area={area_value} "
        f"location={location_value} kind={kind_value}]"
    )


def inject_location_provenance(content: str, module_name: str, area_id: str, location_id: str, source_kind: str) -> str:
    if not isinstance(content, str):
        return content
    if _PROVENANCE_PATTERN.search(content):
        return content

    provenance_line = build_location_provenance_line(module_name, area_id, location_id, source_kind)
    parts = content.split("\n\n", 1)
    if len(parts) == 2:
        return f"{parts[0]}\n{provenance_line}\n\n{parts[1]}"
    return f"{content}\n{provenance_line}"


def parse_location_provenance(content: str) -> Optional[Dict[str, str]]:
    if not isinstance(content, str):
        return None
    match = _PROVENANCE_PATTERN.search(content)
    if not match:
        return None
    return {
        "module": match.group("module"),
        "area": match.group("area"),
        "location": match.group("location"),
        "kind": match.group("kind"),
    }


def is_location_summary_content(content: str) -> bool:
    if not isinstance(content, str):
        return False
    return (
        "[SUMMARY OF EVENTS AT THIS LOCATION]" in content
        or "=== LOCATION SUMMARY ===" in content
    )


def is_location_chronicle_content(content: str) -> bool:
    if not isinstance(content, str):
        return False
    return "=== LOCATION CHRONICLE" in content


def is_derived_location_context_message(message: Any) -> bool:
    if not isinstance(message, dict):
        return False
    if message.get("role") != "assistant":
        return False
    content = str(message.get("content", ""))
    return is_location_summary_content(content) or is_location_chronicle_content(content)


def extract_location_id_from_content(content: str) -> Optional[str]:
    if not isinstance(content, str):
        return None

    provenance = parse_location_provenance(content)
    if provenance and provenance.get("location") and provenance.get("location") != "unknown":
        return provenance["location"]

    patterns = [
        r"current location \(([A-Z]+\d+)\)",
        r"=== LOCATION CHRONICLE: .*?\(([A-Z]+\d+)\)",
        r"=== LOCATION SUMMARY ===\n\n.*?\(([A-Z]+\d+)\)",
        r"\(([A-Z]+\d+)\):",
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    return None


def derived_context_matches_scene(message: Dict[str, Any], module_name: str, location_id: str) -> bool:
    if not is_derived_location_context_message(message):
        return False
    content = str(message.get("content", ""))
    provenance = parse_location_provenance(content)
    normalized_module = str(module_name or "").replace(" ", "_")
    normalized_location = str(location_id or "")

    if provenance:
        if provenance.get("module") != normalized_module:
            return False
        if provenance.get("location") != normalized_location:
            return False
        return True

    legacy_location = extract_location_id_from_content(content)
    if not legacy_location:
        return False
    return legacy_location == normalized_location
