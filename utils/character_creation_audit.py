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
    "backstory",
    "backgroundFeature.name",
    "backgroundFeature.description",
]

READINESS_REPAIR_WRITABLE_FIELDS = [
    "personality_traits",
    "ideals",
    "bonds",
    "flaws",
    "backstory",
    "backgroundFeature.name",
    "backgroundFeature.description",
]

_READINESS_REPAIR_FALLBACK_TEXT = {
    "personality_traits": "I stay alert in danger and keep my focus on protecting the party.",
    "ideals": "I believe courage and steady judgment can turn the tide of any trial.",
    "bonds": "I owe my companions loyalty; their safety is my first duty.",
    "flaws": "I can be stubborn under pressure and slow to ask for help.",
    "backstory": (
        "Your character has a history of trials and encounters that led them "
        "to the path of adventure. This will be revealed through play."
    ),
    "backgroundFeature.name": (
        "A unique benefit tied to your background that provides social access or specialized knowledge."
    ),
    "backgroundFeature.description": (
        "Your background grants trusted social footing among people who share your prior trade and culture."
    ),
}

# Generic placeholder strings for backgroundFeature narrative fields (normalized detection)
# Used to flag narrative-incomplete placeholders during readiness checks and remediation.
_BACKGROUNDFEATURE_NAME_PLACEHOLDERS = frozenset({
    "",
    "feature",
    "background feature",
    "unknown",
})

_BACKGROUNDFEATURE_DESCRIPTION_PLACEHOLDERS = frozenset({
    "",
    "a defining feature from your background.",
    "background feature",
    "standard background feature",
})


def _normalize_for_placeholder_matching(value: Any) -> str:
    """Normalize input to lowercased, trimmed ASCII string for deterministic placeholder detection."""
    if value is None:
        return ""
    return str(value).strip().lower()


def is_generic_background_feature_name(value: Any) -> bool:
    """Return True if the provided value matches known generic name placeholders.

    Determines whether the background feature name is a placeholder that should
    be flagged as narrative-incomplete. Normalizes the value for case/whitespace
    agnostic comparison against the allowlist.

    Args:
        value: The backgroundFeature.name value (typically str or None)

    Returns:
        bool: True if value matches a generic placeholder pattern
    """
    normalized = _normalize_for_placeholder_matching(value)
    return normalized in _BACKGROUNDFEATURE_NAME_PLACEHOLDERS


def is_generic_background_feature_description(value: Any) -> bool:
    """Return True if the provided value matches known generic description placeholders.

    Determines whether the background feature description is a placeholder that
    should be flagged as narrative-incomplete. Normalizes the value for
    case/whitespace agnostic comparison against the allowlist.

    Args:
        value: The backgroundFeature.description value (typically str or None)

    Returns:
        bool: True if value matches a generic placeholder pattern
    """
    normalized = _normalize_for_placeholder_matching(value)
    return normalized in _BACKGROUNDFEATURE_DESCRIPTION_PLACEHOLDERS


def get_placeholder_patterns() -> Dict[str, frozenset]:
    """Return mapping of field path to allowed placeholder patterns for remediation tooling.

    Useful for scripts and migration tools that need to know which values are
    considered placeholders without hardcoding patterns externally.

    Returns:
        Dict mapping 'backgroundFeature.name' and 'backgroundFeature.description'
        to their respective placeholder frozensets.
    """
    return {
        "backgroundFeature.name": _BACKGROUNDFEATURE_NAME_PLACEHOLDERS,
        "backgroundFeature.description": _BACKGROUNDFEATURE_DESCRIPTION_PLACEHOLDERS,
    }


