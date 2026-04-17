# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest module monster authority helpers.

Derives an authored module monster roster for runtime encounter authorization and
provides a reuse-first hydration path for missing canonical monster files.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set

from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import info, warning


GENERIC_MONSTER_MODIFIER_TOKENS = {
    "leader",
    "captain",
    "sergeant",
    "chief",
    "elite",
    "veteran",
    "greater",
    "lesser",
    "hooded",
    "cloaked",
    "robed",
    "red",
    "black",
    "white",
    "dark",
}


def normalize_monster_identity(monster_name: Any) -> str:
    """Normalize monster names with the same slug rules as combat lookup."""
    from updates.update_character_info import normalize_character_name

    return normalize_character_name(str(monster_name or ""))


def _load_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _split_creature_tokens(raw_value: str) -> List[str]:
    if not isinstance(raw_value, str):
        return []

    normalized = raw_value.replace("\n", ",").replace(";", ",")
    tokens: List[str] = []
    for piece in normalized.split(","):
        cleaned = str(piece or "").strip().strip(". ")
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _iter_authored_creature_names(payload: Any) -> List[str]:
    creature_names: List[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"monsters", "creatures"}:
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            token = item.strip().strip(". ")
                            if token:
                                creature_names.append(token)
                        elif isinstance(item, dict):
                            name_value = (
                                str(item.get("name") or item.get("monster") or "")
                                .strip()
                                .strip(". ")
                            )
                            if name_value:
                                creature_names.append(name_value)
                elif isinstance(value, str):
                    creature_names.extend(_split_creature_tokens(value))
            else:
                creature_names.extend(_iter_authored_creature_names(value))
    elif isinstance(payload, list):
        for item in payload:
            creature_names.extend(_iter_authored_creature_names(item))
    return creature_names


def _load_known_npc_names(module_name: str) -> Set[str]:
    npc_names: Set[str] = set()
    path_manager = ModulePathManager(module_name)

    def _extract_npc_names(container: Any) -> None:
        if isinstance(container, list):
            for npc in container:
                if not isinstance(npc, dict):
                    continue
                npc_name = normalize_monster_identity(npc.get("name", ""))
                if npc_name:
                    npc_names.add(npc_name)
            return

        if isinstance(container, dict):
            for value in container.values():
                if not isinstance(value, dict):
                    continue
                npc_name = normalize_monster_identity(value.get("name", ""))
                if npc_name:
                    npc_names.add(npc_name)

    seed_path = os.path.join(path_manager.module_dir, "npcs_seed.json")
    seed_data = _load_json_file(seed_path)
    if isinstance(seed_data, dict):
        _extract_npc_names(seed_data.get("npcs", []))

    context_path = os.path.join(path_manager.module_dir, "module_context.json")
    context_data = _load_json_file(context_path)
    if isinstance(context_data, dict):
        _extract_npc_names(context_data.get("npcs", []))

    try:
        party_tracker = _load_json_file("party_tracker.json") or {}
        for party_member in party_tracker.get("partyMembers", []):
            npc_name = normalize_monster_identity(party_member)
            if npc_name:
                npc_names.add(npc_name)
        for party_npc in party_tracker.get("partyNPCs", []):
            if isinstance(party_npc, dict):
                npc_name = normalize_monster_identity(party_npc.get("name", ""))
            else:
                npc_name = normalize_monster_identity(party_npc)
            if npc_name:
                npc_names.add(npc_name)
    except Exception:
        pass

    return npc_names


def build_module_monster_authority(module_name: str) -> Dict[str, Dict[str, Any]]:
    """Build module-authoritative monster roster from authored module content.

    Authoritative sources in this implementation:
    - existing module monster JSON filenames
    - authored `monsters` fields in module area JSON
    - authored `creatures` fields in module area JSON, excluding known NPC names
    """
    module_slug = str(module_name or "").replace(" ", "_")
    if not module_slug:
        return {}

    path_manager = ModulePathManager(module_slug)
    authority: Dict[str, Dict[str, Any]] = {}
    known_npc_names = _load_known_npc_names(module_slug)

    for seed_name in _extract_seed_monster_names(module_slug):
        slug = normalize_monster_identity(seed_name)
        if not slug or slug in known_npc_names:
            continue
        authority.setdefault(slug, {"sources": []})["sources"].append(
            {"type": "seed_artifact", "name": seed_name}
        )

    monsters_dir = os.path.join(path_manager.module_dir, "monsters")
    if os.path.isdir(monsters_dir):
        for file_name in os.listdir(monsters_dir):
            if not file_name.endswith(".json"):
                continue
            slug = normalize_monster_identity(file_name[:-5])
            if not slug:
                continue
            authority.setdefault(slug, {"sources": []})["sources"].append(
                {
                    "type": "existing_monster_file",
                    "path": os.path.join(monsters_dir, file_name),
                }
            )

    for area_id in path_manager.get_area_ids():
        area_path = path_manager.get_area_path(area_id)
        area_payload = _load_json_file(area_path)
        if not isinstance(area_payload, dict):
            continue

        for creature_name in _iter_authored_creature_names(area_payload):
            slug = normalize_monster_identity(creature_name)
            if not slug or slug in known_npc_names:
                continue
            authority.setdefault(slug, {"sources": []})["sources"].append(
                {
                    "type": "authored_area_content",
                    "path": area_path,
                    "name": creature_name,
                }
            )

    return authority


