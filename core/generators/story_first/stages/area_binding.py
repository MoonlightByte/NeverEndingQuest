# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Accepted-outline to story-purposeful location-role binding."""

from __future__ import annotations

import json
from typing import Any, Mapping, Tuple

from ..compilers import compile_area_binding, compile_redundant_binding_mechanics
from ..contracts import (
    AcceptedAreaBinding,
    AcceptedOutline,
    CompiledWorld,
    StorySeed,
    area_binding_schema,
    mutable_copy,
)
from ..execution import CompletionGateway, execute_structured_stage
from ..settings import STAGE_POLICIES, StagePolicy
from ..validators import semantic_area_binding_checks, validate_compiled_world


TASK_ID = "T099"
SCHEMA_NAME = "story_first_area_binding"


def prompts(seed: StorySeed, outline: AcceptedOutline) -> Tuple[str, str]:
    system = """Translate the accepted story outline into story-purposeful areas and location
roles. Preserve its facts and canonical actors. Every place must have a distinct story use.
Within each area, roleKey connections must be reciprocal, fully reachable, and drawable on a
two-dimensional orthogonal grid: every declared passage joins adjacent cells and adjacent
cells never imply an undeclared passage. Prefer simple paths, turns, branches, and small
cycles; no room may have more than four local connections. Declare one
cross-area passage per connected area pair. Bind every beat and give every beat one canonical
anchor. Anchor successive required main-path beats in the same location or connected locations
when that makes story sense. When an important non-adjacent hop is needed, make the intervening
travel or time change explicit in the authored transition. This is pacing guidance, not a
prohibition: the atlas and runtime travel systems remain authoritative, and the story need not
become a linear corridor. Preserve each accepted area's dangerBand exactly as dangerLevel.
Match the physical scale of each anchor role to its beat: a citywide, village-wide, army,
evacuation, or mass battle scene cannot be anchored to a closet, cell, alcove, or private
one-room shack. Use an explicit public, open, or complex space for a large scene. Use ASCII
text and return only JSON matching the response contract."""
    user = (
        "IMMUTABLE SEED:\n"
        + json.dumps(seed.to_prompt_value(), indent=2)
        + "\nACCEPTED OUTLINE:\n"
        + json.dumps(mutable_copy(outline.value), indent=2)
    )
    return system, user


def run(
    *,
    seed: StorySeed,
    outline: AcceptedOutline,
    map_schema: Mapping[str, Any],
    provider: str,
    model: str,
    model_options: Mapping[str, Any],
    gateway: CompletionGateway,
    policy: StagePolicy = STAGE_POLICIES["area_binding"],
) -> Tuple[AcceptedAreaBinding, CompiledWorld]:
    """Accept one binding and deterministically compile trusted runtime IDs/maps."""
    seed_value = seed.to_prompt_value()
    if not 1 <= seed_value["moduleControls"]["numAreas"] <= 26:
        raise ValueError("story-first area count must be between 1 and 26")
    outline_value = mutable_copy(outline.value)
    system_prompt, user_prompt = prompts(seed, outline)
    semantic_attempt = 0
    accepted_binding = None

    def gate(value):
        nonlocal semantic_attempt, accepted_binding
        semantic_attempt += 1
        candidate = mutable_copy(value)
        compile_metrics = {
            "deterministicAnchorBeatClaimAdditions": 0,
            "deterministicExactPassageDuplicatesCollapsed": 0,
        }
        if semantic_attempt > 1:
            candidate, compile_metrics = compile_redundant_binding_mechanics(candidate)
        metrics = semantic_area_binding_checks(candidate, seed_value, outline_value)
        accepted_binding = candidate
        return {**metrics, **compile_metrics}

    result = execute_structured_stage(
        stage="area_binding",
        task_id=TASK_ID,
        schema_name=SCHEMA_NAME,
        provider=provider,
        model=model,
        model_options=model_options,
        temperature=policy.temperature,
        schema=area_binding_schema(seed_value, outline_value),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_attempts=policy.max_attempts,
        semantic_gate=gate,
        gateway=gateway,
    )
    if accepted_binding is None:
        raise RuntimeError("accepted area binding was not retained")
    binding_value = accepted_binding
    areas, maps, beat_locations = compile_area_binding(binding_value)
    compiled_metrics = validate_compiled_world(
        areas, maps, beat_locations, mutable_copy(map_schema)
    )
    accepted = AcceptedAreaBinding(
        value=binding_value,
        evidence=result.evidence,
        metrics={**mutable_copy(result.metrics), **compiled_metrics},
    )
    return accepted, CompiledWorld(
        areas=tuple(areas), maps=tuple(maps), beat_locations=beat_locations
    )
