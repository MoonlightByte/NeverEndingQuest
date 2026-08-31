"""Strict contracts for private NPC voice requests and responses."""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, Iterable, Mapping

from jsonschema import Draft202012Validator


TASK_ID = "T105"
PACKET_VERSION = "npc-voice-packet/v1"
PROMPT_VERSION = "npc-voice-prompt/v3"
RESPONSE_SCHEMA_VERSION = "npc-voice-response/v2"
AFFINITY_EVENT_TYPES = (
    "abandon",
    "betray",
    "deceive",
    "disrespect",
    "give",
    "harm",
    "heal",
    "honor",
    "protect",
    "rescue",
    "share",
    "support",
    "threaten",
    "trust",
)
NEGATIVE_AFFINITY_EVENT_TYPES = frozenset(
    {"abandon", "betray", "deceive", "disrespect", "harm", "threaten"}
)
POSITIVE_AFFINITY_EVENT_TYPES = (
    frozenset(AFFINITY_EVENT_TYPES) - NEGATIVE_AFFINITY_EVENT_TYPES
)


class ThoughtContractError(ValueError):
    """A packet or model response violated the T105 contract."""


def strict_object(
    properties: Dict[str, Any], required: Iterable[str]
) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


AFFINITY_EVENT_SCHEMA = strict_object(
    {
        "actor": {"type": "string", "minLength": 1},
        "target": {"type": "string", "minLength": 1},
        "eventType": {"type": "string", "enum": list(AFFINITY_EVENT_TYPES)},
        "magnitude": {"type": "integer", "enum": [-3, -2, -1, 1, 2, 3]},
        "witnessed": {"type": "boolean"},
    },
    ("actor", "target", "eventType", "magnitude", "witnessed"),
)

def _nullable_string() -> Dict[str, Any]:
    """A required key whose value is either null or a non-empty string."""
    return {
        "anyOf": [
            {"type": "null"},
            {"type": "string", "minLength": 1},
        ]
    }


# The enriched advisory voice response. In addition to the private ``thought`` and
# the typed ``affinityEvent`` (unchanged), the NPC proposes what it would SAY (a
# line of dialogue), what it would DO (an action/intent, no mechanics asserted),
# and what it currently WANTs (a desire/goal). All three are ADVISORY: the Dungeon
# Master reads them as input and may reword, cut, or override them for legality and
# scene. say/do/want are nullable so an NPC with nothing to add returns null.
THOUGHT_RESPONSE_SCHEMA = strict_object(
    {
        "say": _nullable_string(),
        "do": _nullable_string(),
        "want": _nullable_string(),
        "thought": {"type": "string", "minLength": 1},
        "affinityEvent": {
            "anyOf": [
                {"type": "null"},
                AFFINITY_EVENT_SCHEMA,
            ]
        },
    },
    # say/do/want are OPTIONAL, not required: the same schema/validator serves both
    # the enriched voice call (which returns all three) and the isolated affinity
    # classifier call (which returns only thought + affinityEvent). Absent fields
    # are treated as null. thought + affinityEvent stay required.
    ("thought", "affinityEvent"),
)
# Clearer alias for the enriched contract (kept alongside the historical name so
# existing imports keep working).
VOICE_RESPONSE_SCHEMA = THOUGHT_RESPONSE_SCHEMA

PROFILE_SCHEMA = strict_object(
    {
        "background": {"type": "string"},
        "personality": {"type": "string"},
        "ideals": {"type": "string"},
        "bonds": {"type": "string"},
        "flaws": {"type": "string"},
    },
    ("background", "personality", "ideals", "bonds", "flaws"),
)