def authorize_module_monster(module_name: str, monster_name: str) -> Dict[str, Any]:
    """Return authorization metadata for a requested encounter monster."""
    resolved = resolve_authorized_monster_reference(module_name, monster_name)
    return {
        "module_name": str(module_name or "").replace(" ", "_"),
        "monster_name": str(monster_name or ""),
        "slug": resolved.get("requested_slug", ""),
        "authorized": bool(resolved.get("authorized")),
        "sources": resolved.get("sources", []),
        "canonical_slug": resolved.get("canonical_slug", ""),
        "canonical_name": resolved.get("canonical_name", ""),
        "resolution_mode": resolved.get("resolution_mode", "unauthorized"),
        "reason": resolved.get("reason", ""),
    }


def _tokenize_monster_slug(slug: str) -> List[str]:
    return [token for token in re.split(r"_+", str(slug or "")) if token]


def _signal_tokens(tokens: List[str]) -> Set[str]:
    return {token for token in tokens if token not in GENERIC_MONSTER_MODIFIER_TOKENS}


def _canonical_name_from_slug(slug: str, sources: List[Dict[str, Any]]) -> str:
    for source in sources:
        source_name = str(source.get("name") or "").strip()
        if source_name:
            return source_name
    return str(slug or "").replace("_", " ").strip().title()


def resolve_authorized_monster_reference(
    module_name: str, monster_name: str
) -> Dict[str, Any]:
    """Resolve monster reference to canonical authored identity when deterministic."""
    module_slug = str(module_name or "").replace(" ", "_")
    requested_name = str(monster_name or "").strip()
    requested_slug = normalize_monster_identity(requested_name)
    authority = build_module_monster_authority(module_slug)

    exact_sources = authority.get(requested_slug, {}).get("sources", [])
    if exact_sources:
        return {
            "module_name": module_slug,
            "requested_name": requested_name,
            "requested_slug": requested_slug,
            "canonical_name": _canonical_name_from_slug(requested_slug, exact_sources),
            "canonical_slug": requested_slug,
            "authorized": True,
            "resolution_mode": "exact",
            "reason": "exact_authorized_match",
            "sources": exact_sources,
            "candidates": [requested_slug],
        }

    requested_tokens = _tokenize_monster_slug(requested_slug)
    requested_signal_tokens = _signal_tokens(requested_tokens)

    subset_candidates: List[str] = []
    for candidate_slug in authority.keys():
        candidate_tokens = _tokenize_monster_slug(candidate_slug)
        candidate_signal_tokens = _signal_tokens(candidate_tokens)

        # Require at least one non-modifier signal token to avoid
        # degenerate matches like "red".
        if not candidate_signal_tokens:
            continue

        if candidate_signal_tokens.issubset(requested_signal_tokens):
            subset_candidates.append(candidate_slug)

    subset_candidates = sorted(set(subset_candidates))

    if len(subset_candidates) == 1:
        canonical_slug = subset_candidates[0]
        sources = authority.get(canonical_slug, {}).get("sources", [])
        return {
            "module_name": module_slug,
            "requested_name": requested_name,
            "requested_slug": requested_slug,
            "canonical_name": _canonical_name_from_slug(canonical_slug, sources),
            "canonical_slug": canonical_slug,
            "authorized": True,
            "resolution_mode": "subset_unique",
            "reason": "unique_subset_canonical_match",
            "sources": sources,
            "candidates": subset_candidates,
        }

    if len(subset_candidates) > 1:
        return {
            "module_name": module_slug,
            "requested_name": requested_name,
            "requested_slug": requested_slug,
            "canonical_name": "",
            "canonical_slug": "",
            "authorized": False,
            "resolution_mode": "ambiguous",
            "reason": "ambiguous_candidates",
            "sources": [],
            "candidates": subset_candidates,
        }

    return {
        "module_name": module_slug,
        "requested_name": requested_name,
        "requested_slug": requested_slug,
        "canonical_name": "",
        "canonical_slug": "",
        "authorized": False,
        "resolution_mode": "unauthorized",
        "reason": "no_canonical_match",
        "sources": [],
        "candidates": [],
    }


