"""Phase 2: derive each witness NPC's POV overlay from a canonical episode.

100% code-derived from the episode's own attributed salient facts -- NO model call
(reconcile-by-code). povTag/salience/pinned/personalLine come from the facts the
NPC is the subject of; the shared canonical episode remains the single factual
authority. An NPC with no personal fact in an episode gets no POV row (it is still
recallable via the canonical ledger + witnessIds); POV rows are the personal,
salience-ranked, proactively-surfaced layer.

The maps below are the R7 formula. They are tunable knobs, not model output.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

# How the acting NPC HOLDS a memory, by the salient fact kind they are subject of.
KIND_TO_POVTAG: Dict[str, str] = {
    "near_death": "traumatic",
    "sacrifice": "protective",
    "rescue": "proud",
    "protect": "protective",
    "defeat": "triumphant",
    "victory": "triumphant",
    "defeat_suffered": "grieving",
    "loss": "grieving",
    "betrayal": "resentful",
    "discovery": "proud",
    "vow": "longing",
    "first_meeting": "amused",
    "reunion": "tender",
    "bond": "tender",
    "tender": "tender",
    "gift": "tender",
    "joke": "amused",
    "habit": "amused",
    "fear": "afraid",
    "vulnerability": "afraid",
    "confession": "smitten",
}

# Emotional weight of a fact kind -> feeds salience + which dominant fact wins.
KIND_WEIGHT: Dict[str, float] = {
    "near_death": 1.0, "sacrifice": 1.0, "betrayal": 1.0, "confession": 1.0, "first_meeting": 1.0,
    "rescue": 0.7, "protect": 0.7, "loss": 0.7, "vow": 0.7, "reunion": 0.7, "defeat_suffered": 0.7,
    "tender": 0.5, "gift": 0.5, "bond": 0.5, "discovery": 0.5, "victory": 0.5, "defeat": 0.5,
    "joke": 0.3, "habit": 0.3, "fear": 0.3, "vulnerability": 0.3,
}
_DEFAULT_WEIGHT = 0.3

# Peak beats that are ALWAYS pinned (never age out), regardless of salience.
ALWAYS_PIN = frozenset({"near_death", "sacrifice", "betrayal", "confession", "first_meeting"})

PIN_THRESHOLD = 0.6
_W_INTENSITY = 0.5
_W_KIND = 0.5


def _kind_weight(kind: Any) -> float:
    return KIND_WEIGHT.get(kind, _DEFAULT_WEIGHT)


def derive_pov_episodes(episode: Mapping[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Return {npcId: [povEpisode]} for each witness that has >=1 personal fact.

    salienceScore = w_intensity * episode.intensity + w_kind * dominant kind weight.
    pinned = salience >= PIN_THRESHOLD OR any of the NPC's facts is an always-pin peak.
    povTag/personalLine come from the NPC's highest-weight fact.
    """
    episode_id = episode.get("episodeId")
    if not isinstance(episode_id, str):
        return {}
    try:
        intensity = max(0.0, min(1.0, float(episode.get("intensity", 0.0))))
    except (TypeError, ValueError):
        intensity = 0.0

    facts_by_npc: Dict[str, List[Mapping[str, Any]]] = {}
    for fact in episode.get("salientFacts", []) or []:
        if not isinstance(fact, Mapping):
            continue
        subject = fact.get("subject")
        npc_id = subject.get("id") if isinstance(subject, Mapping) else None
        if isinstance(npc_id, str) and npc_id:
            facts_by_npc.setdefault(npc_id, []).append(fact)

    out: Dict[str, List[Dict[str, Any]]] = {}
    for npc_id, facts in facts_by_npc.items():
        dominant = max(facts, key=lambda f: _kind_weight(f.get("kind")))
        dom_kind = dominant.get("kind")
        salience = round(
            min(1.0, _W_INTENSITY * intensity + _W_KIND * _kind_weight(dom_kind)), 4
        )
        pinned = salience >= PIN_THRESHOLD or any(
            f.get("kind") in ALWAYS_PIN for f in facts
        )
        out[npc_id] = [
            {
                "episodeId": episode_id,
                "povTag": KIND_TO_POVTAG.get(dom_kind, "amused"),
                "salienceScore": salience,
                "pinned": bool(pinned),
                "personalLine": str(dominant.get("oneLine", ""))[:160],
                "linkedEvidenceIds": [],
            }
        ]
    return out