STRUCTURED_PROFILE_SCHEMA = strict_object(
    {
        "voice": strict_object(
            {
                "cadence": {"type": "string"},
                "diction": {"type": "string"},
                "taboos": {
                    "type": "array",
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
            },
            ("cadence", "diction", "taboos"),
        ),
        "goals": {
            "type": "array", "minItems": 1, "maxItems": 3, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "fears": {
            "type": "array", "maxItems": 3, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "values": {
            "type": "array", "minItems": 1, "maxItems": 5, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "preferences": {
            "type": "array", "maxItems": 5, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "boundaries": {
            "type": "array", "maxItems": 5, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "conflictStyle": {"type": "string"},
        "initiativeTendency": {
            "type": "string",
            "enum": ["reserved", "balanced", "proactive"]
        },
        "riskTolerance": {
            "type": "string", "enum": ["cautious", "measured", "bold"]
        },
        "protectionPriorities": {
            "type": "array", "maxItems": 3, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "retreatRules": {
            "type": "array", "maxItems": 3, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "arcSeeds": {
            "type": "array", "maxItems": 2, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
    },
    (
        "voice", "goals", "fears", "values", "preferences", "boundaries",
        "conflictStyle", "initiativeTendency", "riskTolerance",
        "protectionPriorities", "retreatRules", "arcSeeds",
    ),
)

# Phase 6 adds the canonical structured seed without invalidating stored Phase
# 1-5 packet fixtures. Production composers include these fields whenever the
# sidecar has a profile; older saves continue with the authored five-field lens.
PROFILE_SCHEMA["properties"].update(
    copy.deepcopy(STRUCTURED_PROFILE_SCHEMA["properties"])
)

RELATIONSHIP_STATE_SCHEMA = strict_object(
    {
        "trust": {"type": "number", "minimum": -1, "maximum": 1},
        "power": {"type": "number", "minimum": -1, "maximum": 1},
        "intimacy": {"type": "number", "minimum": 0, "maximum": 1},
        "fear": {"type": "number", "minimum": 0, "maximum": 1},
        "respect": {"type": "number", "minimum": -1, "maximum": 1},
    },
    ("trust", "power", "intimacy", "fear", "respect"),
)

RECENT_EVENT_SCHEMA = strict_object(
    {
        "actor": {"type": "string", "minLength": 1},
        "target": {"type": "string", "minLength": 1},
        "eventType": {"type": "string", "enum": list(AFFINITY_EVENT_TYPES)},
        "magnitude": {"type": "integer", "enum": [-3, -2, -1, 1, 2, 3]},
        "witnessed": {"type": "boolean"},
        "summary": {"type": "string", "minLength": 1},
    },
    ("actor", "target", "eventType", "magnitude", "witnessed", "summary"),
)

RELATIONSHIP_EVIDENCE_SCHEMA = strict_object(
    {
        "actorId": {"type": "string", "minLength": 1},
        "actor": {"type": "string", "minLength": 1},
        "targetId": {"type": "string", "minLength": 1},
        "target": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "minLength": 1},
        "witnessed": {"type": "boolean"},
    },
    ("actorId", "actor", "targetId", "target", "summary", "witnessed"),
)

COMMON_PACKET_PROPERTIES: Dict[str, Any] = {
    "contractVersion": {"const": PACKET_VERSION},
    "taskId": {"const": TASK_ID},
    "mode": {"enum": ["COMBAT", "OUT_OF_COMBAT"]},
    "beat": strict_object(
        {
            "id": {"type": "string", "minLength": 1},
            "summary": {"type": "string", "minLength": 1},
            "relationshipEvidence": {
                "anyOf": [
                    {"type": "null"},
                    RELATIONSHIP_EVIDENCE_SCHEMA,
                ]
            },
        },
        ("id", "summary", "relationshipEvidence"),
    ),
    "npc": strict_object(
        {
            "id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "role": {"type": "string", "minLength": 1},
            "profile": PROFILE_SCHEMA,
        },
        ("id", "name", "role", "profile"),
    ),
    "relationship": strict_object(
        {
            "counterpartyId": {
                "type": "string",
                "minLength": 1,
            },
            "counterpartyName": {
                "type": "string",
                "minLength": 1,
            },
            "state": RELATIONSHIP_STATE_SCHEMA,
            "recentEvents": {
                "type": "array",
                "maxItems": 3,
                "items": RECENT_EVENT_SCHEMA,
            },
        },
        ("counterpartyId", "counterpartyName", "state", "recentEvents"),
    ),
    "scene": strict_object(
        {
            "module": {"type": "string", "minLength": 1},
            "locationId": {"type": "string", "minLength": 1},
            "location": {"type": "string", "minLength": 1},
            "presentActors": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
            },
            "stakes": {"type": "string", "minLength": 1},
            "recentEvents": {
                "type": "array",
                "maxItems": 6,
                "items": {"type": "string", "minLength": 1},
            },
        },
        ("module", "locationId", "location", "presentActors", "stakes", "recentEvents"),
    ),
    "working": strict_object(
        {
            "currentGoal": {"type": "string"},
            "priorPrivateIntent": {"type": "string"},
            "openQuestion": {"type": "string"},
            "moodTags": {
                "type": "array",
                "maxItems": 4,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
            },
            "expiresAfterTurn": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "integer", "minimum": 0},
                ]
            },
        },
        (
            "currentGoal",
            "priorPrivateIntent",
            "openQuestion",
            "moodTags",
            "expiresAfterTurn",
        ),
    ),
}

COMBAT_CONTEXT_SCHEMA = strict_object(
    {
        "status": strict_object(
            {
                "hitPoints": strict_object(
                    {
                        "current": {"type": "integer", "minimum": 0},
                        "maximum": {"type": "integer", "minimum": 1},
                    },
                    ("current", "maximum"),
                ),
                "armorClass": {"type": "integer", "minimum": 1, "maximum": 40},
                "conditions": {
                    "type": "array",
                    "maxItems": 8,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
                "position": {"type": "string", "minLength": 1},
            },
            ("hitPoints", "armorClass", "conditions", "position"),
        ),
        "capabilities": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1},
        },
        "allies": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1},
        },
        "threats": {
            "type": "array",
            "maxItems": 8,
            "items": strict_object(
                {
                    "name": {"type": "string", "minLength": 1},
                    "position": {"type": "string", "minLength": 1},
                    "intent": {"type": "string", "minLength": 1},
                },
                ("name", "position", "intent"),
            ),
        },
        "lastRoundEvents": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1},
        },
    },
    ("status", "capabilities", "allies", "threats", "lastRoundEvents"),
)

