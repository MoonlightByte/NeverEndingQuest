"""Phase 4: grounded episodic recall (callsite T112).

When the player references the past ("remember when we took down that wizard, you
almost died in the Mountain of Chaos?"), a luna call PARSES the line into structured
anchors (entities/places/outcomes). CODE then lexically selects the matching episodes
from the NPC's OWN witnessed set -- the model never sees or chooses an episode, so it
cannot fabricate a shared memory. Returns the matched episodes + a confidence the DM
uses under a closed-world grounding contract (vivid / partial / absent).

No embeddings in v1 (Phase 7). A completed empty parse means no anchors; provider or
contract failure returns unavailable so callers omit recall for only that beat rather
than asserting that the NPC remembers nothing.
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
Lowercase the extracted values; omit filler. If the line references nothing concrete, return empty arrays."""

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
    advisory_scope=None,
) -> Optional[Dict[str, List[str]]]:
    prov = provider or model_config.get_provider()
    config = dict(model_config.resolve_callsite_config(TASK_ID, prov))
    model = config.pop("model")
    if capture_fn is None:
        from utils.capture.multi_model_capture import capture_and_fanout

        capture_fn = capture_and_fanout
    try:
        response = capture_fn(
            TASK_ID, completion_fn, _request_provider=prov, model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": player_line},
            ],
            _live_selected="advisory" if advisory_scope is not None else False,
            _detached_scope=advisory_scope,
            **_completion_kwargs(prov, config),
        )
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception as error:  # noqa: BLE001 - caller treats None as unavailable
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


def _norm_value(text: Any) -> str:
    """Normalize a typed VALUE for exact comparison: lowercase, collapse
    whitespace, strip a leading article. This is value normalization of
    model-extracted typed anchor fields, not prose matching."""
    if not isinstance(text, str):
        return ""
    value = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"^(?:the|a|an) ", "", value)


def _episode_exact_values(episode: Mapping[str, Any]) -> set:
    """The episode's typed field VALUES (entity tags, location name, headline,
    salient-fact subject labels), normalized for exact value comparison."""
    values = {_norm_value(episode.get("locationName")), _norm_value(episode.get("headline"))}
    for tag in episode.get("entityTags", []) or []:
        values.add(_norm_value(tag))
    for fact in episode.get("salientFacts", []) or []:
        if isinstance(fact, Mapping):
            subject = fact.get("subject")
            if isinstance(subject, Mapping):
                values.add(_norm_value(subject.get("label")))
    values.discard("")
    return values


def select_episodes(
    anchors: Mapping[str, Sequence[str]],
    episodes: Sequence[Mapping[str, Any]],
    *,
    ignore_terms: Any = frozenset(),
    current_location_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Code-only selection: score each episode by lexical overlap with the anchors
    plus outcome->kind hints. `ignore_terms` (e.g. the NPC's own name -- never a
    distinguishing anchor) are removed so an addressed name cannot false-match every
    episode about that NPC. Returns episodes scoring >= MATCH_THRESHOLD.

    `current_location_id`: when the party is standing at an episode's location, that
    shared physical place IS a real anchor -- add +2 (the outcome-hint weight) so a
    bare "remember this place?" can reach threshold. This never fabricates: the
    episode is still drawn only from the NPC's own witnessed set and really happened
    HERE, so surfacing it is a true recall, not a manufactured event. On a tie, prefer
    the finer-grained episode (a specific fight over a coarse module backfill)."""
    from core.npc.episode_store import episode_grain_rank

    anchor_terms = set()
    for key in ("entities", "places", "outcomes"):
        for phrase in anchors.get(key, []):
            anchor_terms |= _tokens(phrase)
    anchor_terms -= set(ignore_terms)
    # EXACT VALUE RULE: anchors are model-extracted typed fields, so a normalized
    # anchor VALUE that equals an episode's typed-field value (entity tag, location
    # name, headline, subject label) is a definitive hit -- such an episode is
    # flagged "exact" and callers include it regardless of the top-N rank cap
    # (exact value match beats rank). This is value comparison, never prose
    # matching. Anchor values that reduce to the ignored NPC-name tokens are
    # excluded so an addressed name cannot exact-match every episode.
    ignore_set = set(ignore_terms)
    anchor_values = set()
    for key in ("entities", "places", "outcomes"):
        for phrase in anchors.get(key, []):
            value = _norm_value(phrase)
            if value and not (_tokens(value) and _tokens(value) <= ignore_set):
                anchor_values.add(value)
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
        if current_location_id and episode.get("locationId") == current_location_id:
            score += 2
        # Exact typed-value hit: include even if lexical overlap alone is below
        # threshold (anchor-parse variance must not hide a definitive value match).
        exact = bool(anchor_values & _episode_exact_values(episode))
        if exact:
            score = max(score, MATCH_THRESHOLD)
        if score >= MATCH_THRESHOLD:
            scored.append({"episode": episode, "score": score, "exact": exact})
    scored.sort(
        key=lambda s: (
            s["score"],
            -episode_grain_rank(s["episode"]),
            s["episode"].get("ordinal", 0),
        ),
        reverse=True,
    )
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
    current_location_id: Optional[str] = None,
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
    scored = select_episodes(
        anchors, episodes, ignore_terms=ignore_terms,
        current_location_id=current_location_id,
    )
    if not scored:
        return {"confidence": "absent", "episodes": [], "anchors": anchors}
    # Exact value match beats rank: keep the cap for rank-only candidates, but an
    # episode whose typed fields exactly match an anchor value is always included.
    top = scored[:limit] + [s for s in scored[limit:] if s.get("exact")]
    confidence = "vivid" if top[0]["score"] >= VIVID_THRESHOLD else "partial"
    return {
        "confidence": confidence,
        "episodes": [s["episode"] for s in top],
        "anchors": anchors,
    }
