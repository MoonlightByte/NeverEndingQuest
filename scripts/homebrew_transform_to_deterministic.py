# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Transform to Deterministic
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Developer-only transformer that converts Homebrew markdown into a deterministic
room-based format ingestible by NEQ importer.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Local script imports
try:
    from homebrew_preflight import _extract_metadata_block, _extract_title, _strip_title_prefix
except ImportError:
    from scripts.homebrew_preflight import _extract_metadata_block, _extract_title, _strip_title_prefix


def _extract_location_candidates(source_text: str) -> List[Dict[str, str]]:
    """Extract location bullets from ACT/LOCATION style markdown."""
    locations: List[Dict[str, str]] = []

    bullet_pattern = re.compile(
        r"^\s*[-*]\s+(?:\*\*(?P<name_bold>[^*]+)\*\*|(?P<name_plain>[^\-:\n]+))\s*(?:-|:)\s*(?P<desc>.+)$",
        re.MULTILINE,
    )

    for match in bullet_pattern.finditer(source_text):
        name = (match.group("name_bold") or match.group("name_plain") or "").strip()
        desc = (match.group("desc") or "").strip()
        if not name or not desc:
            continue
        locations.append({"name": name, "description": desc})

    deduped: List[Dict[str, str]] = []
    seen = set()
    for loc in locations:
        key = loc["name"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(loc)

    return deduped


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _infer_exits(locations: List[Dict[str, str]]) -> Dict[int, List[Dict[str, int]]]:
    """Infer exits from directional phrases and add linear fallback links."""
    exits: Dict[int, List[Dict[str, int]]] = {i: [] for i in range(len(locations))}
    normalized_names = {_normalize_name(loc["name"]): idx for idx, loc in enumerate(locations)}

    direction_pairs = {
        "north": "south",
        "south": "north",
        "east": "west",
        "west": "east",
    }

    pattern = re.compile(r"\b(north|south|east|west)\s+of\s+(?:the\s+)?([a-zA-Z0-9'\-\s]+)", re.IGNORECASE)

    for idx, loc in enumerate(locations):
        desc = loc["description"]
        for match in pattern.finditer(desc):
            relative_direction = match.group(1).lower()
            target_text = match.group(2).strip()
            target_idx = None

            target_norm = _normalize_name(target_text)
            if target_norm in normalized_names:
                target_idx = normalized_names[target_norm]
            else:
                for name_norm, candidate_idx in normalized_names.items():
                    if target_norm and target_norm in name_norm:
                        target_idx = candidate_idx
                        break

            if target_idx is None or target_idx == idx:
                continue

            # "Current is north of target" means from current exit south to target.
            outbound_direction = direction_pairs.get(relative_direction, "south")
            inbound_direction = relative_direction
            exits[idx].append({"direction": outbound_direction, "target": target_idx})
            exits[target_idx].append({"direction": inbound_direction, "target": idx})

    # Linear fallback to ensure deterministic connectivity.
    for idx in range(len(locations) - 1):
        next_idx = idx + 1
        if not any(link["target"] == next_idx for link in exits[idx]):
            exits[idx].append({"direction": "north", "target": next_idx})
        if not any(link["target"] == idx for link in exits[next_idx]):
            exits[next_idx].append({"direction": "south", "target": idx})

    return exits


def _dedupe_exit_links(links: List[Dict[str, int]]) -> List[Dict[str, int]]:
    seen = set()
    deduped = []
    for link in links:
        key = (link["direction"], link["target"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(link)
    return deduped


def _metadata_value(metadata: Dict[str, str], key: str, fallback: str) -> str:
    value = metadata.get(key, "").strip()
    return value if value else fallback


def transform_source_to_deterministic(source_path: str, output_path: str) -> Dict[str, Any]:
    """Transform source markdown into deterministic room-based markdown output."""
    source_file = Path(source_path)
    if not source_file.exists() or not source_file.is_file():
        return {
            "status": "error",
            "error": f"Source not found: {source_path}",
            "exit_code": 1,
        }

    try:
        source_text = source_file.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "status": "error",
            "error": f"Failed to read source: {exc}",
            "exit_code": 1,
        }

    metadata = _extract_metadata_block(source_text)
    raw_title = _extract_title(source_text, source_file)
    clean_title = _strip_title_prefix(raw_title)

    author = _metadata_value(metadata, "author", "Imported Homebrew")
    description = _metadata_value(metadata, "description", f"Imported adventure: {clean_title}")
    party_size_min = _metadata_value(metadata, "party_size_min", "1")
    party_size_max = _metadata_value(metadata, "party_size_max", "6")

    room_headings = re.findall(r"^##\s+Room\s+\d+:\s*.+$", source_text, re.MULTILINE | re.IGNORECASE)
    if room_headings:
        body = source_text
        # Remove existing metadata block so we can inject normalized metadata.
        body = re.sub(r"```metadata\s*.*?```\s*", "", body, flags=re.IGNORECASE | re.DOTALL)
        transformed = (
            "```metadata\n"
            f"title: {clean_title}\n"
            f"author: {author}\n"
            f"description: {description}\n"
            f"party_size_min: {party_size_min}\n"
            f"party_size_max: {party_size_max}\n"
            "```\n\n"
            f"# {clean_title}\n\n"
            f"{body.strip()}\n"
        )
    else:
        locations = _extract_location_candidates(source_text)
        if not locations:
            return {
                "status": "error",
                "error": "Cannot auto-transform: no parseable location bullets found",
                "exit_code": 2,
            }

        exits = _infer_exits(locations)

        lines: List[str] = []
        lines.extend(
            [
                "```metadata",
                f"title: {clean_title}",
                f"author: {author}",
                f"description: {description}",
                f"party_size_min: {party_size_min}",
                f"party_size_max: {party_size_max}",
                "```",
                "",
                f"# {clean_title}",
                "",
            ]
        )

        for idx, location in enumerate(locations):
            room_number = idx + 1
            lines.append(f"## Room {room_number}: {location['name']}")
            lines.append("")
            lines.append(location["description"])
            lines.append("")
            lines.append("**Exits:**")

            room_exits = _dedupe_exit_links(exits.get(idx, []))
            if room_exits:
                for link in room_exits:
                    target_room = link["target"] + 1
                    direction = link["direction"].capitalize()
                    lines.append(f"- {direction}: Room {target_room}")
            else:
                lines.append("- None")

            lines.append("")
            lines.append("<!-- Encounters: TBD -->")
            lines.append("")

        transformed = "\n".join(lines).strip() + "\n"

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_file.write_text(transformed, encoding="utf-8")
    except Exception as exc:
        return {
            "status": "error",
            "error": f"Failed to write output: {exc}",
            "exit_code": 3,
        }

    return {
        "status": "success",
        "source": str(source_file),
        "output": str(output_file),
        "title": clean_title,
        "room_count": len(re.findall(r"^##\s+Room\s+\d+:", transformed, re.MULTILINE)),
        "exit_code": 0,
    }


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_transform_to_deterministic",
        description="Convert Homebrew markdown to deterministic room-based format",
    )
    parser.add_argument("--source", type=str, required=True, help="Source markdown/text path")
    parser.add_argument("--output", type=str, required=True, help="Prepared markdown output path")
    return parser


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    result = transform_source_to_deterministic(args.source, args.output)
    if result["status"] == "success":
        print("[OK] Transform completed")
        print(f"Source: {result['source']}")
        print(f"Output: {result['output']}")
        print(f"Title: {result['title']}")
        print(f"Rooms: {result['room_count']}")
    else:
        print(f"[ERROR] {result['error']}", file=sys.stderr)

    sys.exit(result.get("exit_code", 3))


if __name__ == "__main__":
    main()
