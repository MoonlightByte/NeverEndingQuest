# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Importer - Homebrewery Markdown Import
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Initial importer for Homebrewery/GMBinder text exports.
Uses deterministic content cleaning and NEQ module generation via the
existing AI-driven module builder.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 2. Third-party imports

# 3. Internal module imports (grouped by layer)
from utils.enhanced_logger import debug, error, info, warning
from utils.file_operations import safe_write_json

# Guarded imports for optional dependencies
try:
    from core.validation.validate_module_files import ModuleValidator
    VALIDATOR_AVAILABLE = True
except Exception:
    VALIDATOR_AVAILABLE = False
    ModuleValidator = None  # type: ignore

try:
    from core.generators.module_builder import ai_driven_module_creation
    AI_MODULE_BUILDER_AVAILABLE = True
except Exception:
    AI_MODULE_BUILDER_AVAILABLE = False
    ai_driven_module_creation = None  # type: ignore

try:
    from core.generators.module_stitcher import ModuleStitcher
    STITCHER_AVAILABLE = True
except Exception:
    STITCHER_AVAILABLE = False
    ModuleStitcher = None  # type: ignore


def _sanitize_module_slug(raw_name: str) -> str:
    """Convert source title/name into NEQ-safe module slug."""
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", raw_name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if cleaned:
        return cleaned
    return f"Imported_Module_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _extract_metadata_title(source_text: str) -> Optional[str]:
    """Extract title from fenced metadata block when available."""
    metadata_match = re.search(r"```metadata\s*(.*?)```", source_text, re.IGNORECASE | re.DOTALL)
    if not metadata_match:
        return None

    metadata_text = metadata_match.group(1)
    for line in metadata_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() == "title":
            title = value.strip().strip('"').strip("'")
            return title or None

    return None


def _strip_presentation_blocks(source_text: str) -> str:
    """Remove layout and styling artifacts to keep semantic adventure text."""
    cleaned = source_text

    # Remove fenced CSS blocks.
    cleaned = re.sub(r"```css\s*.*?```", "\n", cleaned, flags=re.IGNORECASE | re.DOTALL)

    # Remove HTML style blocks.
    cleaned = re.sub(r"<style.*?>.*?</style>", "\n", cleaned, flags=re.IGNORECASE | re.DOTALL)

    # Remove common Homebrewery display macros and page markers.
    cleaned_lines: List[str] = []
    ignored_prefixes = (
        "{{frontCover",
        "{{logo",
        "{{banner",
        "{{artist",
        "{{footnote",
        "{{pageNumber",
        "{{toc",
        "\\page",
        "\\column",
    )

    for line in cleaned.splitlines():
        stripped = line.strip()

        # Drop pure macro lines and pure HTML tags used for layout wrappers.
        if not stripped:
            cleaned_lines.append("")
            continue
        if stripped.startswith(ignored_prefixes):
            continue
        if stripped.startswith("<") and stripped.endswith(">"):
            continue

        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)

    # Collapse repeated whitespace while preserving line breaks.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _build_import_narrative(title: str, source_path: str, semantic_text: str) -> str:
    """Create bounded narrative payload for module generation."""
    max_chars = 28000
    bounded_text = semantic_text[:max_chars]

    return (
        f"Source import request: {title}\n"
        f"Source file: {source_path}\n"
        "Treat this as a structured adventure source. Preserve chapter/room flow, "
        "challenge progression, and finale continuity.\n\n"
        "--- SOURCE CONTENT START ---\n"
        f"{bounded_text}\n"
        "--- SOURCE CONTENT END ---\n"
    )


