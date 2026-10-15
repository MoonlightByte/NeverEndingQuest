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


def _render_hardening(repair):
    """Write the typed guards and level guidance into the DM text the runtime reads."""
    text = repair["dmInstructions"].rstrip()
    for guard in repair["sameEntityGuards"]:
        text += (
            f"\n\nSAME ENTITY: {guard['name']} has both an NPC record and a creature "
            "record here; they are one entity, so never instantiate both. Switch "
            f"representations when: {guard['switchWhen']}"
        )
    entries = sorted(repair["levelGuidance"], key=lambda entry: entry["level"])
    if entries:
        text += "\n\nLEVEL GUIDANCE:" + "".join(
            f"\nLevel {entry['level']}: {entry['guidance']}" for entry in entries
        )
    return text


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
            location_id = location["locationId"]
            if location_id in by_id:
                repair = by_id[location_id]
                guarded = sorted(guard["name"] for guard in repair["sameEntityGuards"])
                if guarded != sorted(overlaps.get(location_id, [])):
                    raise ValueError(
                        f"same-entity guards at {location_id} differ from the overlaps"
                    )
                levels = sorted(entry["level"] for entry in repair["levelGuidance"])
                expected = (
                    list(range(level_min, level_max + 1))
                    if location_id == climax_id
                    else []
                )
                if levels != expected:
                    raise ValueError(
                        f"level guidance at {location_id} must cover exactly {expected}"
                    )
                location["dmInstructions"] = preserve_potential_scene_guidance(
                    location["dmInstructions"],
                    _render_hardening(repair),
                )
            if location.get("encounters") != []:
                raise ValueError("new module contains encounter history")
    climax = next(
        location
        for area in result
        for location in area["locations"]
        if location["locationId"] == climax_id
    )
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
    level_min = seed.module_controls["levelMin"]
    level_max = seed.module_controls["levelMax"]
    production_contract = hardening_schema(
        target_ids,
        mutable_copy(loca_schema),
        [name for names in overlaps.values() for name in names],
        level_min,
        level_max,
    )
    contract = strict_internal_contract(production_contract)
    affected = [
        location
        for area in migrated
        for location in area["locations"]
        if location["locationId"] in target_ids
    ]
    system = """Correct only DM guidance. At any listed social-NPC/combat-template overlap,
the two records are the same entity: give one sameEntityGuards entry per overlapping name, with
switchWhen saying when to switch representations; code writes the never-instantiate-both rule
from it. At the climax, give one levelGuidance entry per level in the seed's actual level range
with useful level-specific roster choices. Other locations use empty sameEntityGuards and
levelGuidance lists. Preserve story facts and possible-scene guidance. Do not claim scenes
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