# Known background feature suggestions (SRD 5.2.1 style)
# Used for deterministic prefill when background feature fields are blank or generic.
_KNOWN_BACKGROUND_FEATURES: Dict[str, Dict[str, str]] = {
    "acolyte": {
        "name": "Shelter of the Faithful",
        "description": "You command the respect of those who share your faith, and you can perform the religious ceremonies of your deity. You can expect to receive free healing and care at a temple, shrine, or other established presence of your faith.",
    },
    "criminal": {
        "name": "Criminal Contact",
        "description": "You have a reliable and trustworthy contact who acts as your liaison to a network of other criminals. You know how to get messages to and from your contact, even over great distances.",
    },
    "folk hero": {
        "name": "Rustic Hospitality",
        "description": "Since you come from the ranks of the common folk, you fit in among them with ease. You can find a place to hide, rest, or recuperate among other commoners, unless you have shown yourself to be a danger to them.",
    },
    "noble": {
        "name": "Position of Privilege",
        "description": "Thanks to your noble birth, people are inclined to think the best of you. You are welcome in high society, and people assume you have the right to be wherever you are.",
    },
    "sage": {
        "name": "Researcher",
        "description": "When you attempt to learn or recall a piece of lore, if you do not know that information, you often know where and from whom you can obtain it.",
    },
    "soldier": {
        "name": "Military Rank",
        "description": "Soldiers loyal to your former military organization still recognize your authority and military rank. They will defer to you if they are of a lower rank, and you can invoke your rank to exert influence over other soldiers.",
    },
}


def get_known_background_feature_suggestion(background: Any) -> Optional[Dict[str, str]]:
    """Return deterministic background feature suggestion for known backgrounds.

    Provides SRD-style background feature entries for recognized backgrounds.
    Returns None for unknown backgrounds to avoid forcing synthetic values.

    Args:
        background: The character background value (typically str)

    Returns:
        Dict with 'name' and 'description' keys for known backgrounds, None otherwise.
    """
    if background is None:
        return None
    normalized = str(background).strip().lower()
    return _KNOWN_BACKGROUND_FEATURES.get(normalized)


