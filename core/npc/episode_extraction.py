"""Companion EPISODE extraction (callsite T108).

Turns full-fidelity encounter text into attributed canonical-episode content:
a headline, a bounded shared-truth summary, entity tags, and salient facts each
attributed to a PRESENT companion. This is the empirically-validated capture that
recovers the attachment beats the DM-perspective T018 summary drops (a companion's
quiet gift, joke, fear, tender gesture) -- WITH correct attribution.

Design rules honored:
- Reads full-fidelity text, not the lossy summary.
- Model PARSES; code RECONCILES: a salient fact is kept only if its companion is in
  the present set (name -> identity id); a merely-mentioned absent companion gets
  nothing. The EpisodeStore is the final sanitizing/validating gate.
- Best-effort / fail-open: any failure returns None; a location close still happens.
- Gated at the call site by NPC_VOICE_ENABLED; model bound via the T108 registry.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import model_config
from core.ai import api_client
from core.npc.episode_store import VALID_SALIENT_KINDS
from utils.capture.multi_model_capture import register_callsite

_LOGGER = logging.getLogger(__name__)

TASK_ID = "T108"
PROMPT_VERSION = "npc-episode-extract/v1"

register_callsite(TASK_ID, "core/npc/episode_extraction.py", 40)

# Client-side validation shape (also converted for Gemini response_schema).
EXTRACTION_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "canonicalSummary", "intensity", "entityTags", "salientFacts"],
    "properties": {
        "headline": {"type": "string"},
        "canonicalSummary": {"type": "string"},
        "intensity": {"type": "number"},
        "entityTags": {"type": "array", "items": {"type": "string"}},
        "salientFacts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["npc", "kind", "oneLine"],
                "properties": {
                    "npc": {"type": "string"},
                    "kind": {"type": "string"},
                    "oneLine": {"type": "string"},
                    "objectLabel": {"type": "string"},
                },
            },
        },
    },
}

_SYSTEM = """You extract a CANONICAL episode from a raw scene of tabletop play, plus the PER-COMPANION personal beats it contains. Present companions are listed; only they can be the subject of a salient fact.

Produce:
- headline: a short label for what happened here (<=100 chars).
- canonicalSummary: the shared, factual account of the scene, third person, <=600 chars. Only what the text supports. This is the DM-agreed truth; do not embellish or invent.
- intensity: 0..1, how emotionally weighty this scene is (a near-death or betrayal is high; idle travel is low).
- entityTags: short lowercase anchors for later recall (e.g. "wizard", "boss:vheshk", "wishing well"). <=12.
- salientFacts: the SPECIFIC, personal, character-defining beats a plot summary drops -- a gesture, habit, joke, fear shown, tender act, gift, vow, near-death. Each: {npc, kind, oneLine, objectLabel?}.

STRICT RULES:
- Use ONLY what is explicitly in the text. Never invent a trait, motive, nickname, or number.
- Attribute each salient fact to the EXACT present companion who DID it.
- PRESENCE GUARD: only companions who are physically present and acting get facts. If a companion is merely MENTIONED or talked ABOUT (not present), do NOT create a fact for them.
- kind is one of: {kinds}.
- oneLine <=120 chars, concrete detail + attribution intact. Ignore generic combat/plot beats for salientFacts (those live in canonicalSummary).

