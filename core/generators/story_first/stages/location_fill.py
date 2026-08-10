# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Narrow story-first adapter around the unchanged T026 location generator."""

from __future__ import annotations

import copy
import json
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

import jsonschema

from ..contracts import (
    AcceptedAreas,
    AcceptedOutline,
    AcceptedPlot,
    CompiledWorld,
    StageEvidence,
    StorySeed,
    mutable_copy,
)
from ..compilers import normalize_ascii_typography, project_side_threads_to_locations
from ..validators import (
    validate_side_thread_location_projection,
    validate_story_first_location_result,
)
from .plot_derivation import trusted_mappings


TASK_ID = "T026"


def context_header(
    outline: AcceptedOutline,
    area: Mapping[str, Any],
    beat_to_plot: Mapping[str, str],
) -> str:
    """Return the authoritative accepted-story slice prepended to T026."""
    assigned = {
        beat for location in area["locations"] for beat in location.get("beatIds", [])
    }
    beats = [
        beat
        for beat in outline.value["beats"]
        if beat["areaRoleId"] == area["areaId"] or beat["id"] in assigned
    ]
    story_slice = {
        "storyPromise": outline.value["storyPromise"],
        "truthLog": mutable_copy(outline.value["truthLog"]),
        "opposition": mutable_copy(outline.value["opposition"]),
        "area": mutable_copy(
            next(
                item
                for item in outline.value["areas"]
                if item["roleId"] == area["areaId"]
            )
        ),
        "beats": mutable_copy(beats),
        "plotPointIdsByBeat": {beat["id"]: beat_to_plot[beat["id"]] for beat in beats},
        "sideThreads": mutable_copy(outline.value["sideThreads"]),
        "creatureBriefs": mutable_copy(outline.value["creatureBriefs"]),
    }
    return (
        "ACCEPTED STORY OUTLINE SLICE - authoritative creative context. Preserve every "
        "trusted stub field. areaConnectivityId values are destination LOCATION IDs. "
        "For a new module, encounters and adventureSummary must be empty and "
        "explorationState must be unvisited; put possible future scenes in "
        "dmInstructions and other authored guidance. CREATURE ALLOWLIST: entries "
        "in monsters may use ONLY the exact singular names listed in "
        "creatureBriefs below. If creatureBriefs is empty, monsters must be []. "
        "Do not invent SRD, common, plural, or filler monster entries; express "
        "other hazards through traps, features, or descriptive guidance. Do not "
        "reuse any canonical significant actor's given name for a newly introduced "
        "NPC unless the identity is intentionally the same and represented once. "
        "Ordinary titles, family names, unnamed roles, and deliberate aliases may "
        "still be used when they remain clear. When a side thread's playable hook "
        "depends on a named person at its canonical host, place that person in the "
        "host location's existing NPC roster and supporting prose. When the hook "
        "does not depend on a named person, do not invent one merely to satisfy this "
        "instruction. For every locked door with a key, passphrase, riddle answer, "
        "cycle tag, or ritual phrase, write keyname as an explicit literal using "
        "exactly one of these forms: Key: <literal>, Passphrase: <literal>, Answer: "
        "<literal>, Cycle tag: <literal>, or Ritual phrase: <literal>. Put that "
        "exact literal in public location content at the same location or a location "
        "reachable no later from the module entry. Do not use placeholders such as "
        "correct, matching, current, or active. Public output must never repeat "
        "private Bxxx beat or Sxxx side-thread IDs from the accepted slice; use a "
        "supplied PPxxx runtime ID only when an ID is necessary, and do not invent "
        "PPxxx or SQxxx IDs. Canonical SQxxx hooks are installed by code.\n"
        + json.dumps(story_slice, indent=2, ensure_ascii=True)
        + "\n\n"
    )


def run(
    *,
    seed: StorySeed,
    outline: AcceptedOutline,
    world: CompiledWorld,
    plot: AcceptedPlot,
    provider: str,
    loca_schema: Mapping[str, Any],
    locationfile_schema: Mapping[str, Any],
    blocklist: Iterable[str],
    generate_batch: Optional[Callable[..., Dict[str, Any]]] = None,
) -> AcceptedAreas:
    """Fill each trusted area stub through T026, without changing T026 mechanics."""
    from model_config import get_provider

    if get_provider() != provider:
        raise ValueError("T026 provider snapshot differs from active provider")
    if generate_batch is None:
        from core.generators.location_generator import LocationGenerator

        generate_batch = LocationGenerator().generate_location_batch

    seed_value = seed.to_prompt_value()
    outline_value = mutable_copy(outline.value)
    plot_value = mutable_copy(plot.value)
    beat_to_plot, thread_to_quest = trusted_mappings(outline)
    module = {
        "moduleName": outline.value["moduleTitle"],
        "moduleDescription": outline.value["conceptSummary"],
        "worldSettings": {
            "era": seed.module_controls.get("era", "fantasy"),
            "magicPrevalence": seed.module_controls.get(
                "magicPrevalence", "setting appropriate"
            ),
        },
    }
    generated_areas = []
    evidence = []
    metrics = []
    for frozen_area in world.areas:
        if get_provider() != provider:
            raise ValueError("T026 provider snapshot changed during location fill")
        area = mutable_copy(frozen_area)
        result = generate_batch(
            area_data=area,
            plot_data=plot_value,
            module_data=module,
            location_stubs=copy.deepcopy(area["locations"]),
            excluded_names=list(seed.campaign_context.get("partyNames", ())),
            context_header=context_header(outline, frozen_area, beat_to_plot),
        )
        result, typography_replacements = normalize_ascii_typography(result)
        jsonschema.validate(result, mutable_copy(loca_schema))
        area_metrics = validate_story_first_location_result(
            result, area, outline_value, seed_value, blocklist
        )
        wrapper = copy.deepcopy(area)
        wrapper["locations"] = copy.deepcopy(result["locations"])
        jsonschema.validate(wrapper, mutable_copy(locationfile_schema))
        generated_areas.append(wrapper)
        evidence.append(
            StageEvidence(
                stage=f"location_fill:{area['areaId']}",
                attempts=1,
                result="accepted",
            )
        )
        metrics.append(
            {
                "areaId": area["areaId"],
                **area_metrics,
                "deterministicAsciiTypographyReplacements": typography_replacements,
            }
        )
    generated_areas = project_side_threads_to_locations(
        generated_areas,
        outline_value,
        mutable_copy(world.beat_locations),
        thread_to_quest,
    )
    for area in generated_areas:
        jsonschema.validate({"locations": area["locations"]}, mutable_copy(loca_schema))
        jsonschema.validate(area, mutable_copy(locationfile_schema))
    projection_metrics = validate_side_thread_location_projection(
        generated_areas,
        plot_value,
        outline_value,
        mutable_copy(world.beat_locations),
        thread_to_quest,
    )
    return AcceptedAreas(
        areas=tuple(generated_areas),
        evidence=tuple(evidence),
        metrics={
            "areaCount": len(generated_areas),
            "locationCount": sum(item["locationCount"] for item in metrics),
            **projection_metrics,
            "areas": metrics,
        },
    )
