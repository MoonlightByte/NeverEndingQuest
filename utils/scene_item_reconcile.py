# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Scene Item Reconciliation
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Narrow deterministic reconciliation for explicit narrated scene gifts.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


_TRANSFER_VERBS_GIVER = ("give", "gives", "hand", "hands", "offer", "offers", "provide", "provides")
_TRANSFER_VERBS_RECIPIENT = ("take", "takes", "receive", "receives")
_QUANTITY_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_VAGUE_ITEM_TERMS = {
    "supplies",
    "provisions",
    "gear",
    "items",
    "stuff",
    "reward",
    "rewards",
}


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace("'", "").replace("_", " ")


def _latest_user_text(conversation_history: List[Dict[str, Any]]) -> str:
    for entry in reversed(conversation_history):
        if not isinstance(entry, dict):
            continue
        if entry.get("role") != "user":
            continue
        content = entry.get("content")
        if isinstance(content, str):
            return content
    return ""


def _has_matching_inventory_add_action(actions: List[Dict[str, Any]], character_name: str, item_name: str) -> bool:
    target_character = _normalize_name(character_name)
    target_item = item_name.strip().lower()
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action") != "updateCharacterInfo":
            continue
        params = action.get("parameters", {})
        if not isinstance(params, dict):
            continue
        existing_character = str(params.get("characterName") or "")
        if _normalize_name(existing_character) != target_character:
            continue
        ops = params.get("ops")
        if not isinstance(ops, list):
            continue
        for op in ops:
            if not isinstance(op, dict):
                continue
            op_name = str(op.get("op") or op.get("type") or "").strip().lower()
            if op_name != "inventory_add":
                continue
            op_item = str(op.get("item_name") or op.get("name") or op.get("item") or "").strip().lower()
            if op_item == target_item:
                return True
    return False


def _build_party_name_lookup(party_tracker_data: Dict[str, Any]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}

    for name in party_tracker_data.get("partyMembers", []):
        if isinstance(name, str) and name.strip():
            lookup[_normalize_name(name)] = name.strip()

    for npc in party_tracker_data.get("partyNPCs", []):
        if isinstance(npc, dict):
            npc_name = npc.get("name")
        elif isinstance(npc, str):
            npc_name = npc
        else:
            npc_name = ""
        if isinstance(npc_name, str) and npc_name.strip():
            lookup[_normalize_name(npc_name)] = npc_name.strip()

    return lookup


def _build_alias_lookup(names: List[str]) -> Dict[str, str]:
    """Build unambiguous alias -> canonical name mapping."""
    candidates: Dict[str, Set[str]] = {}

    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        canonical = name.strip()
        normalized = _normalize_name(canonical)
        tokens = [token for token in normalized.split() if token]

        aliases: Set[str] = {normalized}
        if tokens:
            aliases.add(tokens[-1])
        if len(tokens) >= 2:
            aliases.add(" ".join(tokens[-2:]))

        for alias in aliases:
            if not alias:
                continue
            candidates.setdefault(alias, set()).add(canonical)

    resolved: Dict[str, str] = {}
    for alias, canonical_names in candidates.items():
        if len(canonical_names) == 1:
            resolved[alias] = next(iter(canonical_names))
    return resolved


def _extract_scene_actor_names(location_data: Optional[Dict[str, Any]], party_tracker_data: Dict[str, Any]) -> List[str]:
    actor_names: List[str] = []

    if isinstance(location_data, dict):
        scene_npcs = location_data.get("npcs", [])
        if isinstance(scene_npcs, list):
            for npc in scene_npcs:
                if isinstance(npc, dict):
                    npc_name = npc.get("name")
                elif isinstance(npc, str):
                    npc_name = npc
                else:
                    npc_name = ""
                if isinstance(npc_name, str) and npc_name.strip():
                    actor_names.append(npc_name.strip())

    for name in party_tracker_data.get("partyMembers", []):
        if isinstance(name, str) and name.strip():
            actor_names.append(name.strip())

    for npc in party_tracker_data.get("partyNPCs", []):
        if isinstance(npc, dict):
            npc_name = npc.get("name")
        elif isinstance(npc, str):
            npc_name = npc
        else:
            npc_name = ""
        if isinstance(npc_name, str) and npc_name.strip():
            actor_names.append(npc_name.strip())

    # Deduplicate while preserving order.
    seen: Set[str] = set()
    ordered_unique: List[str] = []
    for actor_name in actor_names:
        normalized = _normalize_name(actor_name)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered_unique.append(actor_name)
    return ordered_unique