def _parse_room_blocks(semantic_text: str) -> List[Dict[str, Any]]:
    """
    Extract room blocks from semantic text using ## Room N: pattern.
    Returns rooms in source order with extracted subsections.
    """
    rooms: List[Dict[str, Any]] = []

    # Pattern to match room headings: ## Room 1: Title or ## Room 100: Title
    room_pattern = re.compile(
        r"^##\s+Room\s+(\d+):\s*(.+)$",
        re.MULTILINE | re.IGNORECASE
    )

    # Find all room positions
    matches = list(room_pattern.finditer(semantic_text))

    for i, match in enumerate(matches):
        room_number = int(match.group(1))
        room_title = match.group(2).strip()

        # Determine content boundaries
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(semantic_text)
        room_content = semantic_text[start_pos:end_pos]

        # Extract subsections
        subsections = _extract_subsections(room_content)

        # Extract any markdown tables
        tables = _extract_markdown_tables(room_content)

        room_record = {
            "source_room_number": room_number,
            "source_room_title": room_title,
            "name": f"Room {room_number}: {room_title}",
            "description": subsections.get("description", ""),
            "puzzle": subsections.get("puzzle", ""),
            "solution": subsections.get("solution", ""),
            "creatures": subsections.get("creatures", ""),
            "exit_comment": subsections.get("exit_comment", ""),
            "other_sections": subsections.get("other", {}),
            "tables": tables,
            "raw_content": room_content.strip(),
        }
        rooms.append(room_record)

    return rooms


def _extract_subsections(room_content: str) -> Dict[str, Any]:
    """
    Extract common adventure subsections from room content.
    Returns dict with keys: description, puzzle, solution, creatures, exit_comment, other.
    """
    subsections: Dict[str, Any] = {
        "description": "",
        "puzzle": "",
        "solution": "",
        "creatures": "",
        "exit_comment": "",
        "other": {},
    }

    # Pattern for ### subsections
    subsection_pattern = re.compile(
        r"^###\s+(.+)$",
        re.MULTILINE | re.IGNORECASE
    )

    # Find all subsection positions
    matches = list(subsection_pattern.finditer(room_content))

    for i, match in enumerate(matches):
        section_title = match.group(1).strip()
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(room_content)
        section_content = room_content[start_pos:end_pos].strip()

        # Normalize title for matching
        title_lower = section_title.lower()

        # Route to appropriate bucket
        if "puzzle" in title_lower:
            subsections["puzzle"] = section_content
        elif "solution" in title_lower:
            subsections["solution"] = section_content
        elif "creature" in title_lower or "monster" in title_lower or "enemy" in title_lower:
            subsections["creatures"] = section_content
        elif "exit" in title_lower and "comment" in title_lower:
            subsections["exit_comment"] = section_content
        elif any(x in title_lower for x in ["burble", "birble", "dm note", "dm notes"]):
            # DM instructions / flavor text
            subsections["other"][section_title] = section_content
        else:
            # First non-matching subsection before puzzle is description
            if not subsections["description"] and "puzzle" not in title_lower:
                subsections["description"] = section_content
            else:
                subsections["other"][section_title] = section_content

    # If no description extracted, use first paragraph of content
    if not subsections["description"] and room_content.strip():
        lines = room_content.strip().split("\n")
        first_para = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                break
            first_para.append(line)
        if first_para:
            subsections["description"] = " ".join(first_para)

    return subsections


def _extract_markdown_tables(content: str) -> List[Dict[str, Any]]:
    """
    Extract markdown tables from content.
    Returns list of table dicts with headers and rows.
    """
    tables: List[Dict[str, Any]] = []

    # Pattern for markdown tables
    table_pattern = re.compile(
        r"\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)",
        re.MULTILINE
    )

    for match in table_pattern.finditer(content):
        header_line = match.group(1)
        rows_text = match.group(2)

        # Parse headers
        headers = [h.strip() for h in header_line.split("|") if h.strip()]

        # Parse rows
        rows: List[List[str]] = []
        for row_line in rows_text.strip().split("\n"):
            if "|" in row_line:
                row_cells = [c.strip() for c in row_line.split("|") if c.strip() or c == ""]
                if row_cells:
                    rows.append(row_cells)

        if headers and rows:
            tables.append({
                "headers": headers,
                "rows": rows,
                "raw": match.group(0),
            })

    return tables


