# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Character Creation Audit - Shared validation pipeline
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Provides a unified normalize -> schema validate -> completeness audit pipeline
for all player-character creation workflows.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft7Validator

from model_config import DM_MINI_MODEL
from utils.ai_client_factory import create_chat_client, get_model_config
from utils.enhanced_logger import info, warning


AUDIT_RESULT_SCHEMA_ERROR = "schema_error"
AUDIT_RESULT_COMPLETENESS_ERROR = "completeness_error"
AUDIT_RESULT_SUCCESS = "success"

SCHEMA_PATH = Path("schemas/char_schema.json")

_COMPLETENESS_PATHS = [
    "name",
    "race",
    "class",
    "background",
    "personality_traits",
    "ideals",
    "bonds",
    "flaws",
    "backgroundFeature.name",
    "backgroundFeature.description",
]

READINESS_REPAIR_WRITABLE_FIELDS = [
    "personality_traits",
    "ideals",
    "bonds",
    "flaws",
    "backgroundFeature.description",
]

_READINESS_REPAIR_FALLBACK_TEXT = {
    "personality_traits": "I stay alert in danger and keep my focus on protecting the party.",
    "ideals": "I believe courage and steady judgment can turn the tide of any trial.",
    "bonds": "I owe my companions loyalty; their safety is my first duty.",
    "flaws": "I can be stubborn under pressure and slow to ask for help.",
    "backgroundFeature.description": (
        "Your background grants trusted social footing among people who share your prior trade and culture."
    ),
}

READINESS_REPAIR_MECHANICAL_PATHS = [
    "hitPoints",
    "maxHitPoints",
    "armorClass",
    "initiative",
    "speed",
    "level",
    "abilities",
    "savingThrows",
    "skills",
    "proficiencyBonus",
    "attacksAndSpellcasting",
    "equipment",
    "currency",
    "spellcasting",
]


def _canonical_character_defaults() -> Dict[str, Any]:
    """Return deterministic schema-compatible defaults."""
    return {
        "character_role": "player",
        "character_type": "player",
        "name": "Unknown Character",
        "type": "player",
        "size": "Medium",
        "level": 1,
        "race": "Human",
        "class": "Fighter",
        "alignment": "neutral",
        "background": "Adventurer",
        "status": "alive",
        "condition": "none",
        "condition_affected": [],
        "hitPoints": 10,
        "maxHitPoints": 10,
        "armorClass": 10,
        "initiative": 0,
        "speed": 30,
        "abilities": {
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        },
        "savingThrows": [],
        "skills": [],
        "proficiencyBonus": 2,
        "senses": {"darkvision": 0, "passivePerception": 10},
        "languages": ["Common"],
        "proficiencies": {"armor": [], "weapons": [], "tools": []},
        "damageVulnerabilities": [],
        "damageResistances": [],
        "damageImmunities": [],
        "conditionImmunities": [],
        "classFeatures": [],
        "racialTraits": [],
        "backgroundFeature": {
            "name": "Background Feature",
            "description": "A defining feature from your background.",
            "source": "SRD 5.2.1",
        },
        "temporaryEffects": [],
        "injuries": [],
        "equipment_effects": [],
        "feats": [],
        "equipment": [],
        "ammunition": [],
        "attacksAndSpellcasting": [],
        "spellcasting": {
            "ability": "none",
            "spellSaveDC": 8,
            "spellAttackBonus": 0,
            "spells": {
                "cantrips": [],
                "level1": [],
                "level2": [],
                "level3": [],
                "level4": [],
                "level5": [],
                "level6": [],
                "level7": [],
                "level8": [],
                "level9": [],
            },
            "spellSlots": {
                "level1": {"current": 0, "max": 0},
                "level2": {"current": 0, "max": 0},
                "level3": {"current": 0, "max": 0},
                "level4": {"current": 0, "max": 0},
                "level5": {"current": 0, "max": 0},
                "level6": {"current": 0, "max": 0},
                "level7": {"current": 0, "max": 0},
                "level8": {"current": 0, "max": 0},
                "level9": {"current": 0, "max": 0},
            },
            "preparedSpells": [],
        },
        "currency": {"gold": 0, "silver": 0, "copper": 0},
        "experience_points": 0,
        "exp_required_for_next_level": 300,
        "personality_traits": "",
        "ideals": "",
        "bonds": "",
        "flaws": "",
    }


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _path_to_string(path_parts: Tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in path_parts)


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _set_nested_value(target: Dict[str, Any], path: str, value: Any) -> None:
    current = target
    path_parts = path.split(".")
    for key in path_parts[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path_parts[-1]] = value


