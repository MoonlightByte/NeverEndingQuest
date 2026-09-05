"""Deterministic out-of-combat NPC mention ordering."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


def _exact_name_mentioned(name: str, raw_input: str) -> bool:
    if not name or not raw_input:
        return False
    pattern = r"(?<!\w)%s(?!\w)" % re.escape(name)
    return re.search(pattern, raw_input, flags=re.IGNORECASE) is not None


def _name_tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[^\W_]+", value, flags=re.UNICODE)
        if token
    }


def resolve_ooc_mention(
    party_npcs: Iterable[Mapping[str, Any]], raw_input: str
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Resolve one exact or unique name-token mention.

    The boolean is true when name-like input matched multiple roster NPCs and
    therefore must not be used to choose a relationship edge.
    """
    candidates = [dict(npc) for npc in party_npcs if isinstance(npc, dict)]
    exact_indexes = [
        index
        for index, npc in enumerate(candidates)
        if _exact_name_mentioned(str(npc.get("name", "")), raw_input)
    ]
    if len(exact_indexes) == 1:
        return candidates[exact_indexes[0]], False
    if len(exact_indexes) > 1:
        return None, True

    roster_tokens: Dict[str, set[int]] = {}
    for index, npc in enumerate(candidates):
        for token in _name_tokens(str(npc.get("name", ""))):
            roster_tokens.setdefault(token, set()).add(index)

    unique_indexes = set()
    shared_token_matched = False
    for token in _name_tokens(raw_input):
        indexes = roster_tokens.get(token, set())
        if len(indexes) == 1:
            unique_indexes.update(indexes)
        elif len(indexes) > 1:
            shared_token_matched = True
    if len(unique_indexes) == 1:
        return candidates[next(iter(unique_indexes))], False
    if len(unique_indexes) > 1 or shared_token_matched:
        return None, True
    return None, False


def rank_ooc_candidates(
    party_npcs: Iterable[Mapping[str, Any]],
    raw_input: str,
) -> List[Dict[str, Any]]:
    """Put one unambiguous mention first while retaining every roster NPC."""
    candidates = [dict(npc) for npc in party_npcs if isinstance(npc, dict)]
    mentioned, _ambiguous = resolve_ooc_mention(candidates, raw_input)
    if mentioned is None:
        return candidates
    return [mentioned] + [npc for npc in candidates if npc != mentioned]