def find_reusable_monster_path(module_name: str, monster_name: str) -> Optional[str]:
    """Find a reusable existing monster JSON with the same normalized slug."""
    slug = normalize_monster_identity(monster_name)
    current_module = str(module_name or "").replace(" ", "_")
    modules_root = "modules"
    if not os.path.isdir(modules_root):
        return None

    for module_dir_name in sorted(os.listdir(modules_root)):
        if module_dir_name == current_module:
            continue
        candidate_path = os.path.join(
            modules_root, module_dir_name, "monsters", f"{slug}.json"
        )
        if os.path.exists(candidate_path):
            return candidate_path
    return None


def load_monster_compendium_lookup(
    compendium_path: str = "data/bestiary/monster_compendium.json",
) -> Dict[str, Dict[str, Any]]:
    """Load global monster compendium into normalized slug lookup."""
    payload = _load_json_file(compendium_path)
    if not isinstance(payload, dict):
        return {}

    monsters_blob = payload.get("monsters")
    lookup: Dict[str, Dict[str, Any]] = {}

    if isinstance(monsters_blob, dict):
        for _, monster_data in monsters_blob.items():
            if not isinstance(monster_data, dict):
                continue
            monster_name = str(monster_data.get("name") or "").strip()
            slug = normalize_monster_identity(monster_name)
            if slug:
                lookup[slug] = monster_data
    elif isinstance(monsters_blob, list):
        for monster_data in monsters_blob:
            if not isinstance(monster_data, dict):
                continue
            monster_name = str(monster_data.get("name") or "").strip()
            slug = normalize_monster_identity(monster_name)
            if slug:
                lookup[slug] = monster_data

    return lookup


def _write_json_atomic(file_path: str, payload: Dict[str, Any]) -> bool:
    """Atomically write JSON payload to a file path."""
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    if os.path.isdir(file_path):
        return False

    temp_fd = None
    temp_path = ""
    try:
        temp_fd, temp_path = tempfile.mkstemp(
            prefix="monster_", suffix=".tmp", dir=parent_dir or None
        )
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
            temp_fd = None
            json.dump(payload, temp_file, indent=2, ensure_ascii=False)
        os.replace(temp_path, file_path)
        return True
    except Exception:
        return False
    finally:
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except Exception:
                pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def _extract_seed_monster_names(module_slug: str) -> List[str]:
    """Read monsters_seed.json names for backward-compatible hydration inputs."""
    path_manager = ModulePathManager(module_slug)
    seed_path = os.path.join(path_manager.module_dir, "monsters_seed.json")
    seed_payload = _load_json_file(seed_path)
    if not isinstance(seed_payload, dict):
        return []

    names: List[str] = []
    monsters = seed_payload.get("monsters")
    if not isinstance(monsters, list):
        return names

    for entry in monsters:
        if isinstance(entry, str):
            cleaned = entry.strip()
        elif isinstance(entry, dict):
            cleaned = str(entry.get("name") or "").strip()
        else:
            cleaned = ""
        if cleaned:
            names.append(cleaned)
    return names


def discover_module_authored_monster_names(module_name: str) -> List[str]:
    """Return deterministic monster candidates from seed and authored module assets."""
    module_slug = str(module_name or "").replace(" ", "_")
    if not module_slug:
        return []

    ordered_names: List[str] = []
    seen_slugs: Set[str] = set()

    for seed_name in _extract_seed_monster_names(module_slug):
        seed_slug = normalize_monster_identity(seed_name)
        if seed_slug and seed_slug not in seen_slugs:
            seen_slugs.add(seed_slug)
            ordered_names.append(seed_name)

    authority = build_module_monster_authority(module_slug)
    for canonical_slug in sorted(authority.keys()):
        if canonical_slug in seen_slugs:
            continue
        sources = authority.get(canonical_slug, {}).get("sources", [])
        canonical_name = _canonical_name_from_slug(canonical_slug, sources)
        if canonical_name:
            seen_slugs.add(canonical_slug)
            ordered_names.append(canonical_name)

    return ordered_names