def apply_background_feature_suggestion_if_generic(
    background: Any,
    name_value: Any,
    description_value: Any,
) -> Dict[str, str]:
    """Apply deterministic background feature suggestion only to generic/blank fields.

    Returns name and description values, preferring authored non-generic values
    and filling in with known background suggestions only where fields are
    blank or match generic placeholder patterns.

    Args:
        background: The character background (e.g., 'criminal', 'sage')
        name_value: Current backgroundFeature.name value
        description_value: Current backgroundFeature.description value

    Returns:
        Dict with 'name' and 'description' keys. Authored non-generic values
        are preserved; blank/generic values are filled from known background
        suggestions if available; unknown backgrounds leave values unchanged.
    """
    result: Dict[str, str] = {
        "name": str(name_value or "").strip(),
        "description": str(description_value or "").strip(),
    }

    suggestion = get_known_background_feature_suggestion(background)
    if suggestion is None:
        # Unknown background - leave values unchanged
        return result

    # Apply suggestion only to blank or generic placeholder fields
    if is_generic_background_feature_name(name_value):
        result["name"] = suggestion["name"]

    if is_generic_background_feature_description(description_value):
        result["description"] = suggestion["description"]

    return result


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
        "age": "",
        "height": "",
        "weight": "",
        "eyes": "",
        "skin": "",
        "hair": "",
        "backstory": "",
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
    description = background_feature.get("description")
    if is_generic_background_feature_description(description):
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

    # Check for empty fields and generic placeholders in background feature
    completeness_missing: List[str] = []
    completeness_errors: List[Dict[str, str]] = []
    
    for path in _COMPLETENESS_PATHS:
        value = _get_nested_value(normalized_data, path)
        if _is_blank(value):
            completeness_missing.append(path)
            completeness_errors.append({"path": path, "message": "Field cannot be empty"})
    
    # Check background feature fields for generic placeholders
    bg_feature = normalized_data.get("backgroundFeature", {})
    bg_name = bg_feature.get("name")
    bg_description = bg_feature.get("description")
    
    if is_generic_background_feature_name(bg_name):
        if "backgroundFeature.name" not in completeness_missing:
            completeness_missing.append("backgroundFeature.name")
            completeness_errors.append({
                "path": "backgroundFeature.name",
                "message": "Background feature name is generic placeholder text",
            })
    
    if is_generic_background_feature_description(bg_description):
        if "backgroundFeature.description" not in completeness_missing:
            completeness_missing.append("backgroundFeature.description")
            completeness_errors.append({
                "path": "backgroundFeature.description",
                "message": "Background feature description is generic placeholder text",
            })
    
    if completeness_missing:
        warning(
            f"[AUDIT] completeness_error source={source} missing={len(completeness_missing)}",
            category="character_creation",
        )
        return CharacterCreationAuditResult(
            result_type=AUDIT_RESULT_COMPLETENESS_ERROR,
            normalized_data=normalized_data,
            source=source,
            errors=completeness_errors,
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


# Portrait-driving profile fields for character sheet quality
_PROFILE_READINESS_PATHS = [
    "age",
    "height",
    "weight",
    "eyes",
    "skin",
    "hair",
    "personality_traits",
    "ideals",
    "bonds",
    "flaws",
    "backstory",
    "backgroundFeature.name",
    "backgroundFeature.description",
]

# Appearance fields specifically (used for portrait generation context)
_APPEARANCE_PROFILE_FIELDS = [
    "age",
    "height",
    "weight",
    "eyes",
    "skin",
    "hair",
]


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


def audit_profile_readiness(character_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check portrait-driving profile field completeness.
    
    This is separate from schema/completeness validation and does NOT
    block operations. It surfaces warnings for optional fields that improve
    character sheet quality and portrait generation context.
    
    Generic placeholders in background feature fields are treated as
    incomplete narrative quality signals, not just blank strings.
    
    Returns:
        Dict with:
        - profile_ready: bool (True if all profile fields present)
        - missing_profile_fields: list of missing field paths
        - missing_appearance_fields: list of missing appearance-only paths
        - warnings: list of human-readable warning strings
    """
    missing_profile: List[str] = []
    missing_appearance: List[str] = []
    
    for path in _PROFILE_READINESS_PATHS:
        value = _get_nested_value(character_data, path)
        is_blank = (value is None) or (isinstance(value, str) and not value.strip())
        
        # Check for generic placeholders in background feature fields
        if path == "backgroundFeature.name":
            bg_name = character_data.get("backgroundFeature", {}).get("name")
            if is_generic_background_feature_name(bg_name):
                is_blank = True
        elif path == "backgroundFeature.description":
            bg_desc = character_data.get("backgroundFeature", {}).get("description")
            if is_generic_background_feature_description(bg_desc):
                is_blank = True
        
        if is_blank:
            missing_profile.append(path)
            if path in _APPEARANCE_PROFILE_FIELDS:
                missing_appearance.append(path)
    
    warnings: List[str] = []
    if missing_appearance:
        warnings.append(f"Missing appearance metadata: {', '.join(missing_appearance)}")
    if missing_profile:
        remaining = [p for p in missing_profile if p not in missing_appearance]
        if remaining:
            warnings.append(f"Missing profile fields: {', '.join(remaining)}")
    
    return {
        "profile_ready": len(missing_profile) == 0,
        "missing_profile_fields": missing_profile,
        "missing_appearance_fields": missing_appearance,
        "warnings": warnings,
    }


def seed_missing_appearance_fields(character_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure appearance field keys exist (as empty strings if missing).
    
    This is a non-destructive operation that ensures promoted NPCs have
    the expected appearance keys present for future profile editing.
    
    Args:
        character_data: Character dict to seed
        
    Returns:
        Updated character_data with appearance keys guaranteed present
    """
    seeded = deepcopy(character_data)
    
    for field in _APPEARANCE_PROFILE_FIELDS:
        if field not in seeded or seeded[field] is None:
            seeded[field] = ""
    
    return seeded


__all__ = [
    "AUDIT_RESULT_SCHEMA_ERROR",
    "AUDIT_RESULT_COMPLETENESS_ERROR",
    "AUDIT_RESULT_SUCCESS",
    "CharacterCreationAuditResult",
    "audit_character_creation",
    "audit_character_readiness",
    "audit_profile_readiness",
    "seed_missing_appearance_fields",
    "READINESS_REPAIR_WRITABLE_FIELDS",
    "build_readiness_repair_proposal",
    "sanitize_readiness_repair_patch",
    "apply_readiness_repair_patch",
    "get_mechanical_snapshot",
    "diff_mechanical_snapshot",
    "is_generic_background_feature_name",
    "is_generic_background_feature_description",
    "get_placeholder_patterns",
    "get_known_background_feature_suggestion",
    "apply_background_feature_suggestion_if_generic",
]
