# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Creative story-outline stage for the gold story-first path."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Tuple

from ..contracts import AcceptedOutline, StorySeed, outline_schema
from ..execution import CompletionGateway, execute_structured_stage
from ..settings import STAGE_POLICIES, StagePolicy
from ..validators import semantic_outline_checks


TASK_ID = "T098"
SCHEMA_NAME = "story_first_outline"


def prompts(
    seed: StorySeed,
    blocklist: Iterable[str],
) -> Tuple[str, str]:
    avoid = ", ".join(blocklist)
    system = f"""You are the lead adventure designer for a persistent fantasy role-playing game.
Author the high-level story before maps and runtime files. Preserve the player's concept and
mandatory facts. You control the story shape, opposition, revelations, consequences, side
threads, and crescendo; do not force a stock act count, boss fight, or dungeon template.
Every beat must use a declared areaRoleId, name only real prerequisite beat IDs, and remain
reachable. The first beat is the entry beat and must have no prerequisites. Set
optionalTerminal true only for an intentional side branch that may end without unlocking a
later beat; otherwise set it false. Give every side thread one anchorBeatId naming the real
accepted beat where that thread becomes available; choose it for story coherence, not merely
by array position. Creature briefs may describe standard creatures or
original creatures when they serve the specific story. Do not classify creature provenance;
every referenced creature is authored later during the creature-build stage. Include each
creature the locations may use as a singular reference identity, never a quantity; do not add
creatures merely to populate locations. Create only story-essential creature identities and
consider the requested location count. Reuse a coherent creature across appropriate scenes
instead of inventing a new monster for each location. A mixed ten-location module ordinarily
needs a sparse roster unless the concept makes distinct creatures central; a creature-focused
seed may legitimately need more, and a social seed may need none. Choose each targetCR by
considering levelMin, levelMax, likely party composition, and the creature's narrative role
together. A climactic creature may be stronger only when the module clearly provides
telegraphing, avoidance, negotiation, environmental leverage, allies, or scaling instructions.
Do not assume every named threat is a solo boss, and do not use a hardcoded party-size formula.
Give every canonical significant actor a distinct full name; ordinary titles, family names,
unnamed roles, and deliberate aliases are not new canonical identities. The frozen runtime
monster format cannot represent swim speed, tremorsense, or vibration sensing. Water themes
remain welcome, but no creature's declared story role may mechanically depend on operating
submerged or locating targets through those unsupported senses; redesign such a role while
preserving its story purpose. Use ASCII canonical text. Avoid
these overused priors unless the seed explicitly contains them:
{avoid}. Return only JSON matching the response contract."""
    seed_value = seed.to_prompt_value()
    user = (
        "IMMUTABLE PLAYER SEED:\n"
        + json.dumps(seed_value, indent=2)
        + (
            f"\nUse exactly {seed_value['moduleControls']['numAreas']} abstract area roles. "
            "Choose the number of beats the specific story needs."
        )
    )
    return system, user


def run(
    *,
    seed: StorySeed,
    blocklist: Iterable[str],
    provider: str,
    model: str,
    model_options: Mapping[str, Any],
    gateway: CompletionGateway,
    policy: StagePolicy = STAGE_POLICIES["outline"],
) -> AcceptedOutline:
    """Return an accepted immutable outline; this function performs no writes."""
    blocked_terms = tuple(blocklist)
    system_prompt, user_prompt = prompts(seed, blocked_terms)
    schema = outline_schema()
    result = execute_structured_stage(
        stage="outline",
        task_id=TASK_ID,
        schema_name=SCHEMA_NAME,
        provider=provider,
        model=model,
        model_options=model_options,
        temperature=policy.temperature,
        schema=schema,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_attempts=policy.max_attempts,
        semantic_gate=lambda value: semantic_outline_checks(
            value,
            seed.to_prompt_value(),
            blocked_terms,
        ),
        gateway=gateway,
    )
    return AcceptedOutline(
        value=result.value, evidence=result.evidence, metrics=result.metrics
    )