def _build_authored_generation_context(
    module_slug: str,
    canonical_slug: str,
    canonical_name: str,
    requested_name: str,
) -> Dict[str, Any]:
    """Build bounded authored context payload for controlled generation."""
    context: Dict[str, Any] = {
        "module": module_slug,
        "monster_name": canonical_name,
        "monster_slug": canonical_slug,
        "requested_name": requested_name,
    }

    module_context_path = os.path.join("modules", module_slug, "module_context.json")
    module_context_data = _load_json_file(module_context_path)
    if isinstance(module_context_data, dict):
        level_range = module_context_data.get("levelRange")
        if isinstance(level_range, dict):
            min_level = level_range.get("min")
            max_level = level_range.get("max")
            if isinstance(min_level, int) and isinstance(max_level, int):
                context["level_range"] = f"{min_level}-{max_level}"

        difficulty = (
            module_context_data.get("difficulty")
            or module_context_data.get("dangerLevel")
            or ""
        )
        if isinstance(difficulty, str) and difficulty.strip():
            context["difficulty"] = difficulty.strip()

    area_context: List[Dict[str, str]] = []
    areas_dir = os.path.join("modules", module_slug, "areas")
    if os.path.isdir(areas_dir):
        target_slug = str(canonical_slug or "").strip().lower()
        for area_name in sorted(os.listdir(areas_dir)):
            if not area_name.endswith(".json") or area_name.endswith("_BU.json"):
                continue
            area_path = os.path.join(areas_dir, area_name)
            area_data = _load_json_file(area_path)
            if not isinstance(area_data, dict):
                continue

            area_label = str(
                area_data.get("areaName") or area_data.get("name") or area_name[:-5]
            ).strip()
            locations = area_data.get("locations")
            if not isinstance(locations, list):
                continue

            for location in locations:
                if not isinstance(location, dict):
                    continue

                matched = False
                for field_name in ("monsters", "creatures"):
                    for candidate in _iter_authored_creature_names(
                        location.get(field_name)
                    ):
                        if normalize_monster_identity(candidate) == target_slug:
                            matched = True
                            break
                    if matched:
                        break

                if not matched:
                    continue

                prose = str(
                    location.get("description")
                    or location.get("readAloudDescription")
                    or location.get("read_aloud")
                    or ""
                ).strip()
                area_context.append(
                    {
                        "area_name": area_label,
                        "location_name": str(
                            location.get("name") or location.get("locationName") or ""
                        ).strip(),
                        "location_id": str(location.get("locationId") or "").strip(),
                        "location_prose": prose[:320],
                    }
                )
                if len(area_context) >= 3:
                    break

            if len(area_context) >= 3:
                break

    if area_context:
        context["area_context"] = area_context

    return context


