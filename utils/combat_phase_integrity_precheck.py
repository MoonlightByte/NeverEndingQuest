# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Combat Phase Integrity Precheck
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Bounded deterministic precheck for explicit combat phase-integrity contradictions.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


_FORBIDDEN_ACTION_VERB_PATTERN = re.compile(
    r"\b(attacks?|hits?|strikes?|shoots?|casts?|uses?|moves?|charges?)\b",
    re.IGNORECASE,
)


def _extract_combined_text(response_json: Dict[str, Any]) -> str:
    """Build a combined text surface for deterministic phrase matching."""
    parts: List[str] = []
    for key in ("plan", "narration"):
        value = response_json.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)

    actions = response_json.get("actions", [])
    if isinstance(actions, list):
        for action in actions:
            if not isinstance(action, dict):
                continue
            params = action.get("parameters", {})
            if not isinstance(params, dict):
                continue
            for field in ("changes", "reason"):
                field_value = params.get(field)
                if isinstance(field_value, str) and field_value.strip():
                    parts.append(field_value)

    return "\n".join(parts)


def _contains_player_turn_prompt(text: str) -> bool:
    """Return True when text explicitly prompts for the next PC turn."""
    lowered = text.lower()
    prompts = (
        "what do you do",
        "it is your turn",
        "it's your turn",
        "your turn",
        "your move",
        "your action",
    )
    return any(prompt in lowered for prompt in prompts)


def _has_forbidden_actor_action(text: str, forbidden_actors: List[str]) -> Optional[str]:
    """Return actor name when explicit forbidden actor action is found."""
    for actor_name in forbidden_actors:
        if not isinstance(actor_name, str):
            continue
        trimmed = actor_name.strip()
        if not trimmed:
            continue
        actor_pattern = re.compile(rf"\b{re.escape(trimmed)}\b", re.IGNORECASE)
        for actor_match in actor_pattern.finditer(text):
            window_start = max(actor_match.start() - 6, 0)
            window_end = min(actor_match.end() + 64, len(text))
            window = text[window_start:window_end]
            if _FORBIDDEN_ACTION_VERB_PATTERN.search(window):
                return trimmed
    return None


def _has_exit_action(response_json: Dict[str, Any]) -> bool:
    """Return True if response actions include an exit action."""
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return False
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_name = action.get("action")
        if isinstance(action_name, str) and action_name.strip().lower() == "exit":
            return True
    return False


def _encounter_has_living_hostiles(encounter_data: Dict[str, Any]) -> Optional[bool]:
    """Return True/False when authoritative, else None for fail-open."""
    creatures = encounter_data.get("creatures")
    if not isinstance(creatures, list):
        return None

    has_enemy = False
    for creature in creatures:
        if not isinstance(creature, dict):
            continue
        if str(creature.get("type", "")).lower() != "enemy":
            continue

        has_enemy = True
        status = str(creature.get("status", "alive")).strip().lower()
        current_hp = creature.get("currentHitPoints", creature.get("hitPoints"))
        try:
            hp_value = int(current_hp)
        except (TypeError, ValueError):
            # Fail-open when HP cannot be interpreted deterministically.
            return None

        if hp_value > 0 and status not in ("dead", "defeated", "unconscious"):
            return True

    if not has_enemy:
        return False
    return False


def validate_combat_phase_integrity_precheck(
    response_json: Dict[str, Any],
    encounter_data: Dict[str, Any],
    phase_state: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """Validate explicit combat phase-integrity contradictions.

    This precheck is intentionally bounded and fail-open on ambiguity.
    """
    if not isinstance(response_json, dict):
        return True, ""
    if not isinstance(encounter_data, dict):
        return True, ""
    if phase_state is None:
        phase_state = {}
    if not isinstance(phase_state, dict):
        return True, ""

    combined_text = _extract_combined_text(response_json)

    # Guard 1: Forbidden phase actor actions.
    forbidden_actors = phase_state.get("forbidden_actors")
    if isinstance(forbidden_actors, list) and forbidden_actors:
        offending_actor = _has_forbidden_actor_action(combined_text, forbidden_actors)
        if offending_actor:
            return False, (
                "Combat phase integrity precheck failed: "
                f"forbidden actor '{offending_actor}' attempted an explicit action in current phase."
            )

    # Guard 2: Mid-enemy-batch stop.
    current_phase = phase_state.get("current_phase")
    pending_enemies = phase_state.get("pending_enemies")
    if (
        isinstance(current_phase, str)
        and current_phase.strip().upper() == "ENEMY_PHASE"
        and isinstance(pending_enemies, list)
        and len(pending_enemies) > 0
        and _contains_player_turn_prompt(combined_text)
    ):
        return False, (
            "Combat phase integrity precheck failed: response stopped or prompted during ENEMY_PHASE "
            "before enemy batch completion."
        )

    # Guard 3: Illegal exit while hostiles remain.
    if _has_exit_action(response_json):
        has_living_hostiles = _encounter_has_living_hostiles(encounter_data)
        if has_living_hostiles is True:
            return False, (
                "Combat phase integrity precheck failed: exit action requested while living hostiles remain."
            )

    # Guard 4: Illegal round increment before all PCs acted.
    ai_round = response_json.get("combat_round")
    current_round = phase_state.get("current_round")
    pc_phase_complete = phase_state.get("pc_phase_complete")
    if (
        isinstance(ai_round, int)
        and isinstance(current_round, int)
        and isinstance(pc_phase_complete, bool)
        and ai_round > current_round
        and pc_phase_complete is False
    ):
        return False, (
            "Combat phase integrity precheck failed: combat_round advanced before all required PCs acted."
        )

    return True, ""