def _parse_item_and_quantity(raw_item_text: str) -> Optional[Tuple[str, int]]:
    text = raw_item_text.strip().lower()
    text = text.strip(" ,;:.\t")
    if not text:
        return None

    # Trim post-item clauses conservatively.
    text = re.split(r"\b(?:while|before|after|because|so that|to)\b", text, maxsplit=1)[0].strip(" ,;:.\t")
    text = re.sub(r"^(?:a|an|the)\s+", "", text)
    text = re.sub(r"^some\s+", "", text)
    text = re.sub(r"\s+each$", "", text)
    if not text:
        return None

    quantity = 1
    match = re.match(r"^(\d+)\s+(.+)$", text)
    if match:
        quantity = int(match.group(1))
        text = match.group(2).strip()
    else:
        for word, count in _QUANTITY_WORDS.items():
            prefix = f"{word} "
            if text.startswith(prefix):
                quantity = count
                text = text[len(prefix):].strip()
                break

    text = text.strip(" ,;:.\t")
    if not text:
        return None

    if text in _VAGUE_ITEM_TERMS:
        return None

    if len(text.split()) > 6:
        return None

    item_name = " ".join(token.capitalize() for token in text.split())
    return (item_name, max(1, quantity))


def _append_grant_action(
    grants: List[Dict[str, Any]],
    existing_actions: List[Dict[str, Any]],
    character_name: str,
    item_name: str,
    quantity: int,
    source_actor: Optional[str] = None,
) -> None:
    if _has_matching_inventory_add_action(existing_actions + grants, character_name, item_name):
        return

    source_text = f" from {source_actor}" if source_actor else " from scene transfer"
    grants.append(
        {
            "action": "updateCharacterInfo",
            "parameters": {
                "characterName": character_name,
                "changes": f"Received {quantity} {item_name}{source_text}.",
                "ops": [
                    {
                        "op": "inventory_add",
                        "item": item_name,
                        "quantity": quantity,
                    }
                ],
            },
        }
    )


def _text_has_actor_transfer_context(text_blob: str, actor_alias_lookup: Dict[str, str]) -> bool:
    for actor_alias in actor_alias_lookup:
        if not actor_alias:
            continue
        for verb in _TRANSFER_VERBS_GIVER:
            pattern = rf"\b{re.escape(actor_alias)}\b[^.!?\n,;]*\b{re.escape(verb)}\b"
            if re.search(pattern, text_blob):
                return True
    return False


def _extract_giver_to_recipient_grants(
    text_blob: str,
    actor_alias_lookup: Dict[str, str],
    recipient_alias_lookup: Dict[str, str],
) -> List[Tuple[str, str, int, str]]:
    grants: List[Tuple[str, str, int, str]] = []
    for actor_alias, actor_name in actor_alias_lookup.items():
        for recipient_alias, recipient_name in recipient_alias_lookup.items():
            if _normalize_name(actor_name) == _normalize_name(recipient_name):
                continue
            for verb in _TRANSFER_VERBS_GIVER:
                pattern = (
                    rf"\b{re.escape(actor_alias)}\b\s+{re.escape(verb)}\s+"
                    rf"\b{re.escape(recipient_alias)}\b\s+(?P<item>[^.!?\n,;]+)"
                )
                for match in re.finditer(pattern, text_blob):
                    parsed = _parse_item_and_quantity(match.group("item"))
                    if not parsed:
                        continue
                    item_name, quantity = parsed
                    grants.append((recipient_name, item_name, quantity, actor_name))
    return grants


def _extract_recipient_transfer_grants(
    text_blob: str,
    actor_alias_lookup: Dict[str, str],
    recipient_alias_lookup: Dict[str, str],
    require_actor_context: bool,
) -> List[Tuple[str, str, int, Optional[str]]]:
    grants: List[Tuple[str, str, int, Optional[str]]] = []

    actor_alias_pattern = "|".join(re.escape(alias) for alias in actor_alias_lookup.keys() if alias)

    for recipient_alias, recipient_name in recipient_alias_lookup.items():
        for verb in _TRANSFER_VERBS_RECIPIENT:
            pattern = (
                rf"\b{re.escape(recipient_alias)}\b\s+{re.escape(verb)}\s+"
                rf"(?P<item>[^.!?\n,;]+?)(?:\s+from\s+(?P<actor>[^.!?\n,;]+))?(?:$|[.!?\n,;])"
            )
            for match in re.finditer(pattern, text_blob):
                parsed = _parse_item_and_quantity(match.group("item"))
                if not parsed:
                    continue

                actor_name: Optional[str] = None
                actor_group = match.group("actor")
                if actor_group and actor_alias_pattern:
                    actor_match = re.search(rf"\b({actor_alias_pattern})\b", actor_group)
                    if actor_match:
                        actor_name = actor_alias_lookup.get(actor_match.group(1))

                if actor_name is None and require_actor_context:
                    continue

                item_name, quantity = parsed
                grants.append((recipient_name, item_name, quantity, actor_name))
    return grants


