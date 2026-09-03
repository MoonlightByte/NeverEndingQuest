"""Deterministic out-of-combat NPC relevance and fairness selection."""

from __future__ import annotations

import re
import threading
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


class SelectionFairness:
    """Process-long least-recently-merged rotation keyed by stable NPC ID."""

    def __init__(self) -> None:
        self._last_merged: Dict[str, int] = {}
        self._turn = 0
        self._lock = threading.Lock()

    def last_merged(self, npc_id: str) -> int:
        with self._lock:
            return self._last_merged.get(npc_id, -1)

    def record_merged(self, npc_ids: Iterable[str]) -> None:
        stable_ids = {str(value) for value in npc_ids if str(value)}
        if not stable_ids:
            return
        with self._lock:
            self._turn += 1
            for npc_id in stable_ids:
                self._last_merged[npc_id] = self._turn


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
    *,
    evidence_npc_ids: Optional[Iterable[str]] = None,
    fairness: Optional[SelectionFairness] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Rank mention, evidence, and least-recent merge with stable ID ties.

    The legacy Phase 1 call shape retains roster order after its mention when
    no Phase 3 relevance inputs are supplied.
    """
    candidates = [dict(npc) for npc in party_npcs if isinstance(npc, dict)]
    mentioned, _ambiguous = resolve_ooc_mention(candidates, raw_input)
    if evidence_npc_ids is None and fairness is None and limit is None:
        if mentioned is None:
            return candidates
        return [mentioned] + [npc for npc in candidates if npc != mentioned]

    mentioned_name = str(mentioned.get("name", "")) if mentioned else ""
    evidence_ids = {str(value) for value in (evidence_npc_ids or ())}

    def stable_id(candidate: Mapping[str, Any]) -> str:
        return str(
            candidate.get("npcId")
            or candidate.get("id")
            or candidate.get("name")
            or ""
        )

    def rank(candidate: Mapping[str, Any]) -> tuple[int, int, int, str]:
        npc_id = stable_id(candidate)
        return (
            0
            if mentioned_name and str(candidate.get("name", "")) == mentioned_name
            else 1,
            0 if npc_id in evidence_ids else 1,
            fairness.last_merged(npc_id) if fairness is not None else -1,
            npc_id,
        )

    ranked = sorted(candidates, key=rank)
    if limit is None:
        return ranked
    return ranked[: max(0, int(limit))]
