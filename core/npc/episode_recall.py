"""Phase 4: grounded episodic recall (callsite T112).

When the player references the past ("remember when we took down that wizard, you
almost died in the Mountain of Chaos?"), a luna call PARSES the line into structured
anchors (entities/places/outcomes). CODE then lexically selects the matching episodes
from the NPC's OWN witnessed set -- the model never sees or chooses an episode, so it
cannot fabricate a shared memory. Returns the matched episodes + a confidence the DM
uses under a closed-world grounding contract (vivid / partial / absent).

No embeddings in v1 (Phase 7). Fail-open: any failure -> absent (the NPC honestly
does not recall), never a fabrication.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import model_config
from core.ai import api_client
from utils.capture.multi_model_capture import register_callsite

_LOGGER = logging.getLogger(__name__)
TASK_ID = "T112"
PROMPT_VERSION = "npc-recall-anchors/v1"
register_callsite(TASK_ID, "core/npc/episode_recall.py", 34)

ANCHOR_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entities", "places", "outcomes"],
    "properties": {
        "entities": {"type": "array", "items": {"type": "string"}},
        "places": {"type": "array", "items": {"type": "string"}},
        "outcomes": {"type": "array", "items": {"type": "string"}},
    },
}

_SYSTEM = """The player is referencing a PAST shared event. Extract the concrete anchors they name, so we can look it up. Do not judge whether it happened; just parse.
Return ONLY JSON: {"entities":[...], "places":[...], "outcomes":[...]}
- entities: named foes/people/things ("the wizard", "the wolf collar").
- places: named locations ("Mountain of Chaos", "the caves").
- outcomes: what happened ("almost died", "clever move", "betrayed me").
Lowercase short phrases; omit filler. If the line references nothing concrete, return empty arrays."""

_STOPWORDS = frozenset({
    "the", "and", "you", "your", "our", "that", "this", "with", "from", "into", "was",
    "were", "had", "has", "for", "when", "then", "they", "them", "his", "her", "she",
    "him", "who", "what", "about", "back", "made", "make", "got", "get", "did", "done",
})


def _tokens(text: Any) -> set:
    if not isinstance(text, str):
        return set()
    return {
        t
        for t in re.split(r"[^a-z0-9]+", text.lower())
        if len(t) >= 3 and t not in _STOPWORDS
    }


# Outcome phrasing -> the salientFact kind it implies (a small, curated hint set so
# "almost died" reliably finds a near_death episode even without lexical tag overlap).
_OUTCOME_KIND_HINTS: Dict[str, frozenset] = {
    "near_death": frozenset({"died", "death", "dying", "nearly", "almost", "killed", "wounded"}),
    "betrayal": frozenset({"betray", "betrayed", "betrayal", "turned"}),
    "rescue": frozenset({"saved", "rescued", "rescue", "pulled"}),
    "protect": frozenset({"shielded", "protected", "defended", "blocked"}),
    "sacrifice": frozenset({"sacrificed", "sacrifice", "gave"}),
    "loss": frozenset({"lost", "loss", "died", "gone"}),
    "confession": frozenset({"confessed", "confession", "admitted", "loved"}),
    "vow": frozenset({"promised", "vowed", "swore", "promise"}),
}


def _episode_terms(episode: Mapping[str, Any]) -> set:
    terms = _tokens(episode.get("locationName")) | _tokens(episode.get("headline"))
    for tag in episode.get("entityTags", []) or []:
        terms |= _tokens(tag)
    for fact in episode.get("salientFacts", []) or []:
        if isinstance(fact, Mapping):
            terms |= _tokens(fact.get("oneLine"))
    return terms


def _completion_kwargs(provider: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {k: v for k, v in config.items()}
    if provider == "gemini":
        kwargs["response_schema"] = model_config.convert_to_gemini_schema(ANCHOR_RESPONSE_SCHEMA)
        kwargs["response_format"] = None
    elif provider == "lmstudio":
        kwargs["response_format"] = None
    else:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def parse_anchors(
    player_line: str,
    *,
    provider: Optional[str] = None,
    completion_fn: Callable[..., Any] = api_client.create_completion,
    capture_fn: Callable[..., Any] = None,
) -> Optional[Dict[str, List[str]]]:
    prov = provider or model_config.get_provider()
    config = dict(model_config.resolve_callsite_config(TASK_ID, prov))
    model = config.pop("model")
    capture = capture_fn or (lambda task_id, fn, **kw: fn(**kw))
    try:
        response = capture(
            TASK_ID, completion_fn, _request_provider=prov, model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": player_line},
            ],
            **_completion_kwargs(prov, config),
        )
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception as error:  # noqa: BLE001 - fail-open -> caller treats as absent
        _LOGGER.debug("recall anchor parse failed: %r", error)
        return None
    if not isinstance(payload, Mapping):
        return None
    return {
        "entities": [str(x) for x in (payload.get("entities") or []) if str(x).strip()],
        "places": [str(x) for x in (payload.get("places") or []) if str(x).strip()],
        "outcomes": [str(x) for x in (payload.get("outcomes") or []) if str(x).strip()],
    }


# A memory needs a real anchor hit, not one incidental token. An outcome->kind hint
# (worth 2) or two overlapping content tokens clears the bar; a lone stray token does
# not -- this is what keeps a fabricated reference from matching an unrelated episode.
MATCH_THRESHOLD = 2
VIVID_THRESHOLD = 4


def select_episodes(
    anchors: Mapping[str, Sequence[str]],
    episodes: Sequence[Mapping[str, Any]],
    *,
    ignore_terms: Any = frozenset(),
) -> List[Dict[str, Any]]:
    """Code-only selection: score each episode by lexical overlap with the anchors
    plus outcome->kind hints. `ignore_terms` (e.g. the NPC's own name -- never a
    distinguishing anchor) are removed so an addressed name cannot false-match every
    episode about that NPC. Returns episodes scoring >= MATCH_THRESHOLD."""
    anchor_terms = set()
    for key in ("entities", "places", "outcomes"):
        for phrase in anchors.get(key, []):
            anchor_terms |= _tokens(phrase)
    anchor_terms -= set(ignore_terms)
    outcome_tokens = set()
    for phrase in anchors.get("outcomes", []):
        outcome_tokens |= _tokens(phrase)
    outcome_tokens -= set(ignore_terms)

    scored: List[Dict[str, Any]] = []
    for episode in episodes:
        terms = _episode_terms(episode)
        score = len(anchor_terms & terms)
        kinds = {
            f.get("kind")
            for f in episode.get("salientFacts", []) or []
            if isinstance(f, Mapping)
        }
        for kind, hints in _OUTCOME_KIND_HINTS.items():
            if kind in kinds and (outcome_tokens & hints):
                score += 2
        if score >= MATCH_THRESHOLD:
            scored.append({"episode": episode, "score": score})
    scored.sort(key=lambda s: (s["score"], s["episode"].get("ordinal", 0)), reverse=True)
    return scored


def recall_episodes(
    player_line: str,
    npc_id: str,
    *,
    episode_store: Any,
    provider: Optional[str] = None,
    completion_fn: Callable[..., Any] = api_client.create_completion,
    capture_fn: Callable[..., Any] = None,
    limit: int = 3,
) -> Dict[str, Any]:
    """Grounded recall for one NPC. Returns {confidence, episodes, anchors}.
    confidence: 'vivid' | 'partial' | 'absent'. Fail-open -> 'absent'."""
    empty = {"confidence": "absent", "episodes": [], "anchors": None}
    if not player_line.strip() or not npc_id or episode_store is None:
        return empty
    try:
        episodes = episode_store.episodes_for_witness(npc_id)
    except Exception:
        return empty
    if not episodes:
        return empty
    anchors = parse_anchors(
        player_line, provider=provider, completion_fn=completion_fn, capture_fn=capture_fn
    )
    if anchors is None:
        return empty
    # The NPC's own name(s) are never a distinguishing anchor (every one of their
    # episodes mentions them); strip them so an addressed name can't false-match.
    ignore_terms = set()
    for episode in episodes:
        for fact in episode.get("salientFacts", []) or []:
            subject = fact.get("subject") if isinstance(fact, Mapping) else None
            if isinstance(subject, Mapping) and subject.get("id") == npc_id:
                ignore_terms |= _tokens(subject.get("label"))
    scored = select_episodes(anchors, episodes, ignore_terms=ignore_terms)
    if not scored:
        return {"confidence": "absent", "episodes": [], "anchors": anchors}
    top = scored[:limit]
    confidence = "vivid" if top[0]["score"] >= VIVID_THRESHOLD else "partial"
    return {
        "confidence": confidence,
        "episodes": [s["episode"] for s in top],
        "anchors": anchors,
    }
