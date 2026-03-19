# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Inventory Possession Authority
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from utils.pc_manager import get_character_state


_POSSESSION_PATTERNS = [
    r"\bdo\s+i\s+still\s+have\b",
    r"\bdo\s+we\s+still\s+have\b",
    r"\bwho\s+has\b",
    r"\bwhere\s+is\b",
    r"\bmissing\b",
    r"\blost\b",
    r"\bcheck\s+my\s+pack\b",
    r"\bcheck\s+our\s+pack\b",
    r"\bcheck\s+inventory\b",
    r"\bwhat\s+do\s+i\s+have\b",
]


def _normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_possession_query_turn(user_utterance: str) -> bool:
    """Return True when the player turn explicitly queries possession truth."""
    normalized = _normalize_text(user_utterance)
    if not normalized:
        return False
    for pattern in _POSSESSION_PATTERNS:
        if re.search(pattern, normalized):
            return True
    return False


def _extract_item_names(character_data: Dict[str, Any]) -> List[str]:
    item_names: List[str] = []

    equipment = character_data.get("equipment", [])
    if isinstance(equipment, list):
        for item in equipment:
            if not isinstance(item, dict):
                continue
            item_name = str(item.get("item_name") or item.get("name") or "").strip()
            if item_name:
                item_names.append(item_name)

    ammunition = character_data.get("ammunition", [])
    if isinstance(ammunition, list):
        for ammo in ammunition:
            if not isinstance(ammo, dict):
                continue
            item_name = str(ammo.get("name") or ammo.get("item_name") or "").strip()
            if item_name:
                item_names.append(item_name)

    return item_names


def _iter_party_names(party_tracker_data: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    seen = set()

    for member_name in party_tracker_data.get("partyMembers", []):
        canonical = str(member_name or "").strip()
        normalized = _normalize_text(canonical)
        if canonical and normalized and normalized not in seen:
            seen.add(normalized)
            names.append(canonical)

    for party_npc in party_tracker_data.get("partyNPCs", []):
        if isinstance(party_npc, dict):
            npc_name = str(party_npc.get("name") or "").strip()
        else:
            npc_name = str(party_npc or "").strip()
        normalized = _normalize_text(npc_name)
        if npc_name and normalized and normalized not in seen:
            seen.add(normalized)
            names.append(npc_name)

    return names


def _build_inventory_snapshot(party_tracker_data: Dict[str, Any]) -> Dict[str, List[str]]:
    snapshot: Dict[str, List[str]] = {}
    for character_name in _iter_party_names(party_tracker_data):
        character_data = get_character_state(character_name)
        if not isinstance(character_data, dict):
            snapshot[character_name] = []
            continue
        snapshot[character_name] = _extract_item_names(character_data)
    return snapshot


def _select_target_character(user_utterance: str, party_tracker_data: Dict[str, Any]) -> str:
    party_names = _iter_party_names(party_tracker_data)
    utterance_norm = _normalize_text(user_utterance)
    for candidate in party_names:
        candidate_norm = _normalize_text(candidate)
        if candidate_norm and re.search(rf"\b{re.escape(candidate_norm)}\b", utterance_norm):
            return candidate

    active_character = str(party_tracker_data.get("active_character") or "").strip()
    if active_character:
        return active_character
    if party_names:
        return party_names[0]
    return ""


def _extract_quoted_item(user_utterance: str) -> Optional[str]:
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", str(user_utterance or ""))
    if len(quoted) == 1:
        candidate = quoted[0].strip()
        if candidate:
            return candidate
    return None


def _match_item_from_snapshot(user_utterance: str, snapshot: Dict[str, List[str]]) -> Optional[str]:
    utterance_norm = _normalize_text(user_utterance)
    if not utterance_norm:
        return None

    candidates: List[str] = []
    seen = set()
    for item_names in snapshot.values():
        for item_name in item_names:
            normalized_item = _normalize_text(item_name)
            if not normalized_item or normalized_item in seen:
                continue
            seen.add(normalized_item)

            if normalized_item in utterance_norm:
                candidates.append(item_name)
                continue

            item_tokens = [token for token in normalized_item.split() if len(token) >= 4]
            token_hits = [token for token in item_tokens if re.search(rf"\b{re.escape(token)}\b", utterance_norm)]
            if len(token_hits) >= 2:
                candidates.append(item_name)

    if len(candidates) == 1:
        return candidates[0]
    return None


def _contains_item(item_names: List[str], item_name: str) -> bool:
    target = _normalize_text(item_name)
    for existing in item_names:
        if _normalize_text(existing) == target:
            return True
    return False


def _find_owner(snapshot: Dict[str, List[str]], item_name: str) -> Optional[str]:
    owners = [name for name, item_names in snapshot.items() if _contains_item(item_names, item_name)]
    if len(owners) == 1:
        return owners[0]
    return None


def evaluate_tracked_item_possession_query(
    user_utterance: str,
    party_tracker_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Return deterministic possession truth for explicit inventory-check turns."""
    if not is_possession_query_turn(user_utterance):
        return {"is_query": False, "handled": False, "authoritative_checked": False}

    snapshot = _build_inventory_snapshot(party_tracker_data)
    target_character = _select_target_character(user_utterance, party_tracker_data)

    quoted_item = _extract_quoted_item(user_utterance)
    matched_item = quoted_item or _match_item_from_snapshot(user_utterance, snapshot)

    # Handle generic pack checks even when no specific item is named.
    utterance_norm = _normalize_text(user_utterance)
    if not matched_item and re.search(r"\b(pack|inventory|bag|satchel)\b", utterance_norm):
        owned_items = snapshot.get(target_character, [])
        if owned_items:
            preview = ", ".join(owned_items[:8])
            response_text = f"Inventory check: {target_character} currently carries {preview}."
        else:
            response_text = f"Inventory check: {target_character} is not carrying any listed items right now."
        return {
            "is_query": True,
            "handled": True,
            "authoritative_checked": True,
            "target_character": target_character,
            "item_name": "",
            "response_text": response_text,
        }

    if not matched_item:
        return {
            "is_query": True,
            "handled": False,
            "authoritative_checked": True,
            "target_character": target_character,
            "item_name": "",
            "reason": "ambiguous_item",
        }

    target_items = snapshot.get(target_character, [])
    if _contains_item(target_items, matched_item):
        response_text = f"Inventory check: {target_character} currently has {matched_item}."
    else:
        owner_name = _find_owner(snapshot, matched_item)
        if owner_name:
            response_text = (
                f"Inventory check: {target_character} does not currently have {matched_item}. "
                f"{owner_name} currently has it."
            )
        else:
            response_text = f"Inventory check: no party member currently has {matched_item}."

    return {
        "is_query": True,
        "handled": True,
        "authoritative_checked": True,
        "target_character": target_character,
        "item_name": matched_item,
        "response_text": response_text,
    }