def _extract_each_distribution_grants(
    text_blob: str,
    actor_alias_lookup: Dict[str, str],
    recipient_alias_lookup: Dict[str, str],
    require_actor_context: bool,
) -> List[Tuple[str, str, int, Optional[str]]]:
    grants: List[Tuple[str, str, int, Optional[str]]] = []
    recipient_items = sorted(recipient_alias_lookup.items(), key=lambda item: len(item[0]), reverse=True)

    for first_alias, first_name in recipient_items:
        for second_alias, second_name in recipient_items:
            if _normalize_name(first_name) == _normalize_name(second_name):
                continue

            pattern = (
                rf"\b{re.escape(first_alias)}\b\s+and\s+\b{re.escape(second_alias)}\b\s+"
                rf"take(?:s)?\s+(?P<item>[^.!?\n,;]+?)\s+each\b"
            )
            for match in re.finditer(pattern, text_blob):
                if require_actor_context:
                    continue

                parsed = _parse_item_and_quantity(match.group("item"))
                if not parsed:
                    continue
                item_name, quantity = parsed

                # "each" implies per-recipient count. Keep minimum deterministic quantity of 1.
                each_quantity = quantity if quantity > 0 else 1
                grants.append((first_name, item_name, each_quantity, None))
                grants.append((second_name, item_name, each_quantity, None))
    return grants


def infer_scene_item_grant_actions(
    parsed_response: Dict[str, Any],
    party_tracker_data: Dict[str, Any],
    location_data: Optional[Dict[str, Any]],
    conversation_history: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Infer deterministic inventory grants for explicit narrated gift scenes.

    The detector is intentionally narrow and fails safe on ambiguous/vague prose.
    """
    actions = parsed_response.get("actions", [])
    if not isinstance(actions, list):
        actions = []

    narration = parsed_response.get("narration")
    narration_text = narration if isinstance(narration, str) else ""
    user_text = _latest_user_text(conversation_history)
    text_blob = f"{narration_text}\n{user_text}".lower()

    recipient_lookup = _build_party_name_lookup(party_tracker_data)
    recipient_names = list(recipient_lookup.values())
    if not recipient_names:
        return []

    actor_names = _extract_scene_actor_names(location_data, party_tracker_data)
    actor_alias_lookup = _build_alias_lookup(actor_names)
    recipient_alias_lookup = _build_alias_lookup(recipient_names)
    if not actor_alias_lookup or not recipient_alias_lookup:
        return []

    has_actor_transfer_context = _text_has_actor_transfer_context(text_blob, actor_alias_lookup)
    if not has_actor_transfer_context:
        # Allow explicit recipient-from-actor phrasing even without actor-leading clause.
        if " from " not in text_blob:
            return []

    raw_grants: List[Tuple[str, str, int, Optional[str]]] = []
    raw_grants.extend(
        _extract_giver_to_recipient_grants(text_blob, actor_alias_lookup, recipient_alias_lookup)
    )
    raw_grants.extend(
        _extract_recipient_transfer_grants(
            text_blob,
            actor_alias_lookup,
            recipient_alias_lookup,
            require_actor_context=not has_actor_transfer_context,
        )
    )
    raw_grants.extend(
        _extract_each_distribution_grants(
            text_blob,
            actor_alias_lookup,
            recipient_alias_lookup,
            require_actor_context=not has_actor_transfer_context,
        )
    )

    grants: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, int]] = set()
    for recipient_name, item_name, quantity, source_actor in raw_grants:
        dedupe_key = (_normalize_name(recipient_name), item_name.lower(), quantity)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        _append_grant_action(
            grants,
            actions,
            recipient_name,
            item_name,
            quantity,
            source_actor=source_actor,
        )

    return grants
