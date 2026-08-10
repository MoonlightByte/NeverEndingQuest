# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Accepted outline/world to frozen runtime plot derivation."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Tuple

import jsonschema

from ..compilers import (
    compile_plot_skeleton as _compile_plot_skeleton,
    merge_plot_narrative,
)
from ..contracts import (
    AcceptedOutline,
    AcceptedPlot,
    CompiledWorld,
    StorySeed,
    mutable_copy,
)
from ..execution import CompletionGateway, execute_structured_stage
from ..settings import STAGE_POLICIES, StagePolicy
from ..validators import semantic_plot_checks


TASK_ID = "T100"
SCHEMA_NAME = "story_first_plot_narrative"


def trusted_mappings(
    outline: AcceptedOutline,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    beats = {
        beat["id"]: f"PP{index:03d}"
        for index, beat in enumerate(outline.value["beats"], 1)
    }
    threads = {
        thread["id"]: f"SQ{index:03d}"
        for index, thread in enumerate(outline.value["sideThreads"], 1)
    }
    return beats, threads


def plot_narrative_schema(outline: AcceptedOutline) -> Dict[str, Any]:
    """Return the strict provider contract containing authored prose slots only."""
    narrative = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "description": {"type": "string", "minLength": 1},
            "plotImpact": {"type": "string", "maxLength": 0},
        },
        "required": ["title", "description", "plotImpact"],
    }
    beat_count = len(outline.value["beats"])
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "plotTitle": {"type": "string", "minLength": 1},
            "mainObjective": {"type": "string", "minLength": 1},
            "plotPoints": {
                "type": "array",
                "minItems": beat_count,
                "maxItems": beat_count,
                "items": mutable_copy(narrative),
            },
        },
        "required": ["plotTitle", "mainObjective", "plotPoints"],
    }


def compile_plot_skeleton(
    outline: AcceptedOutline, world: CompiledWorld
) -> Dict[str, Any]:
    """Compile the runtime structure while keeping authored slots empty."""
    beat_to_plot, thread_to_quest = trusted_mappings(outline)
    return _compile_plot_skeleton(
        mutable_copy(outline.value),
        mutable_copy(world.beat_locations),
        beat_to_plot,
        thread_to_quest,
    )


def prompts(
    seed: StorySeed,
    outline: AcceptedOutline,
    world: CompiledWorld,
    beat_to_plot: Mapping[str, str],
) -> Tuple[str, str]:
    point_slots = [
        {
            "slot": index,
            "plotPointId": beat_to_plot[beat["id"]],
            "locationId": world.beat_locations[beat["id"]],
            "acceptedBeat": mutable_copy(beat),
        }
        for index, beat in enumerate(outline.value["beats"], 1)
    ]
    system = """Author only the plot-point narrative text for a runtime plot whose mechanics
and side quests are compiled by code from the accepted outline. Preserve the accepted story.
Return plot-point narratives in the exact supplied slot order. Do not return IDs, locations,
graph edges, statuses, scopes, side quests, or nested arrays; those fields are not in the
response contract. Every plotImpact is an empty string because this is a new game. Use ASCII
and return only JSON matching the narrative response contract."""
    user = (
        "SEED:\n"
        + json.dumps(seed.to_prompt_value(), indent=2)
        + "\nOUTLINE:\n"
        + json.dumps(mutable_copy(outline.value), indent=2)
        + "\nPLOT NARRATIVE SLOTS (same output order):\n"
        + json.dumps(point_slots, indent=2)
    )
    return system, user


def run(
    *,
    seed: StorySeed,
    outline: AcceptedOutline,
    world: CompiledWorld,
    production_schema: Mapping[str, Any],
    provider: str,
    model: str,
    model_options: Mapping[str, Any],
    gateway: CompletionGateway,
    policy: StagePolicy = STAGE_POLICIES["plot_derivation"],
) -> AcceptedPlot:
    """Merge authored prose into a compiled plot and validate the runtime result."""
    beat_to_plot, thread_to_quest = trusted_mappings(outline)
    skeleton = compile_plot_skeleton(outline, world)
    narrative_schema = plot_narrative_schema(outline)
    system_prompt, user_prompt = prompts(seed, outline, world, beat_to_plot)
    outline_value = mutable_copy(outline.value)
    areas = mutable_copy(world.areas)
    beat_locations = mutable_copy(world.beat_locations)
    accepted_plot = None

    def gate(narrative):
        nonlocal accepted_plot
        candidate = merge_plot_narrative(skeleton, narrative)
        jsonschema.validate(candidate, mutable_copy(production_schema))
        metrics = semantic_plot_checks(
            candidate,
            outline_value,
            areas,
            beat_locations,
            beat_to_plot,
            thread_to_quest,
        )
        accepted_plot = candidate
        return {
            **metrics,
            "deterministicPlotPointCount": len(candidate["plotPoints"]),
            "deterministicSideQuestCount": sum(
                len(point["sideQuests"]) for point in candidate["plotPoints"]
            ),
        }

    result = execute_structured_stage(
        stage="plot_derivation",
        task_id=TASK_ID,
        schema_name=SCHEMA_NAME,
        provider=provider,
        model=model,
        model_options=model_options,
        temperature=policy.temperature,
        schema=narrative_schema,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_attempts=policy.max_attempts,
        semantic_gate=gate,
        gateway=gateway,
    )
    if accepted_plot is None:
        raise RuntimeError("accepted plot merge was not retained")
    return AcceptedPlot(
        value=accepted_plot, evidence=result.evidence, metrics=result.metrics
    )