Present companions: {companions}. Player: {player}.
Return ONLY JSON matching the requested shape."""


def flatten_scene(messages: Sequence[Mapping[str, Any]], *, max_chars: int = 16000) -> str:
    """Flatten raw play messages to DM/Player dialogue, skipping already-compressed
    summary blocks. Mirrors the T018 flattener so extraction reads the same source."""
    def is_summary(text: str) -> bool:
        t = text.strip()
        return t.startswith("===") or "LOCATION SUMMARY" in t or "Chronicle Summary" in t

    lines: List[str] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "") or ""
        if role == "assistant":
            narration = content
            if content.strip().startswith("{"):
                try:
                    narration = json.loads(content).get("narration", content)
                except (ValueError, TypeError):
                    narration = content
            if narration and not is_summary(narration):
                lines.append("Dungeon Master: %s" % narration)
        elif role == "user" and "Player:" in content:
            lines.append("Player: %s" % content.split("Player:", 1)[1].strip())
    scene = "\n\n".join(lines)
    return scene[-max_chars:] if len(scene) > max_chars else scene


def _build_messages(scene_text: str, companion_names: Sequence[str], player_name: str) -> List[Dict[str, str]]:
    system = (
        _SYSTEM.replace("{kinds}", ", ".join(sorted(VALID_SALIENT_KINDS)))
        .replace("{companions}", ", ".join(companion_names) or "(none)")
        .replace("{player}", player_name or "the player")
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "Scene:\n\n%s" % scene_text},
    ]


def _completion_kwargs(provider: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"model": config["model"]}
    for key, value in config.items():
        if key != "model":
            kwargs[key] = value
    if provider == "gemini":
        kwargs["response_schema"] = model_config.convert_to_gemini_schema(EXTRACTION_RESPONSE_SCHEMA)
        kwargs["response_format"] = None
    elif provider == "lmstudio":
        kwargs["response_format"] = None
    else:  # openai / legacy
        kwargs["response_format"] = {"type": "json_object"}
    # Temperature intentionally omitted: luna|low rejects temperature != 1, and
    # extraction does not need low-temperature determinism.
    return kwargs


def extract_episode(
    scene_text: str,
    present_companions: Sequence[Mapping[str, str]],
    *,
    player_name: str = "",
    provider: Optional[str] = None,
    completion_fn: Callable[..., Any] = api_client.create_completion,
    capture_fn: Callable[..., Any] = None,
) -> Optional[Dict[str, Any]]:
    """Extract canonical-episode content from a scene. Returns commit-ready kwargs
    (minus coordinates) or None on failure. present_companions: [{'name','id'}, ...].
    """
    if not scene_text.strip() or not present_companions:
        return None
    prov = provider or model_config.get_provider()
    config = model_config.resolve_callsite_config(TASK_ID, prov)
    names = [c["name"] for c in present_companions if c.get("name")]
    name_to_id = {c["name"]: c.get("id") for c in present_companions if c.get("name")}
    name_to_id_ci = {c["name"].casefold(): c.get("id") for c in present_companions if c.get("name")}

    messages = _build_messages(scene_text, names, player_name)
    capture = capture_fn or (lambda task_id, fn, **kw: fn(**kw))

    try:
        response = capture(TASK_ID, completion_fn, _request_provider=prov,
                           messages=messages, **_completion_kwargs(prov, config))
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception as error:  # noqa: BLE001 - fail-open by design
        _LOGGER.debug("episode extraction failed: %r", error)
        return None
    if not isinstance(payload, Mapping):
        return None

    # Reconcile by code: keep only facts for PRESENT companions, map name -> id.
    facts: List[Dict[str, Any]] = []
    for raw in payload.get("salientFacts", []) or []:
        if not isinstance(raw, Mapping):
            continue
        npc = (raw.get("npc") or "").strip()
        kind = raw.get("kind")
        one_line = (raw.get("oneLine") or "").strip()
        actor_id = name_to_id.get(npc) or name_to_id_ci.get(npc.casefold())
        if actor_id is None or kind not in VALID_SALIENT_KINDS or not one_line:
            continue  # absent/mentioned companion, or malformed -> drop (present-guard)
        fact: Dict[str, Any] = {
            "kind": kind,
            "subject": {"label": npc, "id": actor_id},
            "oneLine": one_line,
        }
        obj_label = (raw.get("objectLabel") or "").strip()
        if obj_label:
            fact["object"] = {"label": obj_label}
        facts.append(fact)

    witness_ids = [c["id"] for c in present_companions if c.get("id")]
    return {
        "headline": (payload.get("headline") or "").strip(),
        "canonical_summary": (payload.get("canonicalSummary") or "").strip(),
        "salient_facts": facts,
        "entity_tags": [str(t).strip() for t in (payload.get("entityTags") or []) if str(t).strip()],
        "witness_ids": witness_ids,
        "intensity": payload.get("intensity", 0.0),
        "prompt_version": PROMPT_VERSION,
    }
