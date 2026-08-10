# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Story-first boundary types and provider-neutral response contracts."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from dataclasses import field
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def freeze_value(value: Any) -> Any:
    """Recursively freeze JSON-compatible boundary data."""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    return value


def mutable_copy(value: Any) -> Any:
    """Return a detached JSON-compatible copy for prompts and serializers."""
    if isinstance(value, Mapping):
        return {key: mutable_copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [mutable_copy(item) for item in value]
    return copy.deepcopy(value)


@dataclass(frozen=True)
class StorySeed:
    """Immutable player intent plus the exact mechanical controls accepted by T030."""

    seed_id: str
    concept: str
    module_controls: Mapping[str, Any]
    campaign_context: Mapping[str, Any]
    mandatory_facts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "module_controls", freeze_value(self.module_controls))
        object.__setattr__(
            self, "campaign_context", freeze_value(self.campaign_context)
        )
        object.__setattr__(self, "mandatory_facts", tuple(self.mandatory_facts))

    def to_prompt_value(self) -> Dict[str, Any]:
        return {
            "seedId": self.seed_id,
            "concept": self.concept,
            "moduleControls": mutable_copy(self.module_controls),
            "campaignContext": mutable_copy(self.campaign_context),
            "mandatoryFacts": list(self.mandatory_facts),
        }


@dataclass(frozen=True)
class StageEvidence:
    """Safe stage outcome metadata; never includes raw output or provider secrets."""

    stage: str
    attempts: int
    result: str
    failure_class: Optional[str] = None
    failure_classes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AcceptedOutline:
    value: Mapping[str, Any]
    evidence: StageEvidence
    metrics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", freeze_value(self.value))
        object.__setattr__(self, "metrics", freeze_value(self.metrics))


@dataclass(frozen=True)
class AcceptedAreaBinding:
    value: Mapping[str, Any]
    evidence: StageEvidence
    metrics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", freeze_value(self.value))
        object.__setattr__(self, "metrics", freeze_value(self.metrics))


@dataclass(frozen=True)
class AcceptedPlot:
    value: Mapping[str, Any]
    evidence: StageEvidence
    metrics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", freeze_value(self.value))
        object.__setattr__(self, "metrics", freeze_value(self.metrics))


@dataclass(frozen=True)
class CompiledWorld:
    areas: tuple[Mapping[str, Any], ...]
    maps: tuple[Mapping[str, Any], ...]
    beat_locations: Mapping[str, str]
    entry: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "areas", freeze_value(self.areas))
        object.__setattr__(self, "maps", freeze_value(self.maps))
        object.__setattr__(self, "beat_locations", freeze_value(self.beat_locations))
        object.__setattr__(self, "entry", freeze_value(self.entry))


@dataclass(frozen=True)
class AcceptedAreas:
    areas: tuple[Mapping[str, Any], ...]
    evidence: tuple[StageEvidence, ...]
    metrics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "areas", freeze_value(self.areas))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "metrics", freeze_value(self.metrics))


@dataclass(frozen=True)
class AcceptedCreatures:
    monsters: tuple[Mapping[str, Any], ...]
    guidance: Mapping[str, str]
    evidence: tuple[StageEvidence, ...]
    metrics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "monsters", freeze_value(self.monsters))
        object.__setattr__(self, "guidance", freeze_value(self.guidance))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "metrics", freeze_value(self.metrics))


@dataclass(frozen=True)
class StoryFirstBuildResult:
    outline: Mapping[str, Any]
    areas: tuple[Mapping[str, Any], ...]
    maps: tuple[Mapping[str, Any], ...]
    plot: Mapping[str, Any]
    monsters: tuple[Mapping[str, Any], ...]
    evidence: tuple[StageEvidence, ...]
    entry: Mapping[str, str] = field(default_factory=dict)
    advisories: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outline", freeze_value(self.outline))
        object.__setattr__(self, "areas", freeze_value(self.areas))
        object.__setattr__(self, "maps", freeze_value(self.maps))
        object.__setattr__(self, "plot", freeze_value(self.plot))
        object.__setattr__(self, "monsters", freeze_value(self.monsters))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "entry", freeze_value(self.entry))
        object.__setattr__(self, "advisories", freeze_value(self.advisories))


