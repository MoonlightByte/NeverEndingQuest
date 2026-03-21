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
from typing import Any, Dict, List, Optional, Set

from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import info


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
                            name_value = str(item.get("name") or item.get("monster") or "").strip().strip(". ")
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

    monsters_dir = os.path.join(path_manager.module_dir, "monsters")
    if os.path.isdir(monsters_dir):
        for file_name in os.listdir(monsters_dir):
            if not file_name.endswith(".json"):
                continue
            slug = normalize_monster_identity(file_name[:-5])
            if not slug:
                continue
            authority.setdefault(slug, {"sources": []})["sources"].append(
                {"type": "existing_monster_file", "path": os.path.join(monsters_dir, file_name)}
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
                {"type": "authored_area_content", "path": area_path, "name": creature_name}
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


def resolve_authorized_monster_reference(module_name: str, monster_name: str) -> Dict[str, Any]:
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
        candidate_path = os.path.join(modules_root, module_dir_name, "monsters", f"{slug}.json")
        if os.path.exists(candidate_path):
            return candidate_path
    return None


def materialize_authorized_monster_file(module_name: str, monster_name: str, monster_builder_path: str) -> Dict[str, Any]:
    """Ensure an authorized monster file exists in the active module."""
    module_slug = str(module_name or "").replace(" ", "_")
    path_manager = ModulePathManager(module_slug)
    resolved_reference = resolve_authorized_monster_reference(module_slug, monster_name)
    canonical_slug = resolved_reference.get("canonical_slug") or resolved_reference.get("requested_slug")
    canonical_name = resolved_reference.get("canonical_name") or str(monster_name or "")
    target_path = path_manager.get_monster_path(canonical_name)

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
        }

    if not resolved_reference.get("authorized"):
        reason = str(resolved_reference.get("reason") or "").strip()
        candidates = resolved_reference.get("candidates", [])
        error_message = (
            f"Monster '{monster_name}' is not authorized by authored module content for '{module_slug}'."
        )
        if reason == "ambiguous_candidates" and candidates:
            error_message += f" Ambiguous canonical candidates: {', '.join(candidates)}."
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
            "resolution_mode": resolved_reference.get("resolution_mode", "unauthorized"),
            "reason": reason,
            "candidates": candidates,
            "sources": [],
        }

    reusable_path = find_reusable_monster_path(module_slug, canonical_name)
    if reusable_path:
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
            "resolution_mode": resolved_reference.get("resolution_mode", "subset_unique"),
        }

    result = subprocess.run(
        [sys.executable, monster_builder_path, canonical_name, "--module", module_slug],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and os.path.exists(target_path):
        info(
            f"TABLETOP MODE: Hydrated authorized monster '{monster_name}' as canonical '{canonical_name}' into {target_path}",
            category="combat_builder",
        )
        return {
            "ok": True,
            "source": "hydrated",
            "target_path": target_path,
            "slug": canonical_slug,
            "requested_name": str(monster_name or ""),
            "requested_slug": resolved_reference.get("requested_slug", ""),
            "canonical_name": canonical_name,
            "canonical_slug": canonical_slug,
            "resolution_mode": resolved_reference.get("resolution_mode", "subset_unique"),
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
    }
