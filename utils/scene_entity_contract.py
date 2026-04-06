# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Scene Entity Contract Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Additive helper utilities for scene-entity metadata that separates visible
location NPC presence from formal combat-valid monster authorization.
"""

import re
from typing import Any, Dict, List, Optional

from utils.encoding_utils import safe_json_dump, safe_json_load
from utils.enhanced_logger import debug, info
from utils.module_path_manager import ModulePathManager


SCENE_COMBAT_VALIDITY_SCENE_ONLY = "scene_only"
SCENE_COMBAT_VALIDITY_ESCALATABLE = "escalatable"

SCENE_MANIFESTATION_CORPOREAL = "corporeal"
SCENE_MANIFESTATION_INCORPOREAL = "incorporeal"

SCENE_POLICY_INCORPOREAL_NO_EFFECT = "incorporeal_no_effect"
SCENE_POLICY_HELPLESS_KILL_ELSE_ESCALATE = "helpless_kill_else_escalate"

_HELPLESS_HINT_TOKENS = {
    "helpless",
    "nonresisting",
    "non-resisting",
    "surrendered",
    "bound",
    "restrained",
    "unconscious",
    "incapacitated",
    "unable to resist",
}


def _normalize_identity(value: Any) -> str:
    token = str(value or "").strip().lower().replace("'", "")
    token = re.sub(r"[^a-z0-9\s_]", "", token)
    token = re.sub(r"\s+", "_", token)
    token = re.sub(r"_+", "_", token)
    return token.strip("_")


def _safe_scene_entity_metadata(npc_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    scene_entity = npc_entry.get("sceneEntity")
    if not isinstance(scene_entity, dict):
        return None

    combat_validity = str(scene_entity.get("combatValidity", "")).strip().lower()
    manifestation = str(scene_entity.get("manifestation", "")).strip().lower()
    violence_policy = str(scene_entity.get("violencePolicy", "")).strip().lower()
    combat_proxy = str(scene_entity.get("combatProxy", "")).strip()
    explicit_helpless = scene_entity.get("helpless")

    return {
        "combatValidity": combat_validity,
        "manifestation": manifestation,
        "violencePolicy": violence_policy,
        "combatProxy": combat_proxy,
        "helpless": bool(explicit_helpless) if isinstance(explicit_helpless, bool) else None,
    }


def _npc_scene_records(location_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(location_data, dict):
        return []

    records: List[Dict[str, Any]] = []
    for npc in location_data.get("npcs", []):
        if not isinstance(npc, dict):
            continue
        scene_entity = _safe_scene_entity_metadata(npc)
        if not scene_entity:
            continue

        name = str(npc.get("name", "")).strip()
        if not name:
            continue

        records.append(
            {
                "name": name,
                "name_slug": _normalize_identity(name),
                "description": str(npc.get("description", "") or "").strip(),
                "attitude": str(npc.get("attitude", "") or "").strip(),
                "sceneEntity": scene_entity,
            }
        )

    return records


def resolve_scene_entity_monster_target(
    monster_label: str,
    location_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Resolve createEncounter monster label to current-scene entity metadata."""
    target_slug = _normalize_identity(monster_label)
    if not target_slug:
        return None

    for record in _npc_scene_records(location_data):
        if record.get("name_slug") == target_slug:
            return record
    return None


def _is_helpless_scene_entity(scene_record: Dict[str, Any]) -> bool:
    scene_metadata = scene_record.get("sceneEntity", {}) if isinstance(scene_record, dict) else {}
    if isinstance(scene_metadata.get("helpless"), bool):
        return bool(scene_metadata.get("helpless"))

    attitude = str(scene_record.get("attitude", "") or "").lower()
    description = str(scene_record.get("description", "") or "").lower()
    combined = f"{attitude} {description}"
    return any(token in combined for token in _HELPLESS_HINT_TOKENS)


