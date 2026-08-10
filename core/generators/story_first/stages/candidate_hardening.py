# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Focused same-entity and level-scaling candidate hardening."""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, Mapping

import jsonschema

from ..compilers import (
    add_level_scaling_precedence,
    migrate_initial_encounters_to_dm_guidance,
    preserve_potential_scene_guidance,
)
from ..contracts import (
    AcceptedAreas,
    AcceptedOutline,
    AcceptedPlot,
    StorySeed,
    hardening_schema,
    mutable_copy,
    strict_internal_contract,
)
from ..execution import CompletionGateway, execute_structured_stage
from ..settings import STAGE_POLICIES, StagePolicy
from ..validators import (
    require_ascii,
    social_monster_overlaps,
    unique_values,
)
from .plot_derivation import trusted_mappings


TASK_ID = "T102"
SCHEMA_NAME = "story_first_candidate_hardening"


def _apply_hardening(
    migrated,
    repairs,
    target_ids,
    overlaps,
    climax_id,
    level_min,
    level_max,
    loca_schema,
    wrapper_schema,
):
    result = copy.deepcopy(migrated)
    by_id = {item["locationId"]: item for item in repairs}
    if set(by_id) != set(target_ids):
        raise ValueError("hardening IDs differ from targets")
    for area in result:
        for location in area["locations"]:
            if location["locationId"] in by_id:
                location["dmInstructions"] = preserve_potential_scene_guidance(
                    location["dmInstructions"],
                    by_id[location["locationId"]]["dmInstructions"],
                )
                if (
                    location["locationId"] in overlaps
                    and "never instantiate both"
                    not in location["dmInstructions"].casefold()
                ):
                    raise ValueError("same-entity guard missing")
            if location.get("encounters") != []:
                raise ValueError("new module contains encounter history")
    climax = next(
        location
        for area in result
        for location in area["locations"]
        if location["locationId"] == climax_id
    )
    text = climax["dmInstructions"].casefold()
    for level in range(level_min, level_max + 1):
        if f"level {level}" not in text:
            raise ValueError(f"climax omits level {level} guidance")
    climax["dmInstructions"] = add_level_scaling_precedence(climax["dmInstructions"])
    require_ascii(result, "hardened candidate")
    for area in result:
        jsonschema.validate({"locations": area["locations"]}, mutable_copy(loca_schema))
        jsonschema.validate(area, mutable_copy(wrapper_schema))
    return result


def run(
    *,
    seed: StorySeed,
    outline: AcceptedOutline,
    filled: AcceptedAreas,
    plot: AcceptedPlot,
    loca_schema: Mapping[str, Any],
    locationfile_schema: Mapping[str, Any],
    provider: str,
    model: str,
    model_options: Mapping[str, Any],
    gateway: CompletionGateway,
    policy: StagePolicy = STAGE_POLICIES["candidate_hardening"],
) -> AcceptedAreas:
    """Harden bounded DM guidance without changing any other location field."""
    areas = mutable_copy(filled.areas)
    migrated, moved = migrate_initial_encounters_to_dm_guidance(areas)
    overlaps = social_monster_overlaps(migrated)
    crescendo = next(
        beat["id"] for beat in outline.value["beats"] if beat["isCrescendo"]
    )
    beat_to_plot, _ = trusted_mappings(outline)
    climax_id = next(
        point["location"]
        for point in plot.value["plotPoints"]
        if point["id"] == beat_to_plot[crescendo]
    )
    target_ids = sorted(set(overlaps) | {climax_id})
    production_contract = hardening_schema(target_ids, mutable_copy(loca_schema))
    contract = strict_internal_contract(production_contract)
    affected = [
        location
        for area in migrated
        for location in area["locations"]
        if location["locationId"] in target_ids
    ]
    level_min = seed.module_controls["levelMin"]
    level_max = seed.module_controls["levelMax"]
    system = """Correct only DM guidance. At any listed social-NPC/combat-template overlap,
the two records are the same entity: explicitly say 'never instantiate both' and when to switch
representations. At the climax, give useful level-specific roster choices across the seed's
actual level range. Preserve story facts and possible-scene guidance. Do not claim scenes
occurred, change any other field, or require combat to solve noncombat paths. Return ASCII JSON."""
    user = (
        "LEVEL RANGE:\n"
        + json.dumps({"min": level_min, "max": level_max})
        + "\nOVERLAPS:\n"
        + json.dumps(overlaps, indent=2)
        + "\nAFFECTED:\n"
        + json.dumps(affected, indent=2)
    )

    def gate(value: Dict[str, Any]):
        jsonschema.validate(value, production_contract)
        ids = unique_values(value["repairs"], "locationId", "hardening IDs")
        if set(ids) != set(target_ids):
            raise ValueError("hardening IDs differ from targets")
        _apply_hardening(
            migrated,
            value["repairs"],
            target_ids,
            overlaps,
            climax_id,
            level_min,
            level_max,
            loca_schema,
            locationfile_schema,
        )
        return {
            "overlaps": overlaps,
            "migratedEncounterCount": moved,
            "targetLocationIds": target_ids,
        }

    execution = execute_structured_stage(
        stage="candidate_hardening",
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
    hardened = _apply_hardening(
        migrated,
        mutable_copy(execution.value["repairs"]),
        target_ids,
        overlaps,
        climax_id,
        level_min,
        level_max,
        loca_schema,
        locationfile_schema,
    )
    return AcceptedAreas(
        areas=tuple(hardened),
        evidence=(execution.evidence,),
        metrics=execution.metrics,
    )