def _extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    text = str(raw_text or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        parsed = json.loads(text[start:end + 1])
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize common legacy field shapes into canonical schema shape."""
    merged = _deep_merge(_canonical_character_defaults(), payload)

    if isinstance(payload.get("abilityScores"), dict) and not isinstance(payload.get("abilities"), dict):
        merged["abilities"] = payload["abilityScores"]

    hit_points_value = payload.get("hitPoints")
    if isinstance(hit_points_value, dict):
        merged["hitPoints"] = int(hit_points_value.get("current", merged["hitPoints"]))
        merged["maxHitPoints"] = int(hit_points_value.get("maximum", merged["maxHitPoints"]))

    for int_field in [
        "level",
        "hitPoints",
        "maxHitPoints",
        "armorClass",
        "initiative",
        "speed",
        "proficiencyBonus",
        "experience_points",
        "exp_required_for_next_level",
    ]:
        try:
            merged[int_field] = int(merged.get(int_field, 0))
        except (TypeError, ValueError):
            pass

    for ability_name in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
        ability_value = merged.get("abilities", {}).get(ability_name)
        try:
            merged["abilities"][ability_name] = int(ability_value)
        except (TypeError, ValueError):
            merged["abilities"][ability_name] = 10

    alignment = str(merged.get("alignment", "neutral")).strip().lower()
    if alignment not in {
        "lawful good",
        "neutral good",
        "chaotic good",
        "lawful neutral",
        "neutral",
        "chaotic neutral",
        "lawful evil",
        "neutral evil",
        "chaotic evil",
    }:
        merged["alignment"] = "neutral"
    else:
        merged["alignment"] = alignment

    return merged


def _load_validator() -> Draft7Validator:
    from utils.encoding_utils import safe_json_load

    schema_data = safe_json_load(str(SCHEMA_PATH))
    if not schema_data:
        raise ValueError(f"Schema file missing or unreadable: {SCHEMA_PATH}")
    return Draft7Validator(schema_data)


@dataclass
class CharacterCreationAuditResult:
    """Deterministic structured result from the creation audit pipeline."""

    result_type: str
    normalized_data: Dict[str, Any]
    source: str
    errors: List[Dict[str, str]] = field(default_factory=list)
    missing_paths: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    enriched_fields: List[str] = field(default_factory=list)


def _apply_optional_enrichment(normalized_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Apply a bounded narrative enrichment pass without touching mechanics."""
    enriched = deepcopy(normalized_data)
    enriched_fields: List[str] = []

    background_feature = enriched.get("backgroundFeature", {})
    description = str(background_feature.get("description", "")).strip()
    if description.lower() in {
        "",
        "background feature",
        "standard background feature",
        "a defining feature from your background.",
    }:
        background_feature["description"] = (
            "Your background grants trusted social footing among people who share your prior trade and culture."
        )
        enriched["backgroundFeature"] = background_feature
        enriched_fields.append("backgroundFeature.description")

    return enriched, enriched_fields


def sanitize_readiness_repair_patch(patch_payload: Dict[str, Any]) -> Dict[str, str]:
    """Return strictly-whitelisted narrative field updates only."""
    sanitized: Dict[str, str] = {}
    candidate_updates = patch_payload.get("updates") if isinstance(patch_payload, dict) else {}
    if not isinstance(candidate_updates, dict):
        return sanitized

    for path in READINESS_REPAIR_WRITABLE_FIELDS:
        raw_value = candidate_updates.get(path)
        if raw_value is None:
            continue
        normalized = str(raw_value).strip()
        if not normalized:
            continue
        sanitized[path] = normalized
    return sanitized


def get_mechanical_snapshot(character_data: Dict[str, Any]) -> Dict[str, Any]:
    """Capture mechanical fields used for drift regression checks."""
    snapshot: Dict[str, Any] = {}
    for path in READINESS_REPAIR_MECHANICAL_PATHS:
        snapshot[path] = deepcopy(_get_nested_value(character_data, path))
    return snapshot


def diff_mechanical_snapshot(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    """Return changed mechanical paths between two snapshots."""
    changed_paths: List[str] = []
    for path in READINESS_REPAIR_MECHANICAL_PATHS:
        if before.get(path) != after.get(path):
            changed_paths.append(path)
    return changed_paths


def apply_readiness_repair_patch(character_data: Dict[str, Any], updates: Dict[str, str]) -> Dict[str, Any]:
    """Apply safe narrative updates to a character payload copy."""
    patched = deepcopy(character_data)
    for path, value in updates.items():
        if path not in READINESS_REPAIR_WRITABLE_FIELDS:
            continue
        _set_nested_value(patched, path, value)
    return patched


def _build_readiness_repair_fallback(missing_paths: List[str]) -> Dict[str, Any]:
    updates: Dict[str, str] = {}
    for path in missing_paths:
        if path in _READINESS_REPAIR_FALLBACK_TEXT:
            updates[path] = _READINESS_REPAIR_FALLBACK_TEXT[path]
    return {
        "source": "fallback",
        "updates": updates,
    }


def build_readiness_repair_proposal(character_data: Dict[str, Any], missing_paths: List[str]) -> Dict[str, Any]:
    """Build proposal via LLM first, deterministic fallback on any failure."""
    missing_whitelisted = [path for path in missing_paths if path in READINESS_REPAIR_WRITABLE_FIELDS]
    if not missing_whitelisted:
        return {"source": "none", "updates": {}}

    fallback = _build_readiness_repair_fallback(missing_whitelisted)

    try:
        model_config = get_model_config("dm_mini", DM_MINI_MODEL)
        client = create_chat_client()

        char_name = character_data.get("name", "Unknown Character")
        char_class = character_data.get("class", "Adventurer")
        char_race = character_data.get("race", "Unknown")
        char_background = character_data.get("background", "Adventurer")
        prompt = {
            "name": char_name,
            "class": char_class,
            "race": char_race,
            "background": char_background,
            "missing_fields": missing_whitelisted,
            "instructions": [
                "Return valid JSON only.",
                "Use key 'updates' mapping path -> concise narrative text.",
                "Only include requested fields.",
                "Do not include mechanics or numbers.",
            ],
        }

        response = client.chat.completions.create(
            model=model_config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "You generate short narrative-only character text fields for tabletop roleplay sheets.",
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt, indent=2),
                },
            ],
            temperature=0.4,
            **model_config.get("extra_body", {}),
        )
        content = response.choices[0].message.content if response and response.choices else ""
        parsed = _extract_json_object(str(content or ""))
        if not parsed:
            return fallback

        sanitized = sanitize_readiness_repair_patch(parsed)
        if not sanitized:
            return fallback
        return {
            "source": "llm",
            "updates": sanitized,
        }
    except Exception as repair_error:
        warning(
            f"[AUDIT_REPAIR] LLM proposal unavailable: {repair_error}",
            category="character_creation",
        )
        return fallback


