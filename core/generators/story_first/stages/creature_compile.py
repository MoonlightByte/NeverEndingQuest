# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Compile accepted original-creature briefs into frozen monster objects."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Tuple

import jsonschema

from ..compilers import safe_filename
from ..contracts import (
    AcceptedAreas,
    AcceptedCreatures,
    AcceptedOutline,
    StageEvidence,
    mutable_copy,
    strict_internal_contract,
)
from ..execution import (
    CompletionGateway,
    SemanticCorrectionError,
    execute_structured_stage,
)
from ..settings import STAGE_POLICIES, StagePolicy
from ..validators import require_ascii, semantic_creature_viability_checks


TASK_ID = "T103"
SCHEMA_NAME = "story_first_module_creature"
_MAX_APPEARANCE_CONTEXT_CHARS = 12_000
_MAX_CONTEXT_TEXT_CHARS = 800
_MAX_CONTEXT_LIST_ITEMS = 8
_AREA_CONTEXT_FIELDS = (
    "areaName",
    "areaType",
    "areaDescription",
    "terrain",
)
_LOCATION_CONTEXT_FIELDS = (
    "name",
    "type",
    "description",
    "dmInstructions",
    "accessibility",
    "plotHooks",
    "features",
    "traps",
    "npcs",
)
_OFFICIAL_SKILL_NAMES = frozenset(
    {
        "Acrobatics",
        "Animal Handling",
        "Arcana",
        "Athletics",
        "Deception",
        "History",
        "Insight",
        "Intimidation",
        "Investigation",
        "Medicine",
        "Nature",
        "Perception",
        "Performance",
        "Persuasion",
        "Religion",
        "Sleight of Hand",
        "Stealth",
        "Survival",
    }
)


def referenced_creatures(areas) -> List[str]:
    result = []
    seen = set()
    for area in areas:
        for location in area["locations"]:
            for monster in location.get("monsters", []):
                key = monster["name"].strip().casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(monster["name"].strip())
    return result


def _bounded_context_value(value: Any) -> Any:
    """Detach and bound accepted prose without changing its meaning or source."""
    if isinstance(value, str):
        if len(value) <= _MAX_CONTEXT_TEXT_CHARS:
            return value
        return value[:_MAX_CONTEXT_TEXT_CHARS].rstrip() + "... [truncated]"
    if isinstance(value, Mapping):
        return {str(key): _bounded_context_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [
            _bounded_context_value(item) for item in value[:_MAX_CONTEXT_LIST_ITEMS]
        ]
    return mutable_copy(value)


def appearance_context(areas, creature_name: str) -> Dict[str, Any]:
    """Return bounded accepted fiction only for this creature's appearances."""
    key = creature_name.strip().casefold()
    records = []
    for area in areas:
        area_context = {
            field: _bounded_context_value(area[field])
            for field in _AREA_CONTEXT_FIELDS
            if field in area
        }
        for location in area["locations"]:
            matches = [
                monster
                for monster in location.get("monsters", [])
                if monster["name"].strip().casefold() == key
            ]
            if not matches:
                continue
            records.append(
                {
                    "areaId": area["areaId"],
                    **area_context,
                    "locationId": location["locationId"],
                    **{
                        f"location{field[0].upper()}{field[1:]}": (
                            _bounded_context_value(location[field])
                        )
                        for field in _LOCATION_CONTEXT_FIELDS
                        if field in location
                    },
                    "dangerLevel": location["dangerLevel"],
                    "quantity": _bounded_context_value(matches[0]["quantity"]),
                }
            )

    selected = list(records)
    while selected:
        payload = {
            "locations": selected,
            "omittedAppearanceCount": len(records) - len(selected),
        }
        if (
            len(json.dumps(payload, indent=2, ensure_ascii=True))
            <= _MAX_APPEARANCE_CONTEXT_CHARS
        ):
            return payload
        selected.pop()
    return {"locations": [], "omittedAppearanceCount": len(records)}


def _response_contract(production_schema: Mapping[str, Any]) -> Dict[str, Any]:
    """Make provider-safe transport fields and optional guidance explicit."""
    contract = strict_internal_contract(mutable_copy(production_schema))
    contract["properties"].pop("skills")
    contract["required"].remove("skills")
    contract["properties"]["skillBonuses"] = {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "bonus": {"type": "integer"},
            },
            "required": ["name", "bonus"],
        },
    }
    contract["required"].append("skillBonuses")
    spellcasting = contract["properties"]["spellcasting"]
    contract["properties"]["spellcasting"] = {"anyOf": [spellcasting, {"type": "null"}]}
    contract["properties"]["dmGuidance"] = {"type": "string"}
    contract["required"].append("dmGuidance")
    return contract