OUT_OF_COMBAT_CONTEXT_SCHEMA = strict_object(
    {
        "utilities": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1},
        },
        "items": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1},
        },
        "socialContext": {"type": "string", "minLength": 1},
        "currentGoals": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {"type": "string", "minLength": 1},
        },
    },
    ("utilities", "items", "socialContext", "currentGoals"),
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def packet_schema(mode: str) -> Dict[str, Any]:
    properties = copy.deepcopy(COMMON_PACKET_PROPERTIES)
    properties["context"] = (
        COMBAT_CONTEXT_SCHEMA if mode == "COMBAT" else OUT_OF_COMBAT_CONTEXT_SCHEMA
    )
    return strict_object(properties, tuple(properties))


def openai_response_format() -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "npc_voice_response",
            "strict": True,
            "schema": copy.deepcopy(THOUGHT_RESPONSE_SCHEMA),
        },
    }


def gemini_response_schema() -> Dict[str, Any]:
    """Return Gemini's strict subset with a nullable event object."""
    from model_config import convert_to_gemini_schema

    non_nullable = copy.deepcopy(THOUGHT_RESPONSE_SCHEMA)
    non_nullable["properties"]["affinityEvent"] = copy.deepcopy(
        AFFINITY_EVENT_SCHEMA
    )
    # say/do/want are anyOf[null,string]; Gemini takes a single typed schema, so
    # flatten each to a plain string and mark it nullable after conversion.
    nullable_fields = ("say", "do", "want")
    for field_name in nullable_fields:
        non_nullable["properties"][field_name] = {
            "type": "string",
            "minLength": 1,
        }
    converted = convert_to_gemini_schema(
        non_nullable,
        preserve_required=True,
        preserve_constraints=True,
    )
    converted["properties"]["affinityEvent"]["nullable"] = True
    for field_name in nullable_fields:
        converted["properties"][field_name]["nullable"] = True
    return converted


def profile_openai_response_format() -> Dict[str, Any]:
    response_schema = copy.deepcopy(STRUCTURED_PROFILE_SCHEMA)
    _remove_array_limits(response_schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "npc_profile_seed_t107",
            "strict": True,
            "schema": response_schema,
        },
    }


def profile_gemini_response_schema() -> Dict[str, Any]:
    from model_config import convert_to_gemini_schema

    response_schema = copy.deepcopy(STRUCTURED_PROFILE_SCHEMA)
    _remove_array_limits(response_schema)
    return convert_to_gemini_schema(
        response_schema,
        preserve_required=True,
        preserve_constraints=True,
    )


def _remove_array_limits(value: Any) -> None:
    """Relax model-output cardinality while preserving all other constraints."""
    if isinstance(value, dict):
        value.pop("maxItems", None)
        for child in value.values():
            _remove_array_limits(child)
    elif isinstance(value, list):
        for child in value:
            _remove_array_limits(child)


def profile_response_schema() -> Dict[str, Any]:
    schema = copy.deepcopy(STRUCTURED_PROFILE_SCHEMA)
    _remove_array_limits(schema)
    return schema