def _obj(properties: Dict[str, Any], required=None) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required if required is not None else properties),
    }


def strict_internal_contract(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Build one provider-neutral response contract from a production-compatible shape.

    This is deliberately separate from ``strict_openai_schema``: every provider response
    is validated against this same contract, then against the untouched production schema.
    """
    result = copy.deepcopy(schema)

    def visit(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "object" or "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node.get("properties", {}))
        for value in node.values():
            if isinstance(value, dict):
                visit(value)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

    visit(result)
    return result


def outline_schema() -> Dict[str, Any]:
    truth = _obj(
        {
            "id": {"type": "string", "pattern": "^T[0-9]{3}$"},
            "fact": {"type": "string", "minLength": 10},
            "visibleAtStart": {"type": "boolean"},
        }
    )
    opposition = _obj(
        {
            "name": {"type": "string", "minLength": 2},
            "nature": {"type": "string", "minLength": 5},
            "goal": {"type": "string", "minLength": 10},
            "method": {"type": "string", "minLength": 10},
            "whyNow": {"type": "string", "minLength": 10},
        }
    )
    area = _obj(
        {
            "roleId": {"type": "string", "pattern": "^AR[0-9]{3}$"},
            "name": {"type": "string", "minLength": 3},
            "storyPurpose": {"type": "string", "minLength": 20},
            "environment": {"type": "string", "minLength": 3},
            "dangerBand": {
                "type": "string",
                "enum": ["Low", "Medium", "High", "Very High"],
            },
        }
    )
    beat = _obj(
        {
            "id": {"type": "string", "pattern": "^B[0-9]{3}$"},
            "title": {"type": "string", "minLength": 3},
            "purpose": {"type": "string", "minLength": 20},
            "areaRoleId": {"type": "string", "pattern": "^AR[0-9]{3}$"},
            "prerequisites": {
                "type": "array",
                "items": {"type": "string", "pattern": "^B[0-9]{3}$"},
            },
            "playerApproaches": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 3},
            },
            "discoveries": {
                "type": "array",
                "items": {"type": "string", "minLength": 3},
            },
            "consequences": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 5},
            },
            "isCrescendo": {"type": "boolean"},
            "optionalTerminal": {"type": "boolean"},
        }
    )
    thread = _obj(
        {
            "id": {"type": "string", "pattern": "^S[0-9]{3}$"},
            "title": {"type": "string", "minLength": 3},
            "hook": {"type": "string", "minLength": 10},
            "mainStoryPayoff": {"type": "string", "minLength": 10},
            "anchorBeatId": {"type": "string", "pattern": "^B[0-9]{3}$"},
        }
    )
    creature = _obj(
        {
            "name": {"type": "string", "minLength": 2},
            "concept": {"type": "string", "minLength": 20},
            "storyRole": {"type": "string", "minLength": 10},
            "targetCR": {"type": "number", "minimum": 0},
        }
    )
    return _obj(
        {
            "moduleTitle": {"type": "string", "minLength": 3},
            "conceptSummary": {"type": "string", "minLength": 40},
            "storyPromise": {"type": "string", "minLength": 20},
            "truthLog": {"type": "array", "minItems": 1, "items": truth},
            "opposition": opposition,
            "areas": {"type": "array", "minItems": 1, "items": area},
            "beats": {"type": "array", "minItems": 1, "items": beat},
            "sideThreads": {"type": "array", "items": thread},
            "creatureBriefs": {"type": "array", "items": creature},
            "continuityTreatment": {
                "type": "array",
                "items": {"type": "string", "minLength": 5},
            },
        }
    )


def area_binding_schema(
    seed: Dict[str, Any], outline: Dict[str, Any]
) -> Dict[str, Any]:
    role = _obj(
        {
            "roleKey": {"type": "string", "pattern": "^L[0-9]{2}$"},
            "name": {"type": "string", "minLength": 3},
            "type": {"type": "string", "minLength": 3},
            "storyPurpose": {"type": "string", "minLength": 15},
            "connections": {
                "type": "array",
                "items": {"type": "string", "pattern": "^L[0-9]{2}$"},
            },
            "beatIds": {
                "type": "array",
                "items": {"type": "string", "pattern": "^B[0-9]{3}$"},
            },
        }
    )
    area = _obj(
        {
            "areaRoleId": {"type": "string", "pattern": "^AR[0-9]{3}$"},
            "areaName": {"type": "string", "minLength": 3},
            "areaDescription": {"type": "string", "minLength": 30},
            "areaType": {"type": "string", "minLength": 3},
            "dangerLevel": {
                "type": "string",
                "enum": ["Low", "Medium", "High", "Very High"],
            },
            "recommendedLevel": {
                "type": "integer",
                "minimum": seed["moduleControls"]["levelMin"],
                "maximum": seed["moduleControls"]["levelMax"],
            },
            "locationRoles": {
                "type": "array",
                "minItems": seed["moduleControls"]["locationsPerArea"],
                "maxItems": seed["moduleControls"]["locationsPerArea"],
                "items": role,
            },
        }
    )
    link = _obj(
        {
            "fromAreaRoleId": {"type": "string", "pattern": "^AR[0-9]{3}$"},
            "fromRoleKey": {"type": "string", "pattern": "^L[0-9]{2}$"},
            "toAreaRoleId": {"type": "string", "pattern": "^AR[0-9]{3}$"},
            "toRoleKey": {"type": "string", "pattern": "^L[0-9]{2}$"},
            "narrativeReason": {"type": "string", "minLength": 15},
        }
    )
    anchor = _obj(
        {
            "beatId": {"type": "string", "pattern": "^B[0-9]{3}$"},
            "areaRoleId": {"type": "string", "pattern": "^AR[0-9]{3}$"},
            "roleKey": {"type": "string", "pattern": "^L[0-9]{2}$"},
        }
    )
    return _obj(
        {
            "areas": {
                "type": "array",
                "minItems": seed["moduleControls"]["numAreas"],
                "maxItems": seed["moduleControls"]["numAreas"],
                "items": area,
            },
            "crossAreaLinks": {
                "type": "array",
                "minItems": 0 if seed["moduleControls"]["numAreas"] == 1 else 1,
                "items": link,
            },
            "beatAnchors": {
                "type": "array",
                "minItems": len(outline["beats"]),
                "maxItems": len(outline["beats"]),
                "items": anchor,
            },
        }
    )


def constrained_plot_schema(repo: Path, outline: Dict[str, Any]) -> Dict[str, Any]:
    schema = copy.deepcopy(_load_json(repo / "schemas/plot_schema.json"))
    schema["properties"]["plotPoints"]["minItems"] = len(outline["beats"])
    schema["properties"]["plotPoints"]["maxItems"] = len(outline["beats"])
    return schema


def npc_repair_schema(location_ids, loca_schema):
    props = loca_schema["properties"]["locations"]["items"]["properties"]
    repair = _obj(
        {
            "locationId": {"type": "string", "enum": list(location_ids)},
            "description": copy.deepcopy(props["description"]),
            "dmInstructions": copy.deepcopy(props["dmInstructions"]),
            "npcs": copy.deepcopy(props["npcs"]),
        }
    )
    return _obj(
        {
            "repairs": {
                "type": "array",
                "minItems": len(location_ids),
                "maxItems": len(location_ids),
                "items": repair,
            }
        }
    )


def hardening_schema(location_ids, loca_schema):
    dm = copy.deepcopy(
        loca_schema["properties"]["locations"]["items"]["properties"]["dmInstructions"]
    )
    repair = _obj(
        {
            "locationId": {"type": "string", "enum": list(location_ids)},
            "dmInstructions": dm,
        }
    )
    return _obj(
        {
            "repairs": {
                "type": "array",
                "minItems": len(location_ids),
                "maxItems": len(location_ids),
                "items": repair,
            }
        }
    )
