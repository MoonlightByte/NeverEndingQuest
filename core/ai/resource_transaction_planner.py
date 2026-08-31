# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""T105: bounded arrangement of observed complex-resource facts."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

import config
import model_config
from core.ai import api_client
from utils.character_sheet_contract import extract_json_object
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite


register_callsite("T105", "core/ai/resource_transaction_planner.py", 78)

_SYSTEM_PROMPT = """You arrange already-observed RPG resource facts into stages.
You are NOT a storyteller and have no authority to invent, remove, or edit a
participant, asset, quantity, denomination, price, or outcome. Reference only
the exact fact_id strings supplied.

Return JSON only with exactly three keys:
{"stages":[{"stage":1,"fact_ids":["..."],"confidence":"high"}],
 "edges":[{"edge_id":"E1","source_fact_ids":["..."],
            "destination_fact_ids":["..."],"authority":"source",
            "confidence":"high"}],
 "duplicates":[{"fact_id":"...","canonical_fact_id":"..."}]}

Every supplied fact must appear exactly once either in one stage or as the
fact_id of an exact duplicate. A duplicate is allowed only when participant,
family, name, direction, and quantity are identical. Use an edge only for an
outgoing and incoming fact representing the same transferred asset between
different participants. Equipment or ammunition names may differ when the
accepted action facts unambiguously describe the same transfer; in that case,
the outgoing source fact is the persisted canonical identity. Never match
different names from similarity alone. Each edge has exactly one source and
one destination.
Facts marked as operations preserve ordered custody that may disappear from a
participant's net final. If a fact supplies requires_fact_ids, put every named
dependency in an earlier stage; never collapse or reorder that handoff. This
lets code rehearse each supplied step before it calculates final images.
Authority identifies which observed side expresses the intended transfer
amount most directly; do no arithmetic. Use sequential stage numbers from 1.
Use confidence high only when the classification follows directly from the
supplied facts; otherwise use uncertain so the transaction fails safely."""


def _provider_config(provider: str) -> Dict[str, Any]:
    """Select the config dict for one already-pinned provider snapshot."""
    if provider == "openai":
        return config.RESOURCE_PLAN_T105_GPT54MINI_LOW
    if provider == "gemini":
        return config.RESOURCE_PLAN_T105_GEMINI_FLASH_LOW
    if provider == "lmstudio":
        return config.RESOURCE_PLAN_T105_LMSTUDIO
    return config.RESOURCE_PLAN_T105_LEGACY


def request_transaction_plan(
    packet: Mapping[str, Any],
    *,
    correction: Optional[str] = None,
) -> Mapping[str, Any]:
    """Make exactly one provider call; the caller owns the two-call ceiling."""
    payload = {"transaction": packet}
    if correction:
        payload["previous_validation_error"] = str(correction)[:1000]
    # Snapshot the provider ONCE: the config dict and the transport must
    # describe the same provider even if the UI switches mid-turn.
    provider = model_config.get_provider()
    provider_config = _provider_config(provider)
    request_options = {
        key: value for key, value in provider_config.items() if key != "model"
    }
    if str(request_options.get("reasoning_effort") or "none").lower() == "none":
        request_options["temperature"] = 0.1
    response = capture_and_fanout(
        "T105", api_client.create_completion,
        _request_provider=provider,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        ],
        model=provider_config["model"],
        **request_options,
    )
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("T105 returned an empty response")
    json_blob = extract_json_object(content)
    if json_blob is None:
        raise ValueError("T105 response contained no complete JSON object")

    def reject_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("T105 response contained a duplicate JSON key")
            value[key] = item
        return value

    value = json.loads(json_blob, object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError("T105 returned a non-object response")
    return value
