# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Combat Narration Consistency Precheck
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Bounded deterministic prechecks for explicit combat narration contradictions and
enemy-routing boundary violations.
"""

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple


_ATTACK_OUTCOME_PATTERN = re.compile(
    r"(?P<attacker>[A-Za-z0-9_][A-Za-z0-9_ '\-]*) attacks "
    r"(?P<target>[A-Za-z0-9_][A-Za-z0-9_ '\-]*?)"
    r"(?: with [A-Za-z0-9_ '\-]+)?"
    r" \(Attack roll: (?P<roll>-?\d+)\+(?P<bonus>-?\d+)=(?P<total>-?\d+), "
    r"(?P<outcome>hits|misses) (?P<target_repeat>[A-Za-z0-9_][A-Za-z0-9_ '\-]*?) AC (?P<ac>\d+)",
    re.IGNORECASE,
)

_MISS_AS_HIT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"bone splinters",
        r"bites deep",
        r"cuts into",
        r"strikes true",
        r"draws blood",
        r"slams into",
        r"drives deep",
        r"finds its mark",
        r"lands solidly",
        r"wet crunch",
        r"cleav(?:e|ing) .*deep",
        r"buries .*in",
    )
]

_HIT_AS_MISS_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"shatter(?:s|ing) against the wall",
        r"strikes only the wall",
        r"thud(?:s)? into the wall",
        r"goes wide",
        r"misses entirely",
        r"harmlessly past",
        r"flies past",
        r"whistles past",
        r"into the stone wall",
        r"against the wall near",
        r"near [A-Za-z0-9_ '\-]+ head",
        r"buries itself in the wall",
    )
]

_EXPLICIT_STATE_MUTATION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"HP\s*-?\d+\s*->\s*-?\d+",
        r"takes\s+\d+",
        r"deals\s+\d+[^.]{0,80}to",
        r"heals?\s+\d+",
        r"condition",
        r"now dead",
        r"now unconscious",
        r"expended\s+\d+\s+(?:arrow|bolt)",
        r"remove\s+\d+\s+(?:arrow|bolt)",
    )
]


def _normalize_name(value: Any) -> str:
    """Normalize a combatant name for bounded matching."""
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _build_ac_map(encounter_data: Dict[str, Any]) -> Dict[str, int]:
    """Build authoritative AC lookup from encounter data."""
    ac_map: Dict[str, int] = {}
    creatures = encounter_data.get("creatures", [])
    if not isinstance(creatures, list):
        return ac_map

    for creature in creatures:
        if not isinstance(creature, dict):
            continue
        normalized_name = _normalize_name(creature.get("name", ""))
        if not normalized_name:
            continue
        armor_class = creature.get("armorClass")
        try:
            ac_map[normalized_name] = int(armor_class)
        except (TypeError, ValueError):
            continue
    return ac_map


def _collect_text_surfaces(response_json: Dict[str, Any]) -> List[str]:
    """Collect bounded text surfaces that can contain attack math mirrors."""
    surfaces: List[str] = []
    for key in ("plan", "narration"):
        value = response_json.get(key)
        if isinstance(value, str) and value.strip():
            surfaces.append(value)

    actions = response_json.get("actions", [])
    if isinstance(actions, list):
        for action in actions:
            if not isinstance(action, dict):
                continue
            params = action.get("parameters", {})
            if not isinstance(params, dict):
                continue
            changes = params.get("changes")
            if isinstance(changes, str) and changes.strip():
                surfaces.append(changes)

    return surfaces


def _extract_attack_outcomes(
    response_json: Dict[str, Any],
    encounter_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Extract explicit attack outcomes only when AC matches authoritative state."""
    outcomes: List[Dict[str, Any]] = []
    seen: set = set()
    ac_map = _build_ac_map(encounter_data)

    for text in _collect_text_surfaces(response_json):
        for match in _ATTACK_OUTCOME_PATTERN.finditer(text):
            attacker = str(match.group("attacker")).strip()
            target = str(match.group("target_repeat") or match.group("target")).strip()
            normalized_target = _normalize_name(target)
            if normalized_target not in ac_map:
                continue

            parsed_ac = int(match.group("ac"))
            if ac_map[normalized_target] != parsed_ac:
                continue

            total = int(match.group("total"))
            outcome = {
                "attacker": attacker,
                "target": target,
                "hit": str(match.group("outcome")).strip().lower() == "hits",
                "total": total,
                "ac": parsed_ac,
            }
            dedupe_key = (
                _normalize_name(attacker),
                normalized_target,
                outcome["hit"],
                total,
                parsed_ac,
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            outcomes.append(outcome)

    return outcomes


def _find_first_name_index(text: str, names: Sequence[str], start_index: int) -> int:
    """Return earliest occurrence of any supplied name at or after start_index."""
    best_index = -1
    for name in names:
        normalized = _normalize_name(name)
        if not normalized:
            continue
        index = text.find(normalized, start_index)
        if index == -1:
            continue
        if best_index == -1 or index < best_index:
            best_index = index
    return best_index


def _segment_contains_any(segment: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    """Return True if any bounded contradiction phrase appears in the segment."""
    for pattern in patterns:
        if pattern.search(segment):
            return True
    return False


def validate_combat_narration_consistency_precheck(
    response_json: Dict[str, Any],
    encounter_data: Dict[str, Any],
) -> Tuple[bool, str]:
    """Reject explicit hit/miss narration contradictions when math is authoritative."""
    if not isinstance(response_json, dict) or not isinstance(encounter_data, dict):
        return True, ""

    narration = response_json.get("narration")
    if not isinstance(narration, str) or not narration.strip():
        return True, ""

    attack_outcomes = _extract_attack_outcomes(response_json, encounter_data)
    if not attack_outcomes:
        return True, ""

    narration_lower = narration.lower()
    previous_end = 0

    for index, outcome in enumerate(attack_outcomes):
        current_names = [outcome.get("attacker", ""), outcome.get("target", "")]
        segment_start = _find_first_name_index(narration_lower, current_names, previous_end)
        if segment_start == -1:
            segment_start = previous_end

        segment_end = len(narration_lower)
        if index + 1 < len(attack_outcomes):
            next_outcome = attack_outcomes[index + 1]
            next_names = [next_outcome.get("attacker", ""), next_outcome.get("target", "")]
            next_start = _find_first_name_index(narration_lower, next_names, segment_start + 1)
            if next_start != -1:
                segment_end = next_start

        segment = narration_lower[segment_start:segment_end]
        previous_end = max(segment_end, previous_end)

        if outcome["hit"]:
            if _segment_contains_any(segment, _HIT_AS_MISS_PATTERNS):
                return False, (
                    "Combat narration consistency precheck failed: "
                    f"'{outcome['attacker']}' attack on '{outcome['target']}' was a confirmed hit "
                    f"({outcome['total']} vs AC {outcome['ac']}) but narration described a harmless miss."
                )
        else:
            if _segment_contains_any(segment, _MISS_AS_HIT_PATTERNS):
                return False, (
                    "Combat narration consistency precheck failed: "
                    f"'{outcome['attacker']}' attack on '{outcome['target']}' was a miss "
                    f"({outcome['total']} vs AC {outcome['ac']}) but narration described successful impact."
                )

    return True, ""


def _collect_non_enemy_names(encounter_data: Dict[str, Any]) -> List[str]:
    """Collect authoritative player and allied NPC names from the encounter."""
    names: List[str] = []
    creatures = encounter_data.get("creatures", [])
    if not isinstance(creatures, list):
        return names

    for creature in creatures:
        if not isinstance(creature, dict):
            continue
        creature_type = str(creature.get("type", "")).strip().lower()
        if creature_type == "enemy":
            continue
        name = str(creature.get("name", "")).strip()
        if name:
            names.append(name)
    return names


def _changes_text_targets_non_enemy(changes_text: str, non_enemy_names: Sequence[str]) -> Optional[str]:
    """Return the first non-enemy target that appears with explicit state mutation text."""
    lowered_changes = changes_text.lower()
    for name in non_enemy_names:
        normalized = _normalize_name(name)
        if not normalized:
            continue
        if normalized not in lowered_changes:
            continue
        if any(pattern.search(changes_text) for pattern in _EXPLICIT_STATE_MUTATION_PATTERNS):
            return name
    return None


def validate_update_encounter_enemy_boundary_precheck(
    response_json: Dict[str, Any],
    encounter_data: Dict[str, Any],
) -> Tuple[bool, str]:
    """Reject explicit updateEncounter payloads that target PC or allied NPC state."""
    if not isinstance(response_json, dict) or not isinstance(encounter_data, dict):
        return True, ""

    non_enemy_names = _collect_non_enemy_names(encounter_data)
    if not non_enemy_names:
        return True, ""

    non_enemy_lookup = {_normalize_name(name): name for name in non_enemy_names}
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return True, ""

    for action in actions:
        if not isinstance(action, dict):
            continue
        action_name = str(action.get("action", "")).strip().lower()
        if action_name != "updateencounter":
            continue

        params = action.get("parameters", {})
        if not isinstance(params, dict):
            continue

        changes_text = params.get("changes")
        if isinstance(changes_text, str) and changes_text.strip():
            offending_name = _changes_text_targets_non_enemy(changes_text, non_enemy_names)
            if offending_name:
                return False, (
                    "Combat enemy-routing precheck failed: updateEncounter prose mirror targeted "
                    f"non-enemy '{offending_name}'. Player and allied NPC state must use updateCharacterInfo."
                )

        ops_payload = params.get("ops")
        if not isinstance(ops_payload, list):
            continue

        for op_item in ops_payload:
            if not isinstance(op_item, dict):
                continue
            for key in ("creature", "target", "name", "character", "characterName"):
                reference = op_item.get(key)
                normalized_reference = _normalize_name(reference)
                if normalized_reference and normalized_reference in non_enemy_lookup:
                    return False, (
                        "Combat enemy-routing precheck failed: updateEncounter ops targeted "
                        f"non-enemy '{non_enemy_lookup[normalized_reference]}'. Player and allied NPC state must use updateCharacterInfo."
                    )

    return True, ""
