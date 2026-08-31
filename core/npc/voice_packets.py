"""Packet composers for the two T105 context lenses."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional

from core.npc.voice_contracts import (
    PACKET_VERSION,
    TASK_ID,
    validate_packet,
)


def _text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _text_list(values: Any, count: int) -> List[str]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        item = _text(value)
        if item and item not in result:
            result.append(item)
        if len(result) >= count:
            break
    return result


def _normalize_common(packet: Dict[str, Any]) -> None:
    packet["beat"]["id"] = _text(packet["beat"].get("id"))
    packet["beat"]["summary"] = _text(packet["beat"].get("summary"))
    evidence = packet["beat"].get("relationshipEvidence")
    if isinstance(evidence, dict):
        for key in ("actorId", "actor", "targetId", "target", "summary"):
            evidence[key] = _text(evidence.get(key))

    npc = packet["npc"]
    npc["id"] = _text(npc.get("id"))
    npc["name"] = _text(npc.get("name"))
    npc["role"] = _text(npc.get("role"))
    profile = npc["profile"]
    for key in ("background", "personality", "ideals", "bonds", "flaws"):
        profile[key] = _text(profile.get(key))
    structured_voice = profile.get("voice")
    if isinstance(structured_voice, dict):
        structured_voice["cadence"] = _text(structured_voice.get("cadence"))
        structured_voice["diction"] = _text(structured_voice.get("diction"))
        structured_voice["taboos"] = _text_list(
            structured_voice.get("taboos"), 3
        )
    for key, count in (
        ("goals", 3),
        ("fears", 3),
        ("values", 5),
        ("preferences", 5),
        ("boundaries", 5),
        ("protectionPriorities", 3),
        ("retreatRules", 3),
        ("arcSeeds", 2),
    ):
        if key in profile:
            profile[key] = _text_list(profile.get(key), count)
    if "conflictStyle" in profile:
        profile["conflictStyle"] = _text(profile.get("conflictStyle"))

    relationship = packet["relationship"]
    relationship["counterpartyId"] = _text(relationship.get("counterpartyId"))
    relationship["counterpartyName"] = _text(relationship.get("counterpartyName"))
    recent_events = relationship.get("recentEvents", [])[:3]
    for event in recent_events:
        if isinstance(event, dict):
            event["actor"] = _text(event.get("actor"))
            event["target"] = _text(event.get("target"))
            event["summary"] = _text(event.get("summary"))
    relationship["recentEvents"] = recent_events

    scene = packet["scene"]
    scene["module"] = _text(scene.get("module"))
    scene["locationId"] = _text(scene.get("locationId"))
    scene["location"] = _text(scene.get("location"))
    scene["presentActors"] = _text_list(scene.get("presentActors"), 12)
    scene["stakes"] = _text(scene.get("stakes"))
    scene["recentEvents"] = _text_list(scene.get("recentEvents"), 6)

    working = packet["working"]
    working["currentGoal"] = _text(working.get("currentGoal"))
    working["priorPrivateIntent"] = _text(working.get("priorPrivateIntent"))
    working["openQuestion"] = _text(working.get("openQuestion"))
    working["moodTags"] = _text_list(working.get("moodTags"), 4)


def _base_packet(
    mode: str,
    beat: Mapping[str, Any],
    npc: Mapping[str, Any],
    relationship: Mapping[str, Any],
    scene: Mapping[str, Any],
    working: Mapping[str, Any],
) -> Dict[str, Any]:
    packet = {
        "contractVersion": PACKET_VERSION,
        "taskId": TASK_ID,
        "mode": mode,
        "beat": copy.deepcopy(dict(beat)),
        "npc": copy.deepcopy(dict(npc)),
        "relationship": copy.deepcopy(dict(relationship)),
        "scene": copy.deepcopy(dict(scene)),
        "working": copy.deepcopy(dict(working)),
    }
    return packet


def compose_out_of_combat_packet(
    *,
    beat: Mapping[str, Any],
    npc: Mapping[str, Any],
    relationship: Mapping[str, Any],
    scene: Mapping[str, Any],
    working: Mapping[str, Any],
    utilities: List[str],
    items: List[str],
    social_context: str,
    current_goals: List[str],
    max_chars: Optional[int] = None,
) -> Dict[str, Any]:
    packet = _base_packet(
        "OUT_OF_COMBAT", beat, npc, relationship, scene, working
    )
    packet["context"] = {
        "utilities": copy.deepcopy(utilities),
        "items": copy.deepcopy(items),
        "socialContext": social_context,
        "currentGoals": copy.deepcopy(current_goals),
    }
    _normalize_common(packet)
    packet["context"]["utilities"] = _text_list(
        packet["context"].get("utilities"), 8
    )
    packet["context"]["items"] = _text_list(
        packet["context"].get("items"), 8
    )
    packet["context"]["socialContext"] = _text(
        packet["context"].get("socialContext")
    )
    packet["context"]["currentGoals"] = _text_list(
        packet["context"].get("currentGoals"), 5
    )
    return validate_packet(packet)


def compose_combat_packet(
    *,
    beat: Mapping[str, Any],
    npc: Mapping[str, Any],
    relationship: Mapping[str, Any],
    scene: Mapping[str, Any],
    working: Mapping[str, Any],
    status: Mapping[str, Any],
    capabilities: List[str],
    allies: List[str],
    threats: List[Mapping[str, Any]],
    last_round_events: List[str],
    max_chars: Optional[int] = None,
) -> Dict[str, Any]:
    packet = _base_packet("COMBAT", beat, npc, relationship, scene, working)
    packet["context"] = {
        "status": copy.deepcopy(dict(status)),
        "capabilities": copy.deepcopy(capabilities),
        "allies": copy.deepcopy(allies),
        "threats": copy.deepcopy(threats),
        "lastRoundEvents": copy.deepcopy(last_round_events),
    }
    _normalize_common(packet)
    packet["context"]["capabilities"] = _text_list(
        packet["context"].get("capabilities"), 8
    )
    packet["context"]["allies"] = _text_list(
        packet["context"].get("allies"), 8
    )
    packet["context"]["lastRoundEvents"] = _text_list(
        packet["context"].get("lastRoundEvents"), 8
    )
    threats_result = []
    for threat in packet["context"].get("threats", [])[:8]:
        if not isinstance(threat, dict):
            continue
        threats_result.append(
            {
                "name": _text(threat.get("name")),
                "position": _text(threat.get("position")),
                "intent": _text(threat.get("intent")),
            }
        )
    packet["context"]["threats"] = threats_result
    return validate_packet(packet)
