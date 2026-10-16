"""Phase 4: grounded episodic recall (callsite T112).

When the player references the past ("remember when we took down that wizard, you
almost died in the Mountain of Chaos?"), one luna call reads the line together with
each companion's OWN witnessed episodes (typed rows: id, headline, place, whether the
party stands there now, salient facts) and returns the episodeIds the line concretely
refers to. CODE owns identity: an id that is not in that companion's witnessed set is
dropped, so the model can only point at memories that exist and cannot fabricate a
shared one. The matched episodes go to the DM under a closed-world grounding contract
(vivid / partial / absent).

A completed empty selection means no match (honest_no_match); a provider or contract
failure returns None so callers omit recall for only that beat rather than asserting
that the NPC remembers nothing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import model_config
from core.ai import api_client
from utils.capture.multi_model_capture import register_callsite

_LOGGER = logging.getLogger(__name__)
TASK_ID = "T112"
PROMPT_VERSION = "npc-recall-select/v2"
register_callsite(TASK_ID, "core/npc/episode_recall.py", 125)

# At most this many recalled episodes per companion reach the voice packet.
MAX_RECALLED_PER_NPC = 2

SELECTION_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["selections"],
    "properties": {
        "selections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["npcId", "episodeIds"],
                "properties": {
                    "npcId": {"type": "string"},
                    "episodeIds": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

_SYSTEM = """You read one line the player just said and, for each companion listed, that companion's own memories of events they witnessed with the party. Decide which of those memories the line concretely refers to. Do not judge whether the player is right; only match.
Return ONLY JSON: {"selections":[{"npcId":"...","episodeIds":["..."]}]}
- Use only npcId and episodeId values copied from the input. Never make up an id.
- Choose an episode only when the line concretely points at it: a named or clearly described person, foe, thing, place or outcome from that episode. Paraphrases count ("the old ranger hut" for a ranger outpost).
- A line about "this place" or "here" may refer to episodes marked atCurrentLocation true.
- Order the ids most specific first: a particular event over a broad summary of a journey.
- If the line refers to something none of a companion's memories contains, or makes no concrete reference to a shared past (present or future intent, small talk), return an empty episodeIds list for that companion. An empty list is a correct answer."""


def _recall_row(episode: Mapping[str, Any], current_location_id: Optional[str]) -> Dict[str, Any]:
    facts = []
    for fact in episode.get("salientFacts", []) or []:
        if isinstance(fact, Mapping):
            facts.append({"kind": fact.get("kind"), "oneLine": fact.get("oneLine")})
    return {
        "episodeId": episode.get("episodeId"),
        "headline": episode.get("headline"),
        "locationName": episode.get("locationName"),
        "atCurrentLocation": bool(
            current_location_id and episode.get("locationId") == current_location_id
        ),
        "salientFacts": facts,
    }


def _completion_kwargs(provider: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {k: v for k, v in config.items()}
    if provider == "gemini":
        kwargs["response_schema"] = model_config.convert_to_gemini_schema(SELECTION_RESPONSE_SCHEMA)
        kwargs["response_format"] = None
    elif provider == "lmstudio":
        kwargs["response_format"] = None
    else:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def select_recalled_episodes(
    player_line: str,
    episodes_by_npc: Mapping[str, Sequence[Mapping[str, Any]]],
    current_location_id: Optional[str] = None,
    *,
    provider: Optional[str] = None,
    completion_fn: Callable[..., Any] = api_client.create_completion,
    capture_fn: Callable[..., Any] = None,
    advisory_scope=None,
) -> Optional[Dict[str, List[Mapping[str, Any]]]]:
    """Ask T112 which of each companion's witnessed episodes the line refers to.

    Returns {npcId: [episode, ...]} holding only companions with a match (at most
    MAX_RECALLED_PER_NPC each, in the model's order); {} when nothing matches; None
    when the call or its reply failed."""
    prov = provider or model_config.get_provider()
    config = dict(model_config.resolve_callsite_config(TASK_ID, prov))
    model = config.pop("model")
    if capture_fn is None:
        from utils.capture.multi_model_capture import capture_and_fanout

        capture_fn = capture_and_fanout
    request = {
        "playerLine": player_line,
        "companions": [
            {
                "npcId": npc_id,
                "memories": [_recall_row(episode, current_location_id) for episode in episodes],
            }
            for npc_id, episodes in episodes_by_npc.items()
        ],
    }
    try:
        response = capture_fn(
            TASK_ID, completion_fn, _request_provider=prov, model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
            ],
            _live_selected="advisory" if advisory_scope is not None else False,
            _detached_scope=advisory_scope,
            **_completion_kwargs(prov, config),
        )
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception as error:  # noqa: BLE001 - caller treats None as unavailable
        _LOGGER.debug("recall selection failed: %r", error)
        return None
    if not isinstance(payload, Mapping) or not isinstance(payload.get("selections"), list):
        return None
    selected: Dict[str, List[Mapping[str, Any]]] = {}
    for row in payload["selections"]:
        if not isinstance(row, Mapping):
            continue
        npc_id = row.get("npcId")
        ids = row.get("episodeIds")
        if npc_id not in episodes_by_npc or not isinstance(ids, list):
            continue
        witnessed = {episode.get("episodeId"): episode for episode in episodes_by_npc[npc_id]}
        chosen = selected.setdefault(npc_id, [])
        for episode_id in ids:
            if episode_id not in witnessed:
                _LOGGER.warning("recall_invalid_id: %r is not witnessed by %s", episode_id, npc_id)
                continue
            if witnessed[episode_id] not in chosen and len(chosen) < MAX_RECALLED_PER_NPC:
                chosen.append(witnessed[episode_id])
    return {npc_id: chosen for npc_id, chosen in selected.items() if chosen}
