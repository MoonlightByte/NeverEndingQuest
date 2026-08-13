# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""T108: bounded classification of an agreed external resource exchange."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

import config
import model_config
from core.ai import api_client
from utils.character_sheet_contract import extract_json_object
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite


register_callsite("T108", "core/ai/resource_commerce_classifier.py", 92)

_SYSTEM_PROMPT = """You classify an already-narrated RPG resource exchange.
You do not decide whether an NPC accepts, invent an item, calculate value, or
edit game state. Use only exact participant IDs, resource names, quantities,
directions, and final destination IDs supplied in the packet.

Return JSON only with exactly:
{"classification":"complete|not_agreed|uncertain",
 "external_actor":"short label or null",
 "transfers":[{"direction":"external_to_party|party_to_external",
   "participant_id":"exact supplied persistent participant ID",
   "family":"equipment|ammunition|currency","name":"exact supplied name",
   "quantity":1,"final_destination_id":"exact supplied ID or null"}]}

Use complete only when the accepted action facts and player intent establish
every external leg. Use not_agreed when the scene does not complete an
exchange. Use uncertain when any actor, direction, resource, quantity, or
destination is ambiguous. Never calculate change or convert denominations."""


def _provider_config() -> Dict[str, Any]:
    provider = model_config.get_provider()
    if provider == "openai":
        return config.RESOURCE_COMMERCE_T108_GPT54MINI_LOW
    if provider == "gemini":
        return config.RESOURCE_COMMERCE_T108_GEMINI_FLASH_LOW
    if provider == "lmstudio":
        return config.RESOURCE_COMMERCE_T108_LMSTUDIO
    return config.RESOURCE_COMMERCE_T108_LEGACY


def _reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("T108 response contained a duplicate JSON key")
        value[key] = item
    return value


def request_commerce_contract(
    packet: Mapping[str, Any],
    *,
    correction: Optional[str] = None,
) -> Mapping[str, Any]:
    """Make one classify-only call; the manager owns the two-call ceiling."""
    payload = {"commerce_candidate": packet}
    if correction:
        payload["previous_validation_error"] = str(correction)[:1000]
    provider_config = _provider_config()
    options = {key: value for key, value in provider_config.items() if key != "model"}
    if str(options.get("reasoning_effort") or "none").lower() == "none":
        options["temperature"] = 0.1
    response = capture_and_fanout(
        "T108",
        api_client.create_completion,
        _request_provider=model_config.get_provider(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        ],
        model=provider_config["model"],
        **options,
    )
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("T108 returned an empty response")
    blob = extract_json_object(content)
    if blob is None:
        raise ValueError("T108 response contained no complete JSON object")
    value = json.loads(blob, object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(value, dict):
        raise ValueError("T108 returned a non-object response")
    return value