def evaluate_scene_entity_encounter_resolution(
    monsters: List[str],
    location_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate scene-entity handling before combat-builder encounter generation."""
    if not isinstance(monsters, list) or not monsters:
        return {"status": "no_scene_entities", "resolved_monsters": monsters}

    resolved_monsters: List[str] = []
    helpless_resolutions: List[Dict[str, Any]] = []

    for monster_label in monsters:
        scene_record = resolve_scene_entity_monster_target(str(monster_label or ""), location_data)
        if not scene_record:
            resolved_monsters.append(monster_label)
            continue

        scene_metadata = scene_record.get("sceneEntity", {})
        combat_validity = scene_metadata.get("combatValidity", "")
        manifestation = scene_metadata.get("manifestation", "")
        violence_policy = scene_metadata.get("violencePolicy", "")
        combat_proxy = str(scene_metadata.get("combatProxy", "") or "").strip()
        scene_name = scene_record.get("name", str(monster_label or ""))

        if combat_validity == SCENE_COMBAT_VALIDITY_SCENE_ONLY:
            return {
                "status": "error",
                "error_type": "non_combat_valid_scene_entity",
                "error_message": (
                    f"non_combat_valid_scene_entity: '{scene_name}' is authored as scene-only content "
                    f"(manifestation={manifestation or 'unknown'}, policy={violence_policy or 'unknown'}) and cannot "
                    "be used in createEncounter.monsters[]."
                ),
                "scene_entity": scene_record,
            }

        if combat_validity != SCENE_COMBAT_VALIDITY_ESCALATABLE:
            resolved_monsters.append(monster_label)
            continue

        if violence_policy != SCENE_POLICY_HELPLESS_KILL_ELSE_ESCALATE:
            if combat_proxy:
                resolved_monsters.append(combat_proxy)
                continue
            return {
                "status": "error",
                "error_type": "scene_entity_missing_combat_proxy",
                "error_message": (
                    f"scene_entity_missing_combat_proxy: '{scene_name}' is escalatable scene content "
                    f"(policy={violence_policy or 'unspecified'}) but no combatProxy is authored."
                ),
                "scene_entity": scene_record,
            }

        if _is_helpless_scene_entity(scene_record):
            helpless_resolutions.append(scene_record)
            continue

        if not combat_proxy:
            return {
                "status": "error",
                "error_type": "scene_entity_missing_combat_proxy",
                "error_message": (
                    f"scene_entity_missing_combat_proxy: '{scene_name}' requires escalation under "
                    "helpless_kill_else_escalate but no combatProxy is authored."
                ),
                "scene_entity": scene_record,
            }

        resolved_monsters.append(combat_proxy)

    if helpless_resolutions and not resolved_monsters:
        return {
            "status": "resolved_without_combat",
            "resolved_monsters": [],
            "helpless_resolutions": helpless_resolutions,
        }

    return {
        "status": "ok",
        "resolved_monsters": resolved_monsters,
        "helpless_resolutions": helpless_resolutions,
    }


def apply_helpless_scene_entity_resolution(
    scene_record: Dict[str, Any],
    party_tracker_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist deterministic scene-state mutation for helpless scene entity harm."""
    scene_name = str(scene_record.get("name", "") or "").strip()
    if not scene_name:
        return {"ok": False, "reason": "missing_scene_entity_name"}

    module_name = str(party_tracker_data.get("module", "") or "").replace(" ", "_")
    current_area_id = str(
        party_tracker_data.get("worldConditions", {}).get("currentAreaId", "") or ""
    ).strip()
    current_location_id = str(
        party_tracker_data.get("worldConditions", {}).get("currentLocationId", "") or ""
    ).strip()

    if not module_name or not current_area_id or not current_location_id:
        return {
            "ok": False,
            "reason": "missing_runtime_context",
            "scene_name": scene_name,
        }

    path_manager = ModulePathManager(module_name)
    area_path = path_manager.get_area_path(current_area_id)
    area_data = safe_json_load(area_path)
    if not isinstance(area_data, dict):
        return {
            "ok": False,
            "reason": "area_load_failed",
            "scene_name": scene_name,
            "area_path": area_path,
        }

    removed = False
    scene_slug = _normalize_identity(scene_name)
    for location in area_data.get("locations", []):
        if not isinstance(location, dict):
            continue
        if str(location.get("locationId", "") or "").strip() != current_location_id:
            continue

        npc_entries = location.get("npcs", [])
        if not isinstance(npc_entries, list):
            npc_entries = []
            location["npcs"] = npc_entries

        kept_entries = []
        for npc in npc_entries:
            if not isinstance(npc, dict):
                kept_entries.append(npc)
                continue
            npc_name = str(npc.get("name", "") or "").strip()
            if _normalize_identity(npc_name) == scene_slug:
                removed = True
                continue
            kept_entries.append(npc)

        location["npcs"] = kept_entries
        break

    if not removed:
        return {
            "ok": False,
            "reason": "scene_entity_not_found_in_location",
            "scene_name": scene_name,
            "location_id": current_location_id,
        }

    if not safe_json_dump(area_data, area_path):
        return {
            "ok": False,
            "reason": "area_save_failed",
            "scene_name": scene_name,
            "area_path": area_path,
        }

    world_conditions = party_tracker_data.setdefault("worldConditions", {})
    resolved_state = world_conditions.setdefault("resolvedSceneEntities", {})
    location_resolved = resolved_state.setdefault(current_location_id, [])
    if scene_name not in location_resolved:
        location_resolved.append(scene_name)
    safe_json_dump(party_tracker_data, "party_tracker.json")

    info(
        f"SCENE_ENTITY: Deterministic helpless resolution persisted for '{scene_name}' in {current_location_id}",
        category="npc_management",
    )
    debug(
        f"STATE_CHANGE: Scene entity '{scene_name}' removed from active location {current_location_id}",
        category="npc_management",
    )
    return {"ok": True, "scene_name": scene_name, "location_id": current_location_id}
