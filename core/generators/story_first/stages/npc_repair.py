# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Focused repair for duplicate static NPC placement."""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, Mapping

import jsonschema

from ..contracts import (
    AcceptedAreas,
    AcceptedOutline,
    StageEvidence,
    StorySeed,
    mutable_copy,
    npc_repair_schema,
    strict_internal_contract,
)
from ..execution import CompletionGateway, execute_structured_stage
from ..settings import STAGE_POLICIES, StagePolicy
from ..validators import (
    duplicate_npc_placements,
    require_ascii,
    unique_values,
)


TASK_ID = "T101"
SCHEMA_NAME = "story_first_npc_placement_repair"


def _apply_repairs(
    areas, repairs, target_ids, original_names, party, loca_schema, wrapper_schema
):
    result = copy.deepcopy(areas)
    by_id = {item["locationId"]: item for item in repairs}
    for area in result:
        for location in area["locations"]:
            if location["locationId"] in by_id:
                for field in ("description", "dmInstructions", "npcs"):
                    location[field] = copy.deepcopy(
                        by_id[location["locationId"]][field]
                    )
    if duplicate_npc_placements(result):
        raise ValueError("duplicate NPC placement remains")
    names = {
        npc["name"].strip().casefold()
        for area in result
        for location in area["locations"]
        for npc in location.get("npcs", [])
    }
    if names != original_names:
        raise ValueError("NPC identity set changed")
    if names & party:
        raise ValueError("party member entered NPC roster")
    require_ascii(result, "NPC repair")
    if set(by_id) != set(target_ids):
        raise ValueError("repair IDs differ from targets")
    for area in result:
        jsonschema.validate({"locations": area["locations"]}, mutable_copy(loca_schema))
        jsonschema.validate(area, mutable_copy(wrapper_schema))
    return result


def run(
    *,
    seed: StorySeed,
    outline: AcceptedOutline,
    filled: AcceptedAreas,
    loca_schema: Mapping[str, Any],
    locationfile_schema: Mapping[str, Any],
    provider: str,
    model: str,
    model_options: Mapping[str, Any],
    gateway: CompletionGateway,
    policy: StagePolicy = STAGE_POLICIES["npc_repair"],
) -> AcceptedAreas:
    """Remove duplicate placements without changing the accepted NPC identity set."""
    areas = mutable_copy(filled.areas)
    duplicates = duplicate_npc_placements(areas)
    if not duplicates:
        return AcceptedAreas(
            areas=filled.areas,
            evidence=(StageEvidence(stage="npc_repair", attempts=0, result="skipped"),),
            metrics={"skipped": True, "duplicatesBefore": {}},
        )
    target_ids = sorted({item for values in duplicates.values() for item in values})
    production_contract = npc_repair_schema(target_ids, mutable_copy(loca_schema))
    contract = strict_internal_contract(production_contract)
    affected = [
        location
        for area in areas
        for location in area["locations"]
        if location["locationId"] in target_ids
    ]
    original_names = {
        npc["name"].strip().casefold()
        for area in areas
        for location in area["locations"]
        for npc in location.get("npcs", [])
    }
    party = {
        str(name).strip().casefold()
        for name in seed.campaign_context.get("partyNames", ())
    }
    system = """Repair duplicate static placement of the same named NPC. Choose one primary
location for each person; remove them from secondary npcs arrays and add a small mobility or
schedule note to secondary prose. Do not rename, add, merge, or remove any NPC identity. Only
return description, dmInstructions, and npcs for the requested locations. Use ASCII JSON."""
    user = (
        "OUTLINE:\n"
        + json.dumps(mutable_copy(outline.value), indent=2)
        + "\nDUPLICATES:\n"
        + json.dumps(duplicates, indent=2)
        + "\nAFFECTED LOCATIONS:\n"
        + json.dumps(affected, indent=2)
        + "\nPARTY NAMES:\n"
        + json.dumps(list(seed.campaign_context.get("partyNames", ())))
    )

    def gate(value: Dict[str, Any]):
        jsonschema.validate(value, production_contract)
        ids = unique_values(value["repairs"], "locationId", "repair IDs")
        if set(ids) != set(target_ids):
            raise ValueError("repair IDs differ from targets")
        _apply_repairs(
            areas,
            value["repairs"],
            target_ids,
            original_names,
            party,
            loca_schema,
            locationfile_schema,
        )
        return {
            "duplicatesBefore": duplicates,
            "duplicatesAfter": {},
            "affectedLocationIds": target_ids,
        }

    execution = execute_structured_stage(
        stage="npc_repair",
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
    )
    repaired = _apply_repairs(
        areas,
        mutable_copy(execution.value["repairs"]),
        target_ids,
        original_names,
        party,
        loca_schema,
        locationfile_schema,
    )
    return AcceptedAreas(
        areas=tuple(repaired),
        evidence=(execution.evidence,),
        metrics=execution.metrics,
    )
