# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""One-shot classification of storage completeness and final party actors."""

from __future__ import annotations

import json
from typing import Any, Dict

import config
import model_config
from core.ai import api_client
from utils.character_sheet_contract import extract_json_object
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import warning


register_callsite("T106", "core/ai/storage_completeness_verifier.py", 113)

_CLASSIFICATIONS = frozenset(
    {"movement_required", "declarative_only", "uncertain"}
)
_FAMILIES = frozenset({"equipment", "ammunition", "currency"})
_DIRECTIONS = frozenset({"store", "retrieve"})
_SYSTEM_PROMPT = """You are a narrow storage-intent classifier for a role-playing game.
Decide whether the natural-language storage description commits to moving named
resources now, and identify the exact supplied party character who must finally
receive or surrender each resource. The candidate may move zero resources or
may route a resource to the wrong party character. Do not invent story outcomes,
storage operations, character names, or mechanical changes.

Return JSON only with exactly:
{"classification":"movement_required|declarative_only|uncertain",
 "resources":[{"family":"equipment|ammunition|currency",
               "name":"exact resource name or denomination",
               "character":"exact supplied party character name",
               "direction":"store|retrieve",
               "quantity":positive_integer}]}

Use movement_required only when the description clearly commits to moving each
listed resource in this turn. List every named resource. Use declarative_only
for a genuine container-only claim/create/name/lock/view action. Use uncertain
for ambiguity or when the final party character cannot be selected exactly from
the supplied identities. For store, character is the party actor surrendering
the resource. For retrieve, character is its intended final party recipient.
Never derive a quantity from a measurement embedded in an item name or
description (for example, 50 feet of rope is one rope item)."""


def _provider_config(provider: str) -> Dict[str, Any]:
    """Select the config dict for one already-pinned provider snapshot."""
    if provider == "openai":
        return config.STORAGE_COMPLETENESS_T106_GPT54MINI_NONE
    if provider == "gemini":
        return config.STORAGE_COMPLETENESS_T106_GEMINI_FLASHLITE_LOW
    if provider == "lmstudio":
        return config.STORAGE_COMPLETENESS_T106_LMSTUDIO
    return config.STORAGE_COMPLETENESS_T106_LEGACY


def _uncertain(reason: str) -> Dict[str, Any]:
    return {"classification": "uncertain", "resources": [], "reason": reason}


def _normalize_contract(value: Any, party_identities) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "classification",
        "resources",
    }:
        return _uncertain("invalid response shape")
    classification = value.get("classification")
    resources = value.get("resources")
    if classification not in _CLASSIFICATIONS or not isinstance(resources, list):
        return _uncertain("invalid classification")
    if classification != "movement_required":
        if resources:
            return _uncertain("non-movement result included resources")
        return {"classification": classification, "resources": []}
    normalized = []
    for resource in resources:
        if not isinstance(resource, dict) or set(resource) != {
            "family",
            "name",
            "character",
            "direction",
            "quantity",
        }:
            return _uncertain("invalid resource shape")
        family = resource.get("family")
        name = str(resource.get("name") or "").strip()
        character = str(resource.get("character") or "").strip()
        direction = resource.get("direction")
        quantity = resource.get("quantity")
        if (
            family not in _FAMILIES
            or not name
            or character not in party_identities
            or direction not in _DIRECTIONS
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity <= 0
        ):
            return _uncertain("invalid resource fact")
        normalized.append(
            {
                "family": family,
                "name": name,
                "character": character,
                "direction": direction,
                "quantity": quantity,
            }
        )
    if not normalized:
        return _uncertain("movement result omitted resources")
    return {"classification": classification, "resources": normalized}


def classify_storage_completeness(
    description: str,
    candidate_operation: Any,
    party_identities=(),
) -> Dict[str, Any]:
    """Make at most one classify-only model call and fail closed on uncertainty."""
    packet = {
        "storage_description": str(description or ""),
        "candidate_operation": (
            candidate_operation if isinstance(candidate_operation, dict) else {}
        ),
        "party_identities": list(party_identities),
    }
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(packet, ensure_ascii=False, sort_keys=True),
        },
    ]
    try:
        # Snapshot the provider ONCE: the config dict and the transport must
        # describe the same provider even if the UI switches mid-turn.
        provider = model_config.MODEL_PROVIDER
        provider_config = _provider_config(provider)
        kwargs = {
            key: value
            for key, value in provider_config.items()
            if key != "model"
        }
        if not any(
            key in provider_config
            for key in ("reasoning_effort", "thinking_level")
        ):
            kwargs["temperature"] = 0.1
        response = capture_and_fanout(
            "T106",
            api_client.create_completion,
            _request_provider=provider,
            messages=messages,
            model=provider_config["model"],
            **kwargs,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            return _uncertain("empty classifier response")
        # Local/Custom providers force response_format off (api_client.py), so
        # the reply can arrive fenced or prose-wrapped. Extract before parsing;
        # the strict normalizer below remains the only authority gate.
        json_blob = extract_json_object(content)
        if json_blob is None:
            return _uncertain("classifier response contained no JSON object")
        return _normalize_contract(json.loads(json_blob), set(party_identities))
    except Exception as exc:
        warning(
            f"T106 storage completeness check failed closed: {exc}",
            category="storage_operations",
        )
        return _uncertain("classifier unavailable")