def audit_character_creation(
    payload: Dict[str, Any],
    source: str,
    enable_enrichment: bool = False,
) -> CharacterCreationAuditResult:
    """Run normalize -> schema validation -> completeness validation -> optional enrichment."""
    normalized_data = _normalize_payload(payload)

    validator = _load_validator()
    schema_errors: List[Dict[str, str]] = []
    for validation_error in sorted(validator.iter_errors(normalized_data), key=lambda err: list(err.path)):
        path = _path_to_string(tuple(validation_error.path)) or "$"
        schema_errors.append({"path": path, "message": validation_error.message})

    if schema_errors:
        warning(
            f"[AUDIT] schema_error source={source} errors={len(schema_errors)}",
            category="character_creation",
        )
        return CharacterCreationAuditResult(
            result_type=AUDIT_RESULT_SCHEMA_ERROR,
            normalized_data=normalized_data,
            source=source,
            errors=schema_errors,
            missing_paths=[entry["path"] for entry in schema_errors],
        )

    completeness_missing = [path for path in _COMPLETENESS_PATHS if _is_blank(_get_nested_value(normalized_data, path))]
    if completeness_missing:
        warning(
            f"[AUDIT] completeness_error source={source} missing={len(completeness_missing)}",
            category="character_creation",
        )
        return CharacterCreationAuditResult(
            result_type=AUDIT_RESULT_COMPLETENESS_ERROR,
            normalized_data=normalized_data,
            source=source,
            errors=[{"path": path, "message": "Field cannot be empty"} for path in completeness_missing],
            missing_paths=completeness_missing,
        )

    enriched_fields: List[str] = []
    if enable_enrichment:
        normalized_data, enriched_fields = _apply_optional_enrichment(normalized_data)

    info(
        f"[AUDIT] success source={source} enriched_fields={len(enriched_fields)}",
        category="character_creation",
    )
    return CharacterCreationAuditResult(
        result_type=AUDIT_RESULT_SUCCESS,
        normalized_data=normalized_data,
        source=source,
        enriched_fields=enriched_fields,
    )


def audit_character_readiness(character_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run non-fatal readiness checks for sheet/PDF consumers."""
    result = audit_character_creation(character_data, source="readiness_audit", enable_enrichment=False)
    if result.result_type == AUDIT_RESULT_SUCCESS:
        return {"ready": True, "warnings": []}

    warning_text = [f"{entry['path']}: {entry['message']}" for entry in result.errors]
    return {
        "ready": False,
        "warnings": warning_text,
        "result_type": result.result_type,
    }


__all__ = [
    "AUDIT_RESULT_SCHEMA_ERROR",
    "AUDIT_RESULT_COMPLETENESS_ERROR",
    "AUDIT_RESULT_SUCCESS",
    "CharacterCreationAuditResult",
    "audit_character_creation",
    "audit_character_readiness",
    "READINESS_REPAIR_WRITABLE_FIELDS",
    "build_readiness_repair_proposal",
    "sanitize_readiness_repair_patch",
    "apply_readiness_repair_patch",
    "get_mechanical_snapshot",
    "diff_mechanical_snapshot",
]