def _normalize_for_production(value: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = mutable_copy(value)
    skill_entries = normalized.pop("skillBonuses")
    skills = {}
    skill_names = [entry["name"].strip() for entry in skill_entries]
    folded_names = [name.casefold() for name in skill_names]
    if any(not name for name in skill_names) or len(folded_names) != len(
        set(folded_names)
    ):
        raise SemanticCorrectionError(
            [
                {
                    "invariant": "unique_skill_names",
                    "offending": json.dumps(skill_names[:8], ensure_ascii=True),
                    "expectation": "skillBonuses names must be nonempty and unique",
                }
            ]
        )
    invalid_names = sorted(set(skill_names) - _OFFICIAL_SKILL_NAMES)
    if invalid_names:
        raise SemanticCorrectionError(
            [
                {
                    "invariant": "official_skill_names",
                    "offending": json.dumps(invalid_names[:8], ensure_ascii=True),
                    "expectation": "use exact official 5e skill names only",
                }
            ]
        )
    for entry, name in zip(skill_entries, skill_names):
        skills[name] = entry["bonus"]
    normalized["skills"] = skills
    normalized.pop("dmGuidance", None)
    if normalized.get("spellcasting") is None:
        normalized.pop("spellcasting", None)
    return normalized


def _validate_creature(
    value: Mapping[str, Any],
    brief: Mapping[str, Any],
    production_schema: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    guidance = str(value["dmGuidance"]).strip()
    normalized = _normalize_for_production(value)
    return _validate_production_creature(normalized, brief, production_schema, guidance)


def _validate_production_creature(
    value: Mapping[str, Any],
    brief: Mapping[str, Any],
    production_schema: Mapping[str, Any],
    guidance: str,
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Validate an already normalized frozen-schema creature artifact."""
    normalized = mutable_copy(value)
    guidance = str(guidance).strip()
    jsonschema.validate(normalized, mutable_copy(production_schema))
    require_ascii(normalized, "monster")
    require_ascii(guidance, "monster DM guidance")
    if normalized["name"] != brief["name"] or float(
        normalized["challengeRating"]
    ) != float(brief["targetCR"]):
        raise ValueError("trusted creature identity/CR drift")
    if (
        normalized["hitPoints"] != normalized["maxHitPoints"]
        or normalized["condition"] != "Alive"
    ):
        raise ValueError("invalid new-creature state")
    viability_metrics = semantic_creature_viability_checks(normalized)
    if any(score < 1 or score > 30 for score in normalized["abilities"].values()):
        raise ValueError("creature ability score is outside 1-30")
    if normalized["legendaryActions"]:
        raise ValueError("frozen schema cannot express executable legendary actions")
    for family in ("actions", "specialAbilities"):
        actions = normalized[family]
        names = [action["name"].strip().casefold() for action in actions]
        if not all(names) or len(names) != len(set(names)):
            raise ValueError(f"{family} entries are missing or duplicated")
        for action in actions:
            if not action["damageDice"].strip() or not action["damageType"].strip():
                raise ValueError(f"hollow {family} entry")
            if action["name"].strip().casefold() == "multiattack":
                raise ValueError("frozen schema cannot express Multiattack sequences")
    spellcasting = normalized.get("spellcasting")
    if spellcasting:
        spell_lists = spellcasting["spells"].values()
        if not any(spell_lists) or any(
            not spell.strip()
            for spells in spellcasting["spells"].values()
            for spell in spells
        ):
            raise ValueError("spellcasting must contain named spells")
    return (
        normalized,
        {
            "name": normalized["name"],
            "challengeRating": normalized["challengeRating"],
            "actionCount": len(normalized["actions"]),
            "specialAbilityCount": len(normalized["specialAbilities"]),
            "hasSpellcasting": bool(spellcasting),
            "hasDmGuidance": bool(guidance),
            **viability_metrics,
        },
        guidance,
    )


def run(
    *,
    outline: AcceptedOutline,
    areas: AcceptedAreas,
    production_schema: Mapping[str, Any],
    provider: str,
    model: str,
    model_options: Mapping[str, Any],
    gateway: CompletionGateway,
    policy: StagePolicy = STAGE_POLICIES["creature_compile"],
) -> AcceptedCreatures:
    """Compile only referenced accepted briefs; return no files or side effects."""
    outline_value = mutable_copy(outline.value)
    area_values = mutable_copy(areas.areas)
    briefs = {
        brief["name"].strip().casefold(): brief
        for brief in outline_value["creatureBriefs"]
    }
    references = referenced_creatures(area_values)
    missing = [name for name in references if name.casefold() not in briefs]
    if missing:
        raise ValueError(f"unbriefed creature references: {missing}")
    filenames = [safe_filename(name) for name in references]
    if any(not name for name in filenames) or len(filenames) != len(set(filenames)):
        raise ValueError("creature references have unsafe or colliding filenames")
    if not references:
        return AcceptedCreatures(
            monsters=(),
            guidance={},
            evidence=(
                StageEvidence(stage="creature_compile", attempts=0, result="skipped"),
            ),
            metrics={
                "referenced": (),
                "compiledCount": 0,
                "unusedBriefs": tuple(
                    brief["name"] for brief in outline_value["creatureBriefs"]
                ),
                "creatures": (),
                "originalCount": 0,
                "srdExactCount": 0,
            },
        )
    contract = _response_contract(production_schema)
    compiled = []
    guidance_by_creature = {}
    evidence = []
    creature_metrics = []
    for name in references:
        brief = briefs[name.casefold()]
        appearances = appearance_context(area_values, name)
        system = """Compile one accepted creature brief into the exact frozen monster
schema using SRD-compatible original mechanics. Preserve name and target CR exactly. Because
the frozen skills object uses dynamic keys that provider structured output cannot represent,
return skillBonuses as an array of unique {name, bonus} objects and do not return skills; the
adapter converts that transport field to the frozen skills object before validation. A new
creature has equal hitPoints/maxHitPoints, condition Alive, and at least one complete named
action. It must have speed above zero or explicitly state a positive fly, hover, swim,
burrow, or climb distance in specialAbilities text.
Actions and specialAbilities can represent only complete attack-shaped mechanics; emit a
complete executable entry or omit it. Never emit hollow prose or Multiattack. The frozen
legendaryActions shape has no executable mechanics, so return an empty array. Set
spellcasting to null for a non-spellcaster; otherwise supply at least one named spell. Put
story flavor that cannot be represented mechanically into dmGuidance as a concise DM note;
never discard it or present an unsupported mechanic as executable. Use ASCII and return only
JSON."""
        user = (
            "STORY PROMISE:\n"
            + outline.value["storyPromise"]
            + "\nBRIEF:\n"
            + json.dumps(brief, indent=2)
            + "\nACCEPTED APPEARANCE CONTEXT:\n"
            + json.dumps(appearances, indent=2)
            + "\nFROZEN SCHEMA:\n"
            + json.dumps(mutable_copy(production_schema), indent=2)
        )

        def gate(value, current_brief=brief):
            _, metrics, _ = _validate_creature(value, current_brief, production_schema)
            return metrics

        execution = execute_structured_stage(
            stage=f"creature_compile:{safe_filename(name)}",
            task_id=TASK_ID,
            schema_name=SCHEMA_NAME,
            provider=provider,
            model=model,
            model_options=model_options,
            temperature=policy.temperature,
            schema=contract,
            system_prompt=system,
            user_prompt=user,
            max_attempts=policy.max_attempts,
            semantic_gate=gate,
            gateway=gateway,
            correction_guidance=(
                "Return legendaryActions as an empty array and never emit Multiattack. "
                "Express only complete supported actions; preserve unrepresentable story "
                "flavor as non-mechanical dmGuidance."
            ),
        )
        normalized, metrics, guidance = _validate_creature(
            execution.value, brief, production_schema
        )
        compiled.append(normalized)
        if guidance:
            guidance_by_creature[normalized["name"]] = guidance
        evidence.append(execution.evidence)
        creature_metrics.append(
            {
                **metrics,
                "provenanceMode": "original",
                "compendiumKey": "",
                "compendiumSourceHash": None,
                "attempts": execution.evidence.attempts,
            }
        )
    referenced_keys = {name.casefold() for name in references}
    return AcceptedCreatures(
        monsters=tuple(compiled),
        guidance=guidance_by_creature,
        evidence=tuple(evidence),
        metrics={
            "referenced": tuple(references),
            "compiledCount": len(compiled),
            "unusedBriefs": tuple(
                brief["name"]
                for brief in outline_value["creatureBriefs"]
                if brief["name"].casefold() not in referenced_keys
            ),
            "creatures": creature_metrics,
            "originalCount": len(creature_metrics),
            "srdExactCount": 0,
        },
    )
