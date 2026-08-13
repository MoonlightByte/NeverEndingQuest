# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""One-shot classification of zero-resource storage operations."""

from __future__ import annotations

import json
from typing import Any, Dict

import config
import model_config
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import warning


register_callsite("T106", "core/ai/storage_completeness_verifier.py", 113)

_CLASSIFICATIONS = frozenset(
    {"movement_required", "declarative_only", "uncertain"}
)
_FAMILIES = frozenset({"equipment", "ammunition", "currency"})
_DIRECTIONS = frozenset({"store", "retrieve"})
_SYSTEM_PROMPT = """You are a narrow storage-intent classifier for a role-playing game.
The supplied candidate storage operation moves zero items, ammunition, or
currency. Decide whether the natural-language storage description nevertheless
commits to moving named resources now, or only creates/claims/names/locks/views
a container without moving resources. Do not invent story outcomes, storage
operations, or mechanical changes.

Return JSON only with exactly:
{"classification":"movement_required|declarative_only|uncertain",
 "resources":[{"family":"equipment|ammunition|currency",
               "name":"exact resource name or denomination",
               "direction":"store|retrieve",
               "quantity":positive_integer}]}

Use movement_required only when the description clearly commits to moving each
listed resource in this turn. List every named resource. Use declarative_only
for a genuine container-only claim/create/name/lock/view action. Use uncertain
for ambiguity. Never derive a quantity from a measurement embedded in an item
name or description (for example, 50 feet of rope is one rope item)."""


def _provider_config() -> Dict[str, Any]:
    provider = model_config.MODEL_PROVIDER
    if provider == "openai":
        return config.STORAGE_COMPLETENESS_T106_GPT54MINI_NONE
    if provider == "gemini":
        return config.STORAGE_COMPLETENESS_T106_GEMINI_FLASHLITE_LOW
    if provider == "lmstudio":
        return config.STORAGE_COMPLETENESS_T106_LMSTUDIO
    return config.STORAGE_COMPLETENESS_T106_LEGACY


def _uncertain(reason: str) -> Dict[str, Any]:
    return {"classification": "uncertain", "resources": [], "reason": reason}


def _normalize_contract(value: Any) -> Dict[str, Any]:
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
            "direction",
            "quantity",
        }:
            return _uncertain("invalid resource shape")
        family = resource.get("family")
        name = str(resource.get("name") or "").strip()
        direction = resource.get("direction")
        quantity = resource.get("quantity")
        if (
            family not in _FAMILIES
            or not name
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
) -> Dict[str, Any]:
    """Make at most one classify-only model call and fail closed on uncertainty."""
    packet = {
        "storage_description": str(description or ""),
        "candidate_operation": (
            candidate_operation if isinstance(candidate_operation, dict) else {}
        ),
    }
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(packet, ensure_ascii=False, sort_keys=True),
        },
    ]
    try:
        provider_config = _provider_config()
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
            _request_provider=model_config.MODEL_PROVIDER,
            messages=messages,
            model=provider_config["model"],
            **kwargs,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            return _uncertain("empty classifier response")
        return _normalize_contract(json.loads(content))
    except Exception as exc:
        warning(
            f"T106 storage completeness check failed closed: {exc}",
            category="storage_operations",
        )
        return _uncertain("classifier unavailable")
