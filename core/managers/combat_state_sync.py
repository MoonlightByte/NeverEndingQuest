# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Combat State Sync - Phase and Roster Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import random
from typing import Any, Dict, Tuple

from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, warning


def _normalize_name(name: Any) -> str:
    """Normalize combatant names for case-insensitive roster matching."""
    return str(name or "").split("(")[0].strip().lower()


def apply_opening_batch_marker(encounter_data: Dict[str, Any], starts_with: str) -> bool:
    """Set additive opening enemy-batch marker from round starter and return marker state."""
    marker_enabled = str(starts_with or "").strip() == "dmGroup"
    encounter_data["openingEnemyBatchPending"] = marker_enabled
    return marker_enabled


def normalize_multi_pc_roster(
    encounter_data: Dict[str, Any],
    party_tracker_data: Dict[str, Any],
    path_manager: Any,
) -> Tuple[Dict[str, Any], bool]:
    """Backfill missing party members into encounter player roster (additive only)."""
    try:
        if not isinstance(party_tracker_data, dict):
            return encounter_data, False

        party_members = party_tracker_data.get("partyMembers", [])
        if len(party_members) <= 1:
            return encounter_data, False

        creatures = encounter_data.get("creatures", [])
        existing_players = {
            _normalize_name(creature.get("name", ""))
            for creature in creatures
            if creature.get("type") == "player"
        }

        roster_changed = False
        for member in party_members:
            member_name = member.get("name", "") if isinstance(member, dict) else str(member)
            normalized_member = _normalize_name(member_name)
            if not normalized_member or normalized_member in existing_players:
                continue

            char_file = path_manager.get_character_path(member_name)
            char_data = safe_json_load(char_file)
            if not char_data:
                warning(
                    f"ROSTER_BACKFILL: Missing character data for '{member_name}' at '{char_file}'",
                    category="combat_events",
                )
                continue

            creatures.append(
                {
                    "name": char_data.get("name", member_name),
                    "type": "player",
                    "initiative": random.randint(1, 20),
                    "status": char_data.get("status", "alive"),
                    "conditions": char_data.get("condition_affected", []),
                    "actions": {"actionType": "", "target": ""},
                    "currentHitPoints": char_data.get("hitPoints", 10),
                    "maxHitPoints": char_data.get("maxHitPoints", 10),
                    "armorClass": char_data.get("armorClass", 10),
                }
            )
            existing_players.add(normalized_member)
            roster_changed = True
            debug(
                f"ROSTER_BACKFILL: Added missing player '{member_name}' to encounter roster",
                category="combat_events",
            )

        return encounter_data, roster_changed
    except Exception as e:
        warning(f"ROSTER_BACKFILL: Fail-open due to normalization error: {e}", category="combat_events")
        return encounter_data, False
