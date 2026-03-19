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
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set

from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error


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

    seed_path = os.path.join(path_manager.module_dir, "npcs_seed.json")
    seed_data = _load_json_file(seed_path)
    if isinstance(seed_data, dict):
        for npc in seed_data.get("npcs", []):
            if not isinstance(npc, dict):
                continue
            npc_name = normalize_monster_identity(npc.get("name", ""))
            if npc_name:
                npc_names.add(npc_name)

    context_path = os.path.join(path_manager.module_dir, "module_context.json")
    context_data = _load_json_file(context_path)
    if isinstance(context_data, dict):
        for npc in context_data.get("npcs", []):
            if not isinstance(npc, dict):
                continue
            npc_name = normalize_monster_identity(npc.get("name", ""))
            if npc_name:
                npc_names.add(npc_name)

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
    slug = normalize_monster_identity(monster_name)
    authority = build_module_monster_authority(module_name)
    sources = authority.get(slug, {}).get("sources", [])
    return {
        "module_name": str(module_name or "").replace(" ", "_"),
        "monster_name": str(monster_name or ""),
        "slug": slug,
        "authorized": bool(sources),
        "sources": sources,
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
    target_path = path_manager.get_monster_path(monster_name)

    if os.path.exists(target_path):
        return {
            "ok": True,
            "source": "existing",
            "target_path": target_path,
            "slug": normalize_monster_identity(monster_name),
        }

    authorization = authorize_module_monster(module_slug, monster_name)
    if not authorization["authorized"]:
        return {
            "ok": False,
            "error_class": "unauthorized_monster_reference",
            "error_message": (
                f"Monster '{monster_name}' is not authorized by authored module content for '{module_slug}'."
            ),
            "target_path": target_path,
            "slug": authorization["slug"],
            "sources": [],
        }

    reusable_path = find_reusable_monster_path(module_slug, monster_name)
    if reusable_path:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(reusable_path, target_path)
        info(
            f"TABLETOP MODE: Reused monster '{monster_name}' from {reusable_path} -> {target_path}",
            category="combat_builder",
        )
        return {
            "ok": True,
            "source": "reuse",
            "target_path": target_path,
            "slug": authorization["slug"],
        }

    result = subprocess.run(
        [sys.executable, monster_builder_path, monster_name, "--module", module_slug],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and os.path.exists(target_path):
        info(
            f"TABLETOP MODE: Hydrated authorized monster '{monster_name}' into {target_path}",
            category="combat_builder",
        )
        return {
            "ok": True,
            "source": "hydrated",
            "target_path": target_path,
            "slug": authorization["slug"],
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
        "slug": authorization["slug"],
        "sources": authorization["sources"],
    }
