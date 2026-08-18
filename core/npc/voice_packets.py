"""Packet composers for the two T105 context lenses."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional

from core.npc.voice_contracts import (
    PACKET_VERSION,
    TASK_ID,
    ThoughtContractError,
    canonical_json,
    validate_packet,
)


MAX_PACKET_CHARS = 4800


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _text_list(values: Any, count: int, limit: int) -> List[str]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        item = _text(value, limit)
        if item and item not in result:
            result.append(item)
        if len(result) >= count:
            break
    return result


def _normalize_common(packet: Dict[str, Any]) -> None:
    packet["beat"]["id"] = _text(packet["beat"].get("id"), 120)
    packet["beat"]["summary"] = _text(packet["beat"].get("summary"), 800)
    evidence = packet["beat"].get("relationshipEvidence")
    if isinstance(evidence, dict):
        for key, limit in (
            ("actorId", 240),
            ("actor", 100),
            ("targetId", 240),
            ("target", 100),
            ("summary", 240),
        ):
            evidence[key] = _text(evidence.get(key), limit)

    npc = packet["npc"]
    npc["id"] = _text(npc.get("id"), 240)
    npc["name"] = _text(npc.get("name"), 100)
    npc["role"] = _text(npc.get("role"), 160)
    profile = npc["profile"]
    for key, limit in (
        ("background", 800),
        ("personality", 800),
        ("ideals", 400),
        ("bonds", 400),
        ("flaws", 400),
    ):
        profile[key] = _text(profile.get(key), limit)
    structured_voice = profile.get("voice")
    if isinstance(structured_voice, dict):
        structured_voice["cadence"] = _text(structured_voice.get("cadence"), 120)
        structured_voice["diction"] = _text(structured_voice.get("diction"), 120)
        structured_voice["taboos"] = _text_list(
            structured_voice.get("taboos"), 3, 80
        )
    for key, count, limit in (
        ("goals", 3, 180),
        ("fears", 3, 180),
        ("values", 5, 120),
        ("preferences", 5, 120),
        ("boundaries", 5, 160),
        ("protectionPriorities", 3, 120),
        ("retreatRules", 3, 160),
        ("arcSeeds", 2, 180),
    ):
        if key in profile:
            profile[key] = _text_list(profile.get(key), count, limit)
    if "conflictStyle" in profile:
        profile["conflictStyle"] = _text(profile.get("conflictStyle"), 160)

    relationship = packet["relationship"]
    relationship["counterpartyId"] = _text(
        relationship.get("counterpartyId"), 240
    )
    relationship["counterpartyName"] = _text(
        relationship.get("counterpartyName"), 100
    )
    recent_events = relationship.get("recentEvents", [])[:3]
    for event in recent_events:
        if isinstance(event, dict):
            event["actor"] = _text(event.get("actor"), 100)
            event["target"] = _text(event.get("target"), 100)
            event["summary"] = _text(event.get("summary"), 240)
    relationship["recentEvents"] = recent_events

    scene = packet["scene"]
    scene["module"] = _text(scene.get("module"), 160)
    scene["locationId"] = _text(scene.get("locationId"), 120)
    scene["location"] = _text(scene.get("location"), 240)
    scene["presentActors"] = _text_list(scene.get("presentActors"), 12, 100)
    scene["stakes"] = _text(scene.get("stakes"), 500)
    scene["recentEvents"] = _text_list(scene.get("recentEvents"), 6, 400)

    working = packet["working"]
    working["currentGoal"] = _text(working.get("currentGoal"), 300)
    working["priorPrivateIntent"] = _text(
        working.get("priorPrivateIntent"), 300
    )
    working["openQuestion"] = _text(working.get("openQuestion"), 240)
    working["moodTags"] = _text_list(working.get("moodTags"), 4, 60)


def _shrink_longest(packet: Dict[str, Any]) -> bool:
    candidates = [
        (packet["npc"]["profile"], "background", 80),
        (packet["npc"]["profile"], "personality", 80),
        (packet["context"], "socialContext", 80),
        (packet["npc"]["profile"], "ideals", 40),
        (packet["npc"]["profile"], "bonds", 40),
        (packet["npc"]["profile"], "flaws", 40),
    ]
    available = [entry for entry in candidates if len(entry[0].get(entry[1], "")) > entry[2]]
    if not available:
        return False
    container, key, minimum = max(
        available,
        key=lambda entry: (len(entry[0][entry[1]]), entry[1]),
    )
    value = container[key]
    new_length = max(minimum, len(value) - max(32, len(value) // 4))
    container[key] = value[:new_length].rstrip()
    return True


def _fit_packet(packet: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
    if max_chars <= 0:
        raise ThoughtContractError("packet character budget must be positive")
    while len(canonical_json(packet)) > max_chars:
        if packet["scene"]["recentEvents"]:
            packet["scene"]["recentEvents"].pop(0)
        elif packet["relationship"]["recentEvents"]:
            packet["relationship"]["recentEvents"].pop()
        elif packet["mode"] == "OUT_OF_COMBAT" and packet["context"]["items"]:
            packet["context"]["items"].pop()
        elif packet["mode"] == "OUT_OF_COMBAT" and packet["context"]["utilities"]:
            packet["context"]["utilities"].pop()
        elif packet["mode"] == "COMBAT" and packet["context"]["lastRoundEvents"]:
            packet["context"]["lastRoundEvents"].pop(0)
        elif not _shrink_longest(packet):
            raise ThoughtContractError("packet exceeds the T105 input budget")
    return validate_packet(packet)


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
        packet["context"].get("utilities"), 8, 240
    )
    packet["context"]["items"] = _text_list(
        packet["context"].get("items"), 8, 240
    )
    packet["context"]["socialContext"] = _text(
        packet["context"].get("socialContext"), 800
    )
    packet["context"]["currentGoals"] = _text_list(
        packet["context"].get("currentGoals"), 5, 300
    )
    budget = MAX_PACKET_CHARS if max_chars is None else max_chars
    return _fit_packet(packet, budget)


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
        packet["context"].get("capabilities"), 8, 240
    )
    packet["context"]["allies"] = _text_list(
        packet["context"].get("allies"), 8, 240
    )
    packet["context"]["lastRoundEvents"] = _text_list(
        packet["context"].get("lastRoundEvents"), 8, 320
    )
    threats_result = []
    for threat in packet["context"].get("threats", [])[:8]:
        if not isinstance(threat, dict):
            continue
        threats_result.append(
            {
                "name": _text(threat.get("name"), 100),
                "position": _text(threat.get("position"), 160),
                "intent": _text(threat.get("intent"), 240),
            }
        )
    packet["context"]["threats"] = threats_result
    budget = MAX_PACKET_CHARS if max_chars is None else max_chars
    return _fit_packet(packet, budget)