def _first_error(schema: Mapping[str, Any], value: Any):
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: repr(list(error.path)),
    )
    return errors[0] if errors else None


def validate_packet(packet: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(packet, dict):
        raise ThoughtContractError("packet must be an object")
    mode = packet.get("mode")
    if mode not in ("COMBAT", "OUT_OF_COMBAT"):
        raise ThoughtContractError("packet mode must be COMBAT or OUT_OF_COMBAT")
    error = _first_error(packet_schema(mode), packet)
    if error is not None:
        path = ".".join(str(part) for part in error.path) or "packet"
        raise ThoughtContractError("invalid packet at %s: %s" % (path, error.message))

    if mode == "COMBAT":
        hp = packet["context"]["status"]["hitPoints"]
        if hp["current"] > hp["maximum"]:
            raise ThoughtContractError(
                "current hit points cannot exceed maximum hit points"
            )

    npc = packet["npc"]
    relationship = packet["relationship"]
    if npc["id"] == relationship["counterpartyId"]:
        raise ThoughtContractError("focal NPC and counterparty IDs must differ")
    expected_names = {npc["name"], relationship["counterpartyName"]}
    if not expected_names.issubset(set(packet["scene"]["presentActors"])):
        raise ThoughtContractError(
            "focal NPC and counterparty must both be present actors"
        )

    evidence = packet["beat"]["relationshipEvidence"]
    if evidence is not None:
        if (
            evidence["actorId"] != relationship["counterpartyId"]
            or evidence["actor"] != relationship["counterpartyName"]
        ):
            raise ThoughtContractError(
                "relationship evidence actor must be the exact counterparty"
            )
        if evidence["targetId"] != npc["id"] or evidence["target"] != npc["name"]:
            raise ThoughtContractError(
                "relationship evidence target must be the exact focal NPC"
            )
    return copy.deepcopy(packet)


def _strip_json_fence(text: str) -> str:
    return re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )


def validate_thought_response(raw: Any, packet: Mapping[str, Any]) -> Dict[str, Any]:
    packet_copy = validate_packet(packet)
    try:
        candidate = json.loads(_strip_json_fence(raw)) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ThoughtContractError(
            "thought response is not JSON: %s" % exc.msg
        ) from exc

    error = _first_error(THOUGHT_RESPONSE_SCHEMA, candidate)
    if error is not None:
        path = ".".join(str(part) for part in error.path) or "response"
        raise ThoughtContractError(
            "invalid thought response at %s: %s" % (path, error.message)
        )

    thought = candidate["thought"].strip()
    if not thought:
        raise ThoughtContractError("thought must contain useful text")
    candidate["thought"] = thought

    # Normalize the enriched advisory fields: strip whitespace, collapse empty to
    # null. These are STRUCTURAL checks only -- we never
    # parse the prose for meaning (no verb/keyword gating); legality/mechanics are
    # the Dungeon Master's job downstream.
    for field_name in ("say", "do", "want"):
        value = candidate.get(field_name)
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                candidate[field_name] = None
            else:
                candidate[field_name] = trimmed

    event = candidate["affinityEvent"]
    evidence = packet_copy["beat"]["relationshipEvidence"]
    if event is None:
        return copy.deepcopy(candidate)
    if evidence is None:
        raise ThoughtContractError(
            "affinity event requires supplied committed relationship evidence"
        )

    npc = packet_copy["npc"]
    relationship = packet_copy["relationship"]
    if (
        event["actor"] != relationship["counterpartyName"]
        or event["target"] != npc["name"]
    ):
        raise ThoughtContractError(
            "affinity event must run from counterparty to focal NPC"
        )
    if event["actor"] != evidence["actor"] or event["target"] != evidence["target"]:
        raise ThoughtContractError("affinity event participants must match evidence")
    if event["witnessed"] is not evidence["witnessed"]:
        raise ThoughtContractError("affinity event witnessed value must match evidence")
    if (
        event["eventType"] in POSITIVE_AFFINITY_EVENT_TYPES
        and event["magnitude"] < 0
    ):
        raise ThoughtContractError("positive affinity event requires positive magnitude")
    if (
        event["eventType"] in NEGATIVE_AFFINITY_EVENT_TYPES
        and event["magnitude"] > 0
    ):
        raise ThoughtContractError("negative affinity event requires negative magnitude")
    return copy.deepcopy(candidate)