def materialize_authorized_monster_file(
    module_name: str,
    monster_name: str,
    monster_builder_path: str,
    compendium_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    allow_generation: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Ensure an authorized monster file exists in the active module."""
    module_slug = str(module_name or "").replace(" ", "_")
    path_manager = ModulePathManager(module_slug)
    resolved_reference = resolve_authorized_monster_reference(module_slug, monster_name)
    canonical_slug = resolved_reference.get("canonical_slug") or resolved_reference.get(
        "requested_slug"
    )
    canonical_name = resolved_reference.get("canonical_name") or str(monster_name or "")
    target_path = path_manager.get_monster_path(canonical_name)
    lookup = compendium_lookup or load_monster_compendium_lookup()

    if os.path.exists(target_path):
        return {
            "ok": True,
            "source": "existing",
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get("resolution_mode", "exact"),
            "bestiary_missing": False,
        }

    if not resolved_reference.get("authorized"):
        reason = str(resolved_reference.get("reason") or "").strip()
        candidates = resolved_reference.get("candidates", [])
        error_message = f"Monster '{monster_name}' is not authorized by authored module content for '{module_slug}'."
        if reason == "ambiguous_candidates" and candidates:
            error_message += (
                f" Ambiguous canonical candidates: {', '.join(candidates)}."
            )
        elif reason == "no_canonical_match":
            error_message += " No canonical match found."

        return {
            "ok": False,
            "error_class": "unauthorized_monster_reference",
            "error_message": error_message,
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get(
                "resolution_mode", "unauthorized"
            ),
            "reason": reason,
            "candidates": candidates,
            "sources": [],
            "bestiary_missing": True,
        }

    reusable_path = find_reusable_monster_path(module_slug, canonical_name)
    if reusable_path:
        if not dry_run:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(reusable_path, target_path)
        info(
            f"TABLETOP MODE: Reused monster '{monster_name}' as canonical '{canonical_name}' from {reusable_path} -> {target_path}",
            category="combat_builder",
        )
        return {
            "ok": True,
            "source": "reuse",
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get(
                "resolution_mode", "subset_unique"
            ),
            "bestiary_missing": False,
        }

    bestiary_entry = lookup.get(str(canonical_slug or "").strip())
    if isinstance(bestiary_entry, dict):
        write_ok = True if dry_run else _write_json_atomic(target_path, bestiary_entry)
        if write_ok and (dry_run or os.path.exists(target_path)):
            info(
                f"TABLETOP MODE: Materialized bestiary monster '{monster_name}' as canonical '{canonical_name}' into {target_path}",
                category="combat_builder",
            )
            return {
                "ok": True,
                "source": "bestiary",
                "target_path": target_path,
                "slug": canonical_slug,
                "requested_name": str(monster_name or ""),
                "requested_slug": resolved_reference.get("requested_slug", ""),
                "canonical_name": canonical_name,
                "canonical_slug": canonical_slug,
                "resolution_mode": resolved_reference.get(
                    "resolution_mode", "subset_unique"
                ),
                "bestiary_missing": False,
            }

    if not allow_generation:
        return {
            "ok": False,
            "error_class": "authorized_monster_provider_unavailable",
            "error_message": (
                f"Monster '{monster_name}' is authorized but controlled generation is disabled for '{target_path}'."
            ),
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get(
                "resolution_mode", "subset_unique"
            ),
            "sources": resolved_reference.get("sources", []),
            "bestiary_missing": True,
        }

    if not monster_builder_path or not os.path.exists(monster_builder_path):
        return {
            "ok": False,
            "error_class": "authorized_monster_provider_unavailable",
            "error_message": (
                f"Monster '{monster_name}' is authorized but generation provider is unavailable for '{target_path}'."
            ),
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get(
                "resolution_mode", "subset_unique"
            ),
            "sources": resolved_reference.get("sources", []),
            "bestiary_missing": True,
        }

    if dry_run:
        return {
            "ok": True,
            "source": "generated",
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get(
                "resolution_mode", "subset_unique"
            ),
            "bestiary_missing": True,
        }

    authored_context = _build_authored_generation_context(
        module_slug=module_slug,
        canonical_slug=str(canonical_slug or ""),
        canonical_name=canonical_name,
        requested_name=str(monster_name or ""),
    )
    context_file_path = ""
    result: Optional[subprocess.CompletedProcess[str]] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="monster_context_",
            delete=False,
        ) as temp_context:
            json.dump(authored_context, temp_context, indent=2, ensure_ascii=False)
            context_file_path = temp_context.name

        result = subprocess.run(
            [
                sys.executable,
                monster_builder_path,
                canonical_name,
                "--module",
                module_slug,
                "--context-file",
                context_file_path,
            ],
            capture_output=True,
            text=True,
        )
    finally:
        if context_file_path and os.path.exists(context_file_path):
            try:
                os.remove(context_file_path)
            except OSError:
                warning(
                    f"TABLETOP MODE: Could not remove temporary monster context file {context_file_path}",
                    category="combat_builder",
                )

    if result is None:
        return {
            "ok": False,
            "error_class": "authorized_monster_hydration_failed",
            "error_message": (
                f"Monster '{monster_name}' is authorized by authored module content but hydration failed for '{target_path}'."
            ),
            "builder_error": "Generation subprocess did not execute",
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get(
                "resolution_mode", "subset_unique"
            ),
            "sources": resolved_reference.get("sources", []),
            "bestiary_missing": True,
        }

    if result.returncode == 0 and os.path.exists(target_path):
        info(
            f"TABLETOP MODE: Hydrated authorized monster '{monster_name}' as canonical '{canonical_name}' into {target_path}",
            category="combat_builder",
        )
        return {
            "ok": True,
            "source": "generated",
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get(
                "resolution_mode", "subset_unique"
            ),
            "bestiary_missing": True,
        }

    builder_error = (result.stderr or result.stdout or "").strip()
    return {
        "ok": False,
        "error_class": "authorized_monster_hydration_failed",
        "error_message": (
            f"Monster '{monster_name}' is authorized by authored module content but hydration failed for '{target_path}'."
        ),
        "builder_error": builder_error,
        "target_path": target_path,
        "slug": canonical_slug,
        "requested_name": str(monster_name or ""),
        "requested_slug": resolved_reference.get("requested_slug", ""),
        "canonical_name": canonical_name,
        "canonical_slug": canonical_slug,
        "resolution_mode": resolved_reference.get("resolution_mode", "subset_unique"),
        "sources": resolved_reference.get("sources", []),
        "bestiary_missing": True,
    }