def _build_intermediate_adventure(
    title: str,
    source_path: str,
    rooms: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build normalized intermediate adventure structure from parsed rooms.
    This is the canonical deterministic extraction result before NEQ emission.
    """
    # Derive module type from content
    module_type = "dungeon"

    # Estimate level range from room count/complexity
    room_count = len(rooms)
    if room_count <= 10:
        level_min, level_max = 1, 4
    elif room_count <= 20:
        level_min, level_max = 3, 6
    else:
        level_min, level_max = 5, 10

    # Build chapter structure from room groups
    chapters: List[Dict[str, Any]] = []
    current_chapter: Dict[str, Any] = {"title": "The Challenge Rooms", "summary": "", "rooms": []}

    for room in rooms:
        # Simple grouping: first room is introduction, last few are finale
        if room["source_room_number"] == 1 and not current_chapter["rooms"]:
            current_chapter["title"] = "Introduction"

        current_chapter["rooms"].append(room)

    # If we have a finale room (Room 100 or similar outlier), make it final chapter
    if rooms and rooms[-1]["source_room_number"] >= 100:
        # Split into chapters
        intro_rooms = [r for r in rooms if r["source_room_number"] == 1]
        challenge_rooms = [r for r in rooms if 2 <= r["source_room_number"] < 100]
        finale_rooms = [r for r in rooms if r["source_room_number"] >= 100]

        chapters = []
        if intro_rooms:
            chapters.append({
                "title": "Introduction",
                "summary": "The hook and entry to the academy.",
                "rooms": intro_rooms,
            })
        if challenge_rooms:
            chapters.append({
                "title": "The Challenge Rooms",
                "summary": "A series of puzzles and trials.",
                "rooms": challenge_rooms,
            })
        if finale_rooms:
            chapters.append({
                "title": "Finale",
                "summary": "The final confrontation and resolution.",
                "rooms": finale_rooms,
            })
    else:
        chapters = [current_chapter]

    return {
        "source": {
            "path": source_path,
            "title": title,
            "room_count": room_count,
        },
        "module_seed": {
            "module_name": "",
            "module_description": f"Imported adventure: {title}",
            "level_min": level_min,
            "level_max": level_max,
            "module_type": module_type,
        },
        "chapters": chapters,
        "rooms": rooms,
        "appendix": {
            "magic_items": [],
            "stat_blocks": [],
        },
    }


def _generate_neq_ids(module_slug: str, rooms: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """
    Generate sequential NEQ area and location IDs.
    Returns (area_id, list_of_location_ids) where IDs are NEQ-sequential,
    NOT derived from source room numbers.
    """
    # Create module prefix from first 3 chars of slug, uppercase
    prefix = module_slug[:3].upper()
    if len(prefix) < 3:
        prefix = prefix + "X" * (3 - len(prefix))

    area_id = f"{prefix}001"

    # Generate sequential location IDs: PREFIX01, PREFIX02, etc.
    location_ids = []
    for i in range(len(rooms)):
        loc_id = f"{prefix}{i + 1:02d}"
        location_ids.append(loc_id)

    return area_id, location_ids


def _emit_module_context(
    module_path: Path,
    module_slug: str,
    intermediate: Dict[str, Any],
    area_id: str,
    location_ids: List[str],
) -> Path:
    """Emit module_context.json with deterministic structure."""
    module_path.mkdir(parents=True, exist_ok=True)

    rooms = intermediate.get("rooms", [])
    areas = {}
    npcs = {}
    locations = {}

    # Build area entry
    areas[area_id] = {
        "name": f"{module_slug} Main Area",
        "type": intermediate["module_seed"].get("module_type", "dungeon"),
        "locations": location_ids,
        "npcs": [],
        "plot_points": [],
    }

    # Build location entries with sequential IDs
    for i, room in enumerate(rooms):
        loc_id = location_ids[i]
        locations[loc_id] = {
            "name": room["name"],
            "type": "room",
            "description_preview": room.get("description", "")[:100],
            "source_room_number": room.get("source_room_number"),
        }

    context = {
        "module_name": module_slug,
        "module_id": module_slug,
        "areas": areas,
        "npcs": npcs,
        "locations": locations,
        "plot_scopes": {},
        "references": {},
        "validation_issues": [],
        "generated_at": datetime.now().isoformat(),
        "import_source": intermediate["source"],
    }

    context_path = module_path / "module_context.json"
    safe_write_json(str(context_path), context)
    return context_path


def _emit_module_plot(
    module_path: Path,
    module_slug: str,
    intermediate: Dict[str, Any],
    area_id: str,
    location_ids: List[str],
) -> Path:
    """Emit module_plot.json with sequential plot points."""
    rooms = intermediate.get("rooms", [])
    chapters = intermediate.get("chapters", [])

    plot_points = []

    # Create plot points for each room using sequential IDs
    for i, room in enumerate(rooms):
        loc_id = location_ids[i]

        # Determine plot point type based on position
        if i == 0:
            plot_type = "introduction"
        elif i == len(rooms) - 1 and room.get("source_room_number", 0) >= 100:
            plot_type = "finale"
        else:
            plot_type = "challenge"

        plot_point = {
            "id": f"PP{i + 1:03d}",
            "title": room["name"],
            "description": room.get("description", room["name"]),
            "location": loc_id,
            "nextPoints": [f"PP{i + 2:03d}"] if i < len(rooms) - 1 else [],
            "status": "not started",
            "plotImpact": f"{plot_type.capitalize()} room progression",
            "source_room_number": room.get("source_room_number"),
        }
        plot_points.append(plot_point)

    # Build main plot objective from first chapter
    main_objective = "Complete the adventure"
    if chapters:
        main_objective = chapters[0].get("summary", main_objective)

    plot = {
        "plotTitle": f"{module_slug} Adventure",
        "mainObjective": main_objective,
        "plotPoints": plot_points,
        "import_metadata": {
            "source_title": intermediate["source"].get("title"),
            "room_count": len(rooms),
            "area_id": area_id,
        },
    }

    plot_path = module_path / "module_plot.json"
    safe_write_json(str(plot_path), plot)
    return plot_path


def _emit_area_file(
    module_path: Path,
    module_slug: str,
    intermediate: Dict[str, Any],
    area_id: str,
    location_ids: List[str],
) -> Path:
    """Emit areas/<AREA>.json with location definitions."""
    areas_dir = module_path / "areas"
    areas_dir.mkdir(parents=True, exist_ok=True)

    rooms = intermediate.get("rooms", [])

    # Build locations array
    locations = []
    for i, room in enumerate(rooms):
        loc_id = location_ids[i]

        location = {
            "locationId": loc_id,
            "name": room["name"],
            "description": room.get("description", ""),
            "source_room_number": room.get("source_room_number"),
            "source_room_title": room.get("source_room_title"),
        }

        # Add optional fields if present
        if room.get("puzzle"):
            location["puzzle"] = room["puzzle"]
        if room.get("solution"):
            location["solution"] = room["solution"]
        if room.get("creatures"):
            location["creatures"] = room["creatures"]
        if room.get("exit_comment"):
            location["exit_comment"] = room["exit_comment"]
        if room.get("tables"):
            location["tables"] = room["tables"]

        locations.append(location)

    area = {
        "areaId": area_id,
        "areaName": f"{module_slug} Main Area",
        "areaDescription": intermediate["module_seed"].get("module_description", ""),
        "locations": locations,
    }

    area_path = areas_dir / f"{area_id}.json"
    safe_write_json(str(area_path), area)
    return area_path


def _emit_map_file(
    module_path: Path,
    module_slug: str,
    intermediate: Dict[str, Any],
    area_id: str,
    location_ids: List[str],
) -> Path:
    """Emit map_<AREA>.json with room connectivity."""
    rooms = intermediate.get("rooms", [])

    # Build rooms list for map
    map_rooms = []
    for i, room in enumerate(rooms):
        loc_id = location_ids[i]

        # Determine connections (linear progression by default)
        connections = []
        if i > 0:
            connections.append(location_ids[i - 1])  # Previous room
        if i < len(rooms) - 1:
            connections.append(location_ids[i + 1])  # Next room

        map_room = {
            "id": loc_id,
            "name": room["name"],
            "connections": connections,
            "coordinates": f"X{i}Y0",  # Linear layout, schema requires string
        }
        map_rooms.append(map_room)

    # Simple 1D layout
    layout = [[loc_id] for loc_id in location_ids]

    map_data = {
        "mapName": f"{module_slug} Map",
        "mapId": f"map_{area_id}",
        "totalRooms": len(rooms),
        "rooms": map_rooms,
        "layout": layout,
    }

    map_path = module_path / f"map_{area_id}.json"
    safe_write_json(str(map_path), map_data)
    return map_path


def _emit_neq_artifacts(
    module_path: Path,
    module_slug: str,
    intermediate: Dict[str, Any],
) -> List[str]:
    """
    Emit all deterministic NEQ module artifacts with sequential IDs.
    Returns list of created file paths.
    """
    rooms = intermediate.get("rooms", [])
    if not rooms:
        return []

    # Generate sequential NEQ IDs (NOT derived from source room numbers)
    area_id, location_ids = _generate_neq_ids(module_slug, rooms)

    artifacts = []

    # Emit module_context.json
    context_path = _emit_module_context(module_path, module_slug, intermediate, area_id, location_ids)
    artifacts.append(str(context_path))

    # Emit module_plot.json
    plot_path = _emit_module_plot(module_path, module_slug, intermediate, area_id, location_ids)
    artifacts.append(str(plot_path))

    # Emit areas/<AREA>.json
    area_path = _emit_area_file(module_path, module_slug, intermediate, area_id, location_ids)
    artifacts.append(str(area_path))

    # Emit map_<AREA>.json
    map_path = _emit_map_file(module_path, module_slug, intermediate, area_id, location_ids)
    artifacts.append(str(map_path))

    return artifacts


def _validate_module_artifacts(module_path: Path, schema_dir: Path) -> Dict[str, Any]:
    """Run module validation and return structured results."""
    if not VALIDATOR_AVAILABLE or ModuleValidator is None:
        # Skip validation when validator dependencies unavailable
        return {
            "passed": True,
            "failed_count": 0,
            "success_rate": 1.0,
            "errors": [],
            "note": "Validation skipped (validator dependencies unavailable)",
        }

    validator = ModuleValidator(str(module_path), str(schema_dir))
    validator.load_schemas()
    validator.run_all_validations()

    errors: List[str] = []
    total_failed = 0

    for category, result in validator.results.items():
        failed = int(result.get("failed", 0) or 0)
        total_failed += failed
        result_errors = result.get("errors", []) or []
        for err in result_errors:
            errors.append(f"{category}: {err}")

    return {
        "passed": total_failed == 0,
        "failed_count": total_failed,
        "success_rate": validator.get_success_rate(),
        "errors": errors,
    }


def _collect_artifacts(module_path: Path, repo_root: Path) -> List[str]:
    """Collect generated JSON artifact paths as repo-relative strings."""
    artifact_paths: List[str] = []
    if not module_path.exists():
        return artifact_paths

    for json_file in sorted(module_path.rglob("*.json")):
        try:
            artifact_paths.append(os.path.relpath(str(json_file), str(repo_root)))
        except Exception:
            artifact_paths.append(str(json_file))

    return artifact_paths


def _register_module_if_valid(
    module_slug: str,
    validation_passed: bool,
    strict: bool,
) -> Dict[str, Any]:
    """
    Register module in world registry after strict validation passes.
    Returns registration audit result with attempted/success/present/errors fields.
    """
    result: Dict[str, Any] = {
        "registration_attempted": False,
        "registration_success": False,
        "registry_module_present": False,
        "registration_errors": [],
    }

    # Only attempt registration if validation passed and strict mode is on
    if not validation_passed:
        return result

    if not strict:
        # Non-strict mode: skip registration attempt
        result["registration_errors"].append("Registration skipped in non-strict mode")
        return result

    if not STITCHER_AVAILABLE or ModuleStitcher is None:
        result["registration_attempted"] = True
        result["registration_errors"].append("ModuleStitcher not available")
        return result

    try:
        result["registration_attempted"] = True
        stitcher = ModuleStitcher()

        # Attempt integration (integrate_module returns bool)
        integration_success = stitcher.integrate_module(module_slug)

        if integration_success:
            result["registration_success"] = True
        else:
            result["registration_errors"].append("Module integration returned False")

        # Verify registry presence
        if module_slug in stitcher.world_registry.get("modules", {}):
            result["registry_module_present"] = True
        else:
            result["registration_errors"].append("Module not found in registry after integration")

    except Exception as e:
        result["registration_attempted"] = True
        result["registration_errors"].append(f"Registration exception: {str(e)}")

    return result


def import_homebrewery_adventure_to_module(
    source_path: str,
    module_slug: Optional[str] = None,
    output_root: str = "modules",
    strict: bool = True,
    llm_enrich: bool = True,
    parse_appendix_stats: bool = True,
    use_deterministic: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Parse Homebrewery markdown export into NEQ module artifacts.

    Notes:
        - Deterministic path (use_deterministic=True): uses parsed structure + sequential IDs.
        - AI-driven path (use_deterministic=False): uses ai_driven_module_creation.
        - `llm_enrich` and `parse_appendix_stats` are reserved for upcoming phases.
        - `dry_run=True`: parse only, no file writes, return preview structure.
    """
    del llm_enrich
    del parse_appendix_stats

    repo_root = Path(__file__).resolve().parents[2]
    schema_dir = repo_root / "schemas"

    try:
        source_file = Path(source_path)
        if not source_file.exists() or not source_file.is_file():
            return {
                "status": "error",
                "module_slug": module_slug,
                "artifacts": [],
                "validation": {"passed": False, "errors": [f"Source not found: {source_path}"]},
                "quarantine_reason": "source_not_found",
            }

        with open(source_file, "r", encoding="utf-8") as f:
            raw_text = f.read()

        if not raw_text.strip():
            return {
                "status": "error",
                "module_slug": module_slug,
                "artifacts": [],
                "validation": {"passed": False, "errors": ["Source file is empty"]},
                "quarantine_reason": "empty_source",
            }

        source_title = _extract_metadata_title(raw_text) or source_file.stem
        effective_slug = _sanitize_module_slug(module_slug or source_title)

        semantic_text = _strip_presentation_blocks(raw_text)

        source_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]
        info(
            f"MODULE_INGEST: Import start source={source_file.name} slug={effective_slug} hash={source_hash}",
            category="module_ingest",
        )

        if use_deterministic:
            # Deterministic path: parse rooms and emit NEQ artifacts with sequential IDs
            rooms = _parse_room_blocks(semantic_text)
            if not rooms:
                return {
                    "status": "error",
                    "module_slug": effective_slug,
                    "artifacts": [],
                    "validation": {"passed": False, "errors": ["No rooms found in source"]},
                    "quarantine_reason": "no_rooms_found",
                }

            intermediate = _build_intermediate_adventure(source_title, str(source_file), rooms)
            intermediate["module_seed"]["module_name"] = effective_slug

            module_path = Path(output_root) / effective_slug

            if dry_run:
                # Preview mode: generate IDs and artifact paths without writing
                area_id, location_ids = _generate_neq_ids(effective_slug, rooms)
                preview_artifacts = [
                    str(module_path / "module_context.json"),
                    str(module_path / "module_plot.json"),
                    str(module_path / f"areas/{area_id}.json"),
                    str(module_path / f"map_{area_id}.json"),
                ]
                info(
                    f"MODULE_INGEST: Dry-run preview slug={effective_slug} rooms={len(rooms)} area={area_id}",
                    category="module_ingest",
                )
                return {
                    "status": "dry_run",
                    "module_slug": effective_slug,
                    "artifacts": preview_artifacts,
                    "validation": {"passed": True, "errors": [], "dry_run": True},
                    "quarantine_reason": None,
                    "preview": {
                        "room_count": len(rooms),
                        "area_id": area_id,
                        "location_ids": location_ids[:5] if len(location_ids) > 5 else location_ids,
                    },
                }

            artifacts = _emit_neq_artifacts(module_path, effective_slug, intermediate)

            if not artifacts:
                return {
                    "status": "error",
                    "module_slug": effective_slug,
                    "artifacts": [],
                    "validation": {"passed": False, "errors": ["Artifact emission failed"]},
                    "quarantine_reason": "emission_failed",
                }

            generated_module_name = effective_slug

        else:
            # AI-driven path via module builder
            if not AI_MODULE_BUILDER_AVAILABLE:
                return {
                    "status": "error",
                    "module_slug": effective_slug,
                    "artifacts": [],
                    "validation": {"passed": False, "errors": ["AI module builder not available (missing dependencies)"]},
                    "quarantine_reason": "ai_builder_unavailable",
                }

            narrative = _build_import_narrative(source_title, str(source_file), semantic_text)
            params: Dict[str, Any] = {
                "module_name": effective_slug,
                "narrative": narrative,
                "concept": narrative,
            }

            success, generated_module_name = ai_driven_module_creation(params)
            if not success or not generated_module_name:
                return {
                    "status": "error",
                    "module_slug": effective_slug,
                    "artifacts": [],
                    "validation": {"passed": False, "errors": ["Module generation failed"]},
                    "quarantine_reason": "generation_failed",
                }

            module_path = Path(output_root) / generated_module_name
            artifacts = _collect_artifacts(module_path=module_path, repo_root=repo_root)

        validation = _validate_module_artifacts(module_path=module_path, schema_dir=schema_dir)

        # Re-collect artifacts after validation (in case validation created temp files)
        artifacts = _collect_artifacts(module_path=module_path, repo_root=repo_root)

        if strict and not validation["passed"]:
            warning(
                f"MODULE_INGEST: Validation failed slug={generated_module_name} failed={validation['failed_count']}",
                category="module_ingest",
            )
            return {
                "status": "quarantined",
                "module_slug": generated_module_name,
                "artifacts": artifacts,
                "validation": {
                    "passed": False,
                    "errors": validation["errors"],
                    "failed_count": validation["failed_count"],
                    "success_rate": validation["success_rate"],
                },
                "quarantine_reason": "schema_validation_failed",
                "registration": {
                    "registration_attempted": False,
                    "registration_success": False,
                    "registry_module_present": False,
                    "registration_errors": ["Registration skipped due to validation failure"],
                },
            }

        # Attempt registry integration after strict validation passes
        registration_result = _register_module_if_valid(
            module_slug=generated_module_name,
            validation_passed=validation["passed"],
            strict=strict,
        )

        # Fail-closed: success requires both validation pass AND registry presence
        if strict and not registration_result["registry_module_present"]:
            warning(
                f"MODULE_INGEST: Registration failed slug={generated_module_name}",
                category="module_ingest",
            )
            return {
                "status": "quarantined",
                "module_slug": generated_module_name,
                "artifacts": artifacts,
                "validation": {
                    "passed": validation["passed"],
                    "errors": validation["errors"],
                    "failed_count": validation["failed_count"],
                    "success_rate": validation["success_rate"],
                },
                "quarantine_reason": "registry_integration_failed",
                "registration": registration_result,
            }

        info(
            f"MODULE_INGEST: Import complete slug={generated_module_name} passed={validation['passed']} registered={registration_result['registry_module_present']}",
            category="module_ingest",
        )
        return {
            "status": "success",
            "module_slug": generated_module_name,
            "artifacts": artifacts,
            "validation": {
                "passed": validation["passed"],
                "errors": validation["errors"],
                "failed_count": validation["failed_count"],
                "success_rate": validation["success_rate"],
            },
            "quarantine_reason": None,
            "registration": registration_result,
        }

    except Exception as e:
        error(
            f"MODULE_INGEST: Unexpected import exception for source={source_path}",
            exception=e,
            category="module_ingest",
        )
        return {
            "status": "error",
            "module_slug": module_slug,
            "artifacts": [],
            "validation": {"passed": False, "errors": [str(e)]},
            "quarantine_reason": "unexpected_exception",
        }
