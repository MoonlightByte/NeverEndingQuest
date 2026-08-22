"""OOC packet assembly, accepted-boundary persistence, and private context."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from core.npc.voice_packets import compose_out_of_combat_packet
from core.npc.voice_packets import compose_combat_packet
from core.npc.relationship_store import (
    RelationshipStore,
    game_day_ordinal,
    normalize_identity_seed,
)
from core.npc.voice_contracts import NEGATIVE_AFFINITY_EVENT_TYPES
from core.npc.voice_selection import (
    SelectionFairness,
    rank_ooc_candidates,
    resolve_ooc_mention,
)
from core.npc.voice_service import NpcVoiceBatch, NpcVoiceService


_LOGGER = logging.getLogger(__name__)
_DEFAULT_SERVICE: Optional[NpcVoiceService] = None
_OOC_FAIRNESS = SelectionFairness()
_PRIVATE_BLOCK_PREFIX = "Private NPC intentions for the Dungeon Master only."


@dataclass(frozen=True)
class CombatVoiceStage:
    """One request-local combat batch and its exact actor-ID T096 view."""

    batch: NpcVoiceBatch
    intents: Mapping[str, Mapping[str, str]]


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _batch_id(conversation_prefix: Iterable[Any], raw_input: str) -> str:
    payload = json.dumps(
        {"prefix": list(conversation_prefix), "input": raw_input},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()[:32]


def _raw_player_text(content: Any) -> str:
    if not isinstance(content, str):
        return ""
    if not content.startswith("Dungeon Master Note:"):
        return content.strip()
    marker = " Player: "
    if marker not in content:
        return ""
    value = content.rsplit(marker, 1)[1]
    cutoffs = [
        index
        for index in (
            value.find("\n[Inventory Context:"),
            value.find("\n[SRD CONTEXT"),
        )
        if index >= 0
    ]
    if cutoffs:
        value = value[: min(cutoffs)]
    return value.strip()


def _source_turn_witnessed(user_content: Any, npc_name: str) -> bool:
    """Read presence only from the engine-authored party field in a DM note."""
    if not isinstance(user_content, str) or not user_content.startswith(
        "Dungeon Master Note:"
    ):
        return True
    marker = "Party NPCs: "
    end_marker = " Party stats:"
    start = user_content.find(marker)
    end = user_content.find(end_marker, start + len(marker))
    if start < 0 or end < 0:
        return True
    roster_text = user_content[start + len(marker) : end]
    return "%s (" % npc_name in roster_text


def _accepted_evidence_summary(
    conversation_prefix: Iterable[Any], npc_name: str
) -> tuple[str, bool, str]:
    """Return the latest completed player/DM pair without sentiment parsing."""
    messages = list(conversation_prefix)
    for assistant_index in range(len(messages) - 1, -1, -1):
        assistant = messages[assistant_index]
        if not isinstance(assistant, dict) or assistant.get("role") != "assistant":
            continue
        assistant_content = assistant.get("content")
        if not isinstance(assistant_content, str):
            continue
        try:
            parsed = json.loads(assistant_content)
            narration = parsed.get("narration", "") if isinstance(parsed, dict) else ""
        except (TypeError, ValueError):
            narration = assistant_content
        narration = _string(narration)
        if not narration:
            continue
        for user_index in range(assistant_index - 1, -1, -1):
            user = messages[user_index]
            if not isinstance(user, dict) or user.get("role") != "user":
                continue
            user_content = user.get("content")
            player_text = _raw_player_text(user_content)
            if not player_text or player_text.startswith("Error Note:"):
                continue
            summary = "Player: %s Result: %s" % (player_text, narration)
            return (
                summary[:240].rstrip(),
                _source_turn_witnessed(user_content, npc_name),
                player_text,
            )
        return "", True, ""
    return "", True, ""


def _accepted_legacy_combat_evidence_summary(
    conversation_prefix: Iterable[Any],
) -> str:
    """Return the latest accepted legacy T045 pair, never the current turn."""
    messages = list(conversation_prefix)
    player_marker = "--- PLAYER ACTION ---"
    required_marker = "--- REQUIRED RESPONSE ---"
    for assistant_index in range(len(messages) - 1, -1, -1):
        assistant = messages[assistant_index]
        if not isinstance(assistant, Mapping) or assistant.get("role") != "assistant":
            continue
        assistant_content = assistant.get("content")
        if not isinstance(assistant_content, str):
            continue
        try:
            parsed = json.loads(assistant_content)
            narration = parsed.get("narration", "") if isinstance(parsed, Mapping) else ""
        except (TypeError, ValueError):
            narration = ""
        narration = _string(narration)
        if not narration:
            continue
        for user_index in range(assistant_index - 1, -1, -1):
            user = messages[user_index]
            if not isinstance(user, Mapping) or user.get("role") != "user":
                continue
            content = user.get("content")
            if not isinstance(content, str):
                break
            if player_marker not in content or required_marker not in content:
                break
            player_text = content.split(player_marker, 1)[1]
            player_text = player_text.split(required_marker, 1)[0].strip()
            if not player_text or player_text.startswith(
                "System combat continuation:"
            ):
                break
            return ("Player: %s Result: %s" % (player_text, narration))[
                :240
            ].rstrip()
    return ""


def _packet_recent_events(records: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result = []
    for record in records:
        event_type = record.get("eventType")
        if event_type is None:
            continue
        magnitude = int(record.get("magnitude", 0) or 0)
        if event_type in NEGATIVE_AFFINITY_EVENT_TYPES:
            magnitude = -magnitude
        result.append(
            {
                "actor": record.get("actor", ""),
                "target": record.get("target", ""),
                "eventType": event_type,
                "magnitude": magnitude,
                "witnessed": bool(record.get("witnessed")),
                "summary": record.get("summary", ""),
            }
        )
        if len(result) >= 3:
            break
    return result


def _is_eligible_sheet(sheet: Mapping[str, Any]) -> bool:
    unavailable = " ".join(
        (
            _string(sheet.get("status")),
            _string(sheet.get("condition")),
        )
    ).casefold()
    return not any(
        marker in unavailable
        for marker in ("dead", "defeated", "unconscious")
    )


def _sidecar_identity_inactive(
    store: RelationshipStore, npc_name: str, sheet_path: str
) -> bool:
    """Honor an exact persisted inactive identity even if a stale roster lists it."""
    normalized_path = normalize_identity_seed(sheet_path)
    matches = []
    for identity in store.snapshot().get("identities", {}).values():
        if not isinstance(identity, Mapping) or identity.get("kind") != "npc":
            continue
        names = {identity.get("displayName"), *identity.get("aliases", [])}
        if (
            normalize_identity_seed(identity.get("sheetPath", "")) == normalized_path
            or npc_name in names
        ):
            matches.append(identity)
    return len(matches) == 1 and matches[0].get("active") is False


def _canonical_packet_profile(
    sheet: Mapping[str, Any], stored: Optional[Mapping[str, Any]]
) -> Dict[str, Any]:
    profile = {
        "background": _string(sheet.get("background")),
        "personality": _string(
            sheet.get("personality_traits") or sheet.get("personality")
        ),
        "ideals": _string(sheet.get("ideals")),
        "bonds": _string(sheet.get("bonds")),
        "flaws": _string(sheet.get("flaws")),
    }
    if isinstance(stored, Mapping):
        for key in (
            "voice", "goals", "fears", "values", "preferences", "boundaries",
            "conflictStyle", "initiativeTendency", "riskTolerance",
            "protectionPriorities", "retreatRules", "arcSeeds",
        ):
            if key in stored:
                profile[key] = copy.deepcopy(stored[key])
    return profile


def _utilities(sheet: Mapping[str, Any]) -> list[str]:
    result = []
    skills = sheet.get("skills")
    if isinstance(skills, dict):
        result.extend(_string(name) for name in skills if _string(name))
    elif isinstance(skills, list):
        result.extend(_string(name) for name in skills if _string(name))
    languages = sheet.get("languages")
    if isinstance(languages, list):
        result.extend("Speaks %s" % _string(name) for name in languages if _string(name))
    return result[:8]


def _items(sheet: Mapping[str, Any]) -> list[str]:
    result = []
    equipment = sheet.get("equipment")
    if not isinstance(equipment, list):
        return result
    for item in equipment:
        if isinstance(item, dict):
            name = _string(item.get("item_name") or item.get("name"))
        else:
            name = _string(item)
        if name:
            result.append(name)
        if len(result) >= 8:
            break
    return result


def _combat_capabilities(sheet: Mapping[str, Any]) -> list[str]:
    """Render bounded sheet mechanics without claiming that any are legal now."""
    result = []
    for field in (
        "attacksAndSpellcasting",
        "actions",
        "specialAbilities",
        "classFeatures",
        "spellcasting",
    ):
        value = sheet.get(field)
        if isinstance(value, Mapping):
            values = value.values()
        elif isinstance(value, list):
            values = value
        else:
            values = ()
        for entry in values:
            if isinstance(entry, Mapping):
                name = _string(
                    entry.get("name")
                    or entry.get("actionName")
                    or entry.get("spellName")
                )
                detail = _string(
                    entry.get("description")
                    or entry.get("damage")
                    or entry.get("effect")
                )
                rendered = ": ".join(value for value in (name, detail) if value)
            else:
                rendered = _string(entry)
            if rendered and rendered not in result:
                result.append(rendered[:240])
            if len(result) >= 8:
                return result
    return result


def _combat_fact_text(
    fact: Mapping[str, Any], names_by_id: Mapping[str, str]
) -> str:
    action = _string(fact.get("action")) or "an action"
    event_id = _string(fact.get("eventId"))
    event_tag = (
        hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:12]
        if event_id
        else ""
    )
    details = []
    for target in fact.get("targets", []) if isinstance(fact.get("targets"), list) else []:
        if not isinstance(target, Mapping):
            continue
        target_name = names_by_id.get(
            _string(target.get("targetId")), _string(target.get("targetId"))
        ) or "a combatant"
        delta = target.get("hpDelta")
        status = _string(target.get("statusAfter"))
        if type(delta) is int:
            details.append("%s HP %+d" % (target_name, delta))
        elif status:
            details.append("%s status %s" % (target_name, status))
    rendered = "%s%s" % (
        action,
        "; " + ", ".join(details) if details else "",
    )
    return "event %s: %s" % (event_tag, rendered) if event_tag else rendered


def _committed_combat_facts(encounter_data: Mapping[str, Any]) -> list[str]:
    creatures = encounter_data.get("creatures", [])
    names_by_id = {
        _string(creature.get("combatantId")): _string(creature.get("name"))
        for creature in creatures
        if isinstance(creature, Mapping)
    }
    activity = (encounter_data.get("combatState") or {}).get(
        "narrationActivity", {}
    )
    if not isinstance(activity, Mapping):
        return []
    rendered = []
    for actor_id in sorted(activity):
        row = activity.get(actor_id)
        if not isinstance(row, Mapping):
            continue
        actor_name = names_by_id.get(actor_id, actor_id)
        facts = row.get("recentFacts", [])
        if not isinstance(facts, list):
            continue
        for fact in facts[-3:]:
            if isinstance(fact, Mapping):
                rendered.append(
                    "%s committed %s." % (
                        actor_name,
                        _combat_fact_text(fact, names_by_id),
                    )
                )
    return rendered[-8:]


def _committed_player_evidence(
    encounter_data: Mapping[str, Any],
    *,
    player: Mapping[str, Any],
    player_id: str,
    npc: Mapping[str, Any],
    npc_id: str,
) -> Optional[Dict[str, Any]]:
    """Return only a previously committed player fact involving this NPC."""
    activity = (encounter_data.get("combatState") or {}).get(
        "narrationActivity", {}
    )
    row = activity.get(player.get("combatantId"), {}) if isinstance(activity, Mapping) else {}
    facts = row.get("recentFacts", []) if isinstance(row, Mapping) else []
    names_by_id = {
        _string(creature.get("combatantId")): _string(creature.get("name"))
        for creature in encounter_data.get("creatures", [])
        if isinstance(creature, Mapping)
    }
    for fact in reversed(facts if isinstance(facts, list) else []):
        if not isinstance(fact, Mapping):
            continue
        targets = fact.get("targets", [])
        if not any(
            isinstance(target, Mapping)
            and target.get("targetId") == npc.get("combatantId")
            for target in targets if isinstance(targets, list)
        ):
            continue
        return {
            "actorId": player_id,
            "actor": _string(player.get("name")),
            "targetId": npc_id,
            "target": _string(npc.get("name")),
            "summary": (
                "%s committed %s." % (
                    _string(player.get("name")),
                    _combat_fact_text(fact, names_by_id),
                )
            )[:240],
            "witnessed": True,
        }
    return None


def _present_actor_names(
    tracker: Mapping[str, Any], player_name: str, npc_name: str
) -> list[str]:
    ordered = [player_name, npc_name]
    for roster_npc in tracker.get("partyNPCs", []):
        if isinstance(roster_npc, dict):
            ordered.append(_string(roster_npc.get("name")))
    result = []
    for name in ordered:
        if name and name not in result:
            result.append(name)
        if len(result) >= 12:
            break
    return result


def build_ooc_packet_for_turn(
    *,
    party_tracker_data: Mapping[str, Any],
    player_name: str,
    raw_input: str,
    location_data: Optional[Mapping[str, Any]],
    conversation_prefix: Iterable[Any],
    path_manager: Any,
    json_loader: Callable[[str], Optional[Dict[str, Any]]] = _load_json,
    relationship_store: Optional[RelationshipStore] = None,
    _selected_candidate: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compose one eligible packet; raw player text is never prose-gated."""
    roster = party_tracker_data.get("partyNPCs", [])
    if not isinstance(roster, list):
        roster = []
    _mentioned_npc, ambiguous_mention = resolve_ooc_mention(roster, raw_input)
    store = relationship_store or RelationshipStore()
    selected = None
    selected_sheet = None
    selected_path = None
    candidate_order = (
        [dict(_selected_candidate)]
        if isinstance(_selected_candidate, Mapping)
        else rank_ooc_candidates(roster, raw_input)
    )
    for candidate in candidate_order:
        name = _string(candidate.get("name"))
        if not name:
            continue
        path = path_manager.get_character_path(name)
        sheet = json_loader(path)
        if not isinstance(sheet, dict) or not _is_eligible_sheet(sheet):
            continue
        sheet_name = _string(sheet.get("name")) or name
        if _sidecar_identity_inactive(store, sheet_name, path):
            continue
        selected = candidate
        selected_sheet = sheet
        selected_path = path
        break
    if selected is None or selected_sheet is None or selected_path is None:
        raise ValueError("no eligible active party NPC")

    npc_name = _string(selected_sheet.get("name")) or _string(selected.get("name"))
    role = _string(selected.get("role")) or "party companion"
    player_path = path_manager.get_character_path(player_name)
    world = party_tracker_data.get("worldConditions", {})
    if not isinstance(world, dict):
        world = {}
    location = location_data if isinstance(location_data, dict) else {}
    location_name = (
        _string(world.get("currentLocation"))
        or _string(location.get("name"))
        or "Unknown location"
    )
    location_id = _string(world.get("currentLocationId")) or "unknown"
    module = _string(party_tracker_data.get("module")) or "Unknown module"
    current_game_day = game_day_ordinal(world)
    npc_id = store.ensure_identity(
        kind="npc",
        display_name=npc_name,
        sheet_path=selected_path,
        module=module,
        location_id=location_id,
        active=None,
    )
    player_id = store.ensure_identity(
        kind="player",
        display_name=player_name,
        sheet_path=player_path,
        module=module,
        location_id=location_id,
    )
    store.migrate_legacy_identity(
        npc_id,
        player_id,
        game_day=current_game_day,
    )
    relationship_state = store.get_relationship(
        npc_id,
        player_id,
        game_day=current_game_day,
    )
    retrieved_evidence = store.retrieve_evidence(
        npc_id,
        player_id,
        present_actor_ids=(npc_id, player_id),
        entity_ids=(),
    )
    scene_id = "%s|%s" % (module, location_id)
    stored_working = store.get_working(npc_id, scene_id=scene_id)
    accepted_summary, accepted_witnessed, accepted_player_text = (
        _accepted_evidence_summary(conversation_prefix, npc_name)
    )
    _accepted_mention, accepted_mention_ambiguous = resolve_ooc_mention(
        roster, accepted_player_text
    )
    beat_evidence = None
    accepted_matches_selected = (
        _accepted_mention is None
        or _string(_accepted_mention.get("name")) == _string(selected.get("name"))
    )
    if (
        accepted_summary
        and not ambiguous_mention
        and not accepted_mention_ambiguous
        and accepted_matches_selected
    ):
        beat_evidence = {
            "actorId": player_id,
            "actor": player_name,
            "targetId": npc_id,
            "target": npc_name,
            "summary": accepted_summary,
            "witnessed": accepted_witnessed,
        }

    stored_profile = store.get_profile(npc_id)
    profile = _canonical_packet_profile(selected_sheet, stored_profile)
    structured_goals = (
        list(profile.get("goals", [])) if isinstance(profile.get("goals"), list) else []
    )
    arc_seeds = (
        list(profile.get("arcSeeds", []))
        if isinstance(profile.get("arcSeeds"), list)
        else []
    )
    goals = list(dict.fromkeys(
        structured_goals
        + arc_seeds[:1]
        + [profile["bonds"], profile["ideals"], role]
    ))
    goals = [goal for goal in goals if goal]
    location_description = _string(location.get("description"))
    social_context = location_description or (
        "%s is present with the party at %s." % (npc_name, location_name)
    )
    packet = compose_out_of_combat_packet(
        beat={
            "id": _batch_id(conversation_prefix, raw_input),
            "summary": raw_input,
            # Only the prior accepted player/DM pair is committed evidence.
            # The current declaration remains summary/context only.
            "relationshipEvidence": beat_evidence,
        },
        npc={
            "id": npc_id,
            "name": npc_name,
            "role": role,
            "profile": profile,
        },
        relationship={
            "counterpartyId": player_id,
            "counterpartyName": player_name,
            "state": relationship_state["current"],
            "recentEvents": _packet_recent_events(retrieved_evidence),
        },
        scene={
            "module": module,
            "locationId": location_id,
            "location": location_name,
            "presentActors": _present_actor_names(
                party_tracker_data, player_name, npc_name
            ),
            "stakes": raw_input,
            "recentEvents": [],
        },
        working={
            "currentGoal": goals[0] if goals else "",
            "priorPrivateIntent": stored_working.get("currentPrivateIntent", ""),
            "openQuestion": stored_working.get("openQuestion", ""),
            "moodTags": stored_working.get("moodTags", []),
            "expiresAfterTurn": stored_working.get("expiresAfterTurn"),
        },
        utilities=_utilities(selected_sheet),
        items=_items(selected_sheet),
        social_context=social_context,
        current_goals=goals[:5],
    )
    return packet


def build_ooc_packets_for_turn(
    *,
    party_tracker_data: Mapping[str, Any],
    player_name: str,
    raw_input: str,
    location_data: Optional[Mapping[str, Any]],
    conversation_prefix: Iterable[Any],
    path_manager: Any,
    json_loader: Callable[[str], Optional[Dict[str, Any]]] = _load_json,
    relationship_store: Optional[RelationshipStore] = None,
    fairness: Optional[SelectionFairness] = None,
    limit: int = 4,
) -> tuple[Dict[str, Any], ...]:
    """Compose and deterministically rank up to four eligible OOC packets."""
    roster = party_tracker_data.get("partyNPCs", [])
    if not isinstance(roster, list):
        return ()
    prefix = list(conversation_prefix)
    store = relationship_store or RelationshipStore()
    packets_by_id: Dict[str, Dict[str, Any]] = {}
    ranked_inputs = []
    evidence_npc_ids = set()
    for candidate in roster:
        if not isinstance(candidate, Mapping):
            continue
        try:
            packet = build_ooc_packet_for_turn(
                party_tracker_data=party_tracker_data,
                player_name=player_name,
                raw_input=raw_input,
                location_data=location_data,
                conversation_prefix=prefix,
                path_manager=path_manager,
                json_loader=json_loader,
                relationship_store=store,
                _selected_candidate=candidate,
            )
        except Exception:
            continue
        npc_id = packet["npc"]["id"]
        packets_by_id[npc_id] = packet
        ranked_inputs.append(
            {
                "name": _string(candidate.get("name")) or packet["npc"]["name"],
                "role": candidate.get("role", ""),
                "npcId": npc_id,
            }
        )
        if packet["beat"]["relationshipEvidence"] is not None:
            evidence_npc_ids.add(npc_id)

    ranked = rank_ooc_candidates(
        ranked_inputs,
        raw_input,
        evidence_npc_ids=evidence_npc_ids,
        fairness=fairness or _OOC_FAIRNESS,
        limit=min(4, max(0, int(limit))),
    )
    return tuple(packets_by_id[candidate["npcId"]] for candidate in ranked)


def build_combat_packets_for_window(
    *,
    encounter_data: Mapping[str, Any],
    actor_ids: Iterable[str],
    character_paths: Mapping[str, str],
    context_sheets: Mapping[str, Mapping[str, Any]],
    party_tracker_data: Mapping[str, Any],
    location_info: Optional[Mapping[str, Any]],
    player_input: str,
    legacy_conversation_prefix: Optional[Iterable[Any]] = None,
    relationship_store: Optional[RelationshipStore] = None,
) -> tuple[tuple[str, Dict[str, Any]], ...]:
    """Compose packets for exact pending-window party NPC combatant IDs only."""
    actor_window = list(dict.fromkeys(_string(value) for value in actor_ids if _string(value)))
    if not actor_window:
        return ()
    creatures = [
        creature
        for creature in encounter_data.get("creatures", [])
        if isinstance(creature, Mapping)
    ]
    creatures_by_id = {
        _string(creature.get("combatantId")): creature for creature in creatures
    }
    player = next(
        (creature for creature in creatures if creature.get("type") == "player"),
        None,
    )
    if player is None:
        return ()
    roster = party_tracker_data.get("partyNPCs", [])
    roster_by_name = {
        _string(row.get("name")): row
        for row in roster
        if isinstance(row, Mapping) and _string(row.get("name"))
    } if isinstance(roster, list) else {}
    if not roster_by_name:
        return ()

    store = relationship_store or RelationshipStore()
    legacy_prefix = (
        list(legacy_conversation_prefix)
        if legacy_conversation_prefix is not None
        else None
    )
    world = party_tracker_data.get("worldConditions", {})
    if not isinstance(world, Mapping):
        world = {}
    module = _string(party_tracker_data.get("module")) or "Unknown module"
    location = location_info if isinstance(location_info, Mapping) else {}
    location_id = _string(world.get("currentLocationId")) or "unknown"
    location_name = (
        _string(world.get("currentLocation"))
        or _string(location.get("name"))
        or "Unknown location"
    )
    game_day = game_day_ordinal(world)
    player_name = _string(player.get("name"))
    player_path = character_paths.get(player_name, player_name)
    player_id = store.ensure_identity(
        kind="player",
        display_name=player_name,
        sheet_path=str(player_path),
        module=module,
        location_id=location_id,
    )
    stable_present_ids = [player_id]
    committed_facts = _committed_combat_facts(encounter_data)
    state = encounter_data.get("combatState", {})
    revision = state.get("revision", 0) if isinstance(state, Mapping) else 0
    round_number = state.get("round", 1) if isinstance(state, Mapping) else 1
    scene_id = "%s|%s|combat" % (module, location_id)
    present_names = [
        _string(creature.get("name"))
        for creature in creatures
        if _string(creature.get("name"))
        and _string(creature.get("status") or "alive").casefold()
        not in {"dead", "defeated"}
    ][:12]
    threats = [
        {
            "name": _string(creature.get("name")) or "Unknown threat",
            "position": _string(creature.get("position")) or "in the encounter",
            "intent": _string((creature.get("actions") or {}).get("actionType"))
            if isinstance(creature.get("actions"), Mapping)
            else "",
        }
        for creature in creatures
        if creature.get("type") == "enemy" or creature.get("faction") == "hostile"
    ]
    for threat in threats:
        if not threat["intent"]:
            threat["intent"] = "oppose the party"

    packets = []
    for actor_id in actor_window:
        creature = creatures_by_id.get(actor_id)
        if (
            not isinstance(creature, Mapping)
            or creature.get("type") != "npc"
            or _string(creature.get("name")) not in roster_by_name
        ):
            continue
        npc_name = _string(creature.get("name"))
        sheet = context_sheets.get(npc_name)
        sheet_path = character_paths.get(npc_name)
        if not isinstance(sheet, Mapping) or not sheet_path:
            continue
        if _sidecar_identity_inactive(store, npc_name, str(sheet_path)):
            continue
        npc_id = store.ensure_identity(
            kind="npc",
            display_name=npc_name,
            sheet_path=str(sheet_path),
            module=module,
            location_id=location_id,
            active=None,
        )
        store.migrate_legacy_identity(npc_id, player_id, game_day=game_day)
        relationship = store.get_relationship(npc_id, player_id, game_day=game_day)
        retrieved = store.retrieve_evidence(
            npc_id,
            player_id,
            present_actor_ids=tuple(stable_present_ids + [npc_id]),
            entity_ids=(),
        )
        working = store.get_working(
            npc_id,
            scene_id=scene_id,
            current_turn=round_number if type(round_number) is int else None,
        )
        evidence = _committed_player_evidence(
            encounter_data,
            player=player,
            player_id=player_id,
            npc=creature,
            npc_id=npc_id,
        )
        if evidence is None and legacy_prefix is not None:
            accepted_summary = _accepted_legacy_combat_evidence_summary(
                legacy_prefix
            )
            if accepted_summary:
                evidence = {
                    "actorId": player_id,
                    "actor": player_name,
                    "targetId": npc_id,
                    "target": npc_name,
                    "summary": accepted_summary,
                    "witnessed": True,
                }
        hp_current = creature.get("currentHitPoints", sheet.get("hitPoints", 1))
        hp_maximum = creature.get("maxHitPoints", sheet.get("maxHitPoints", hp_current))
        hp_current = max(0, int(hp_current)) if isinstance(hp_current, (int, float)) else 0
        hp_maximum = max(1, int(hp_maximum)) if isinstance(hp_maximum, (int, float)) else 1
        armor = creature.get("armorClass", sheet.get("armorClass", 10))
        armor = max(1, min(40, int(armor))) if isinstance(armor, (int, float)) else 10
        conditions = creature.get("conditions", sheet.get("condition_affected", []))
        conditions = conditions if isinstance(conditions, list) else []
        role = _string(roster_by_name[npc_name].get("role")) or "party companion"
        profile = _canonical_packet_profile(sheet, store.get_profile(npc_id))
        structured_goals = (
            list(profile.get("goals", []))
            if isinstance(profile.get("goals"), list)
            else []
        )
        arc_seeds = (
            list(profile.get("arcSeeds", []))
            if isinstance(profile.get("arcSeeds"), list)
            else []
        )
        goals = list(dict.fromkeys(
            structured_goals
            + arc_seeds[:1]
            + [profile["bonds"], profile["ideals"], role]
        ))
        goals = [value for value in goals if value]
        allies = [
            "%s: %s" % (
                _string(other.get("name")),
                _string(other.get("status") or "alive"),
            )
            for other in creatures
            if other.get("combatantId") != actor_id
            and other.get("type") in {"player", "npc"}
            and _string(other.get("name"))
        ][:8]
        stakes = " ".join(
            value
            for value in (
                _string(encounter_data.get("encounterSummary")),
                _string(player_input),
            )
            if value
        ) or "Resolve the current combat window."
        beat_id = "combat:%s:r%s:v%s:%s" % (
            _string(encounter_data.get("encounterId")) or "unknown",
            round_number,
            revision,
            ",".join(actor_window),
        )
        packet = compose_combat_packet(
            beat={
                "id": beat_id[:120],
                "summary": stakes,
                "relationshipEvidence": evidence,
            },
            npc={"id": npc_id, "name": npc_name, "role": role, "profile": profile},
            relationship={
                "counterpartyId": player_id,
                "counterpartyName": player_name,
                "state": relationship["current"],
                "recentEvents": _packet_recent_events(retrieved),
            },
            scene={
                "module": module,
                "locationId": location_id,
                "location": location_name,
                "presentActors": present_names,
                "stakes": stakes,
                "recentEvents": committed_facts[-6:],
            },
            working={
                "currentGoal": goals[0] if goals else "",
                "priorPrivateIntent": working.get("currentPrivateIntent", ""),
                "openQuestion": working.get("openQuestion", ""),
                "moodTags": working.get("moodTags", []),
                "expiresAfterTurn": working.get("expiresAfterTurn"),
            },
            status={
                "hitPoints": {"current": min(hp_current, hp_maximum), "maximum": hp_maximum},
                "armorClass": armor,
                "conditions": conditions,
                "position": _string(creature.get("position")) or "in the encounter",
            },
            capabilities=_combat_capabilities(sheet),
            allies=allies,
            threats=threats,
            last_round_events=committed_facts,
        )
        packets.append((actor_id, packet))
    return tuple(packets)


def legacy_actor_ids_for_turn_window(
    encounter_data: Mapping[str, Any],
    turn_window: Optional[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Resolve a calculated legacy name/ID window to exact combatant IDs."""
    if not isinstance(turn_window, Mapping):
        return ()
    requested = turn_window.get("turn_window")
    if not isinstance(requested, list):
        return ()
    creatures = [
        creature
        for creature in encounter_data.get("creatures", [])
        if isinstance(creature, Mapping)
    ]
    by_id = {
        _string(creature.get("combatantId")): creature
        for creature in creatures
        if _string(creature.get("combatantId"))
    }
    ids_by_name: Dict[str, list[str]] = {}
    for creature in creatures:
        name = _string(creature.get("name"))
        actor_id = _string(creature.get("combatantId"))
        if name and actor_id:
            ids_by_name.setdefault(name, []).append(actor_id)

    actor_ids = []
    for entry in requested:
        if isinstance(entry, Mapping):
            requested_id = _string(entry.get("combatantId"))
            requested_name = _string(entry.get("name"))
        else:
            requested_id = _string(entry)
            requested_name = requested_id
        actor_id = requested_id if requested_id in by_id else ""
        if not actor_id:
            matches = ids_by_name.get(requested_name, [])
            if len(matches) == 1:
                actor_id = matches[0]
        if actor_id and actor_id not in actor_ids:
            actor_ids.append(actor_id)
    return tuple(actor_ids)


def _empty_combat_stage() -> CombatVoiceStage:
    return CombatVoiceStage(
        batch=NpcVoiceBatch(batch_id="", results=()),
        intents=MappingProxyType({}),
    )


def run_combat_voice_stage(
    *,
    recovery_action_name: str,
    encounter_data: Mapping[str, Any],
    actor_ids: Iterable[str],
    character_paths: Mapping[str, str],
    context_sheets: Mapping[str, Mapping[str, Any]],
    party_tracker_data: Mapping[str, Any],
    location_info: Optional[Mapping[str, Any]],
    player_input: str,
    legacy_conversation_prefix: Optional[Iterable[Any]] = None,
    service: Optional[NpcVoiceService] = None,
    relationship_store: Optional[RelationshipStore] = None,
) -> CombatVoiceStage:
    """Run T105 for a fresh/regenerated T096 window and contain all failure."""
    if recovery_action_name not in {"continue", "regenerate_intent"}:
        return _empty_combat_stage()
    try:
        packet_rows = build_combat_packets_for_window(
            encounter_data=encounter_data,
            actor_ids=actor_ids,
            character_paths=character_paths,
            context_sheets=context_sheets,
            party_tracker_data=party_tracker_data,
            location_info=location_info,
            player_input=player_input,
            legacy_conversation_prefix=legacy_conversation_prefix,
            relationship_store=relationship_store,
        )
        if not packet_rows:
            return _empty_combat_stage()
        batch = (service or _default_service()).dispatch_batch(
            [packet for _actor_id, packet in packet_rows]
        ).collect_blocking()
        packets_by_npc_id = {
            packet["npc"]["id"]: packet for _actor_id, packet in packet_rows
        }
        batch = replace(
            batch,
            results=tuple(
                replace(
                    result,
                    relationship_evidence_id=(
                        "combat-evidence:%s" % hashlib.sha256(
                            json.dumps(
                                packets_by_npc_id[result.npc_id]["beat"][
                                    "relationshipEvidence"
                                ],
                                ensure_ascii=True,
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode("ascii")
                        ).hexdigest()
                        if packets_by_npc_id.get(result.npc_id, {}).get("beat", {}).get(
                            "relationshipEvidence"
                        ) is not None
                        else ""
                    ),
                )
                for result in batch.results
            ),
        )
        actor_by_npc_id = {
            packet["npc"]["id"]: actor_id for actor_id, packet in packet_rows
        }
        intents = {}
        for result in batch.results:
            actor_id = actor_by_npc_id.get(result.npc_id)
            if actor_id:
                entry = {"npcName": result.npc_name}
                if result.say:
                    entry["say"] = result.say
                if result.do:
                    entry["do"] = result.do
                if result.want:
                    entry["want"] = result.want
                entry["thought"] = result.thought
                intents[actor_id] = entry
        return CombatVoiceStage(batch=batch, intents=MappingProxyType(intents))
    except Exception as exc:
        _LOGGER.debug("T105 combat stage skipped: %s", type(exc).__name__)
        return _empty_combat_stage()


def run_legacy_combat_voice_stage(
    *,
    encounter_data: Mapping[str, Any],
    turn_window: Optional[Mapping[str, Any]],
    character_paths: Mapping[str, str],
    context_sheets: Mapping[str, Mapping[str, Any]],
    party_tracker_data: Mapping[str, Any],
    location_info: Optional[Mapping[str, Any]],
    player_input: str,
    conversation_prefix: Iterable[Any],
    service: Optional[NpcVoiceService] = None,
    relationship_store: Optional[RelationshipStore] = None,
) -> CombatVoiceStage:
    """Run one fail-open T105 batch for the calculated legacy T045 window."""
    actor_ids = legacy_actor_ids_for_turn_window(encounter_data, turn_window)
    return run_combat_voice_stage(
        recovery_action_name="continue",
        encounter_data=encounter_data,
        actor_ids=actor_ids,
        character_paths=character_paths,
        context_sheets=context_sheets,
        party_tracker_data=party_tracker_data,
        location_info=location_info,
        player_input=player_input,
        legacy_conversation_prefix=conversation_prefix,
        service=service,
        relationship_store=relationship_store,
    )


def commit_accepted_combat_voice_batch(
    batch: Optional[NpcVoiceBatch],
    party_tracker_data: Mapping[str, Any],
    *,
    relationship_store: Optional[RelationshipStore] = None,
) -> int:
    """Apply only validated prior-commit evidence, idempotently and fail-open."""
    return commit_accepted_ooc_voice_batch(
        batch,
        party_tracker_data,
        relationship_store=relationship_store,
    )


def _default_service() -> NpcVoiceService:
    global _DEFAULT_SERVICE
    if _DEFAULT_SERVICE is None:
        _DEFAULT_SERVICE = NpcVoiceService()
    return _DEFAULT_SERVICE


def run_ooc_voice_stage(
    *,
    party_tracker_data: Mapping[str, Any],
    player_name: str,
    raw_input: str,
    location_data: Optional[Mapping[str, Any]],
    conversation_prefix: Iterable[Any],
    path_manager: Any,
    service: Optional[NpcVoiceService] = None,
    relationship_store: Optional[RelationshipStore] = None,
    fairness: Optional[SelectionFairness] = None,
) -> NpcVoiceBatch:
    """Run one bounded Phase 3 T105 batch and contain every failure."""
    try:
        selection = fairness or _OOC_FAIRNESS
        packets = build_ooc_packets_for_turn(
            party_tracker_data=party_tracker_data,
            player_name=player_name,
            raw_input=raw_input,
            location_data=location_data,
            conversation_prefix=conversation_prefix,
            path_manager=path_manager,
            relationship_store=relationship_store,
            fairness=selection,
        )
        handle = (service or _default_service()).dispatch_batch(packets)
        # Fairness bookkeeping moves to collection time: record_merged runs in
        # inject (below) against what actually merged, not what was dispatched.
        handle._fairness_selection = selection
        return handle
    except Exception as exc:
        _LOGGER.debug("T105 OOC stage skipped: %s", type(exc).__name__)
        return NpcVoiceBatch(batch_id="", results=())


def commit_accepted_ooc_voice_batch(
    batch,
    party_tracker_data: Mapping[str, Any],
    *,
    relationship_store: Optional[RelationshipStore] = None,
) -> int:
    """Commit a staged batch only after T067 validation accepts its candidate.

    Accepts an NpcVoiceBatch or a VoiceBatchHandle; the handle is collected
    non-blocking here, which also captures results that completed while the
    candidate was being validated."""
    if batch is None:
        return 0
    if hasattr(batch, "collect"):
        batch = batch.collect()
    if not batch.results:
        return 0
    store = relationship_store or RelationshipStore()
    world = party_tracker_data.get("worldConditions", {})
    game_day = game_day_ordinal(world if isinstance(world, Mapping) else {})
    committed = 0
    for result in batch.results:
        try:
            if (
                batch.generation_token
                and result.generation_token != batch.generation_token
            ):
                if batch.telemetry is not None:
                    batch.telemetry.record_disposition(
                        "commit",
                        "generation_rejected",
                        batch_id=batch.batch_id,
                        npc_id=result.npc_id,
                    )
                continue
            working = {
                "currentPrivateIntent": result.thought,
                "sourceTurn": result.source_turn_id or batch.batch_id,
                "currentGoalReference": result.current_goal_reference,
                "openQuestion": result.open_question,
                "moodTags": list(result.mood_tags),
                "expiresAfterTurn": result.expires_after_turn,
                "sceneId": result.scene_id,
            }
            if result.affinity_event is not None:
                application = store.apply_event(
                    subject_id=result.npc_id,
                    counterparty_id=result.counterparty_id,
                    event=result.affinity_event,
                    source_turn_id=(
                        result.relationship_evidence_id
                        or result.source_turn_id
                        or batch.batch_id
                    ),
                    evidence_summary=result.relationship_evidence_summary,
                    game_day=game_day,
                    module=result.module,
                    location_id=result.location_id,
                    packet_hash=result.packet_hash,
                    working=working,
                )
                committed += int(application.mutated)
                if batch.telemetry is not None:
                    batch.telemetry.record_disposition(
                        "commit",
                        "duplicate" if application.duplicate else (
                            "applied" if application.mutated else "not_applied"
                        ),
                        batch_id=batch.batch_id,
                        npc_id=result.npc_id,
                    )
            else:
                working_mutated = store.update_working(
                    result.npc_id,
                    source_turn_id=result.source_turn_id or batch.batch_id,
                    thought=result.thought,
                    current_goal_reference=result.current_goal_reference,
                    open_question=result.open_question,
                    mood_tags=result.mood_tags,
                    expires_after_turn=result.expires_after_turn,
                    scene_id=result.scene_id,
                )
                committed += int(working_mutated)
                if batch.telemetry is not None:
                    batch.telemetry.record_disposition(
                        "commit",
                        "working_updated" if working_mutated else "duplicate",
                        batch_id=batch.batch_id,
                        npc_id=result.npc_id,
                    )
        except Exception as exc:
            if batch.telemetry is not None:
                batch.telemetry.record_disposition(
                    "commit",
                    "failure",
                    batch_id=batch.batch_id,
                    npc_id=result.npc_id,
                )
            _LOGGER.debug(
                "T105 accepted event skipped: %s", type(exc).__name__
            )
    return committed


def _voice_row(result):
    """Build one compact advisory row for the DM (null say/do/want omitted)."""
    row = {"npcId": result.npc_id, "npcName": result.npc_name}
    if getattr(result, "say", None):
        row["say"] = result.say
    if getattr(result, "do", None):
        row["do"] = result.do
    if getattr(result, "want", None):
        row["want"] = result.want
    row["thought"] = result.thought
    if getattr(result, "stale", False):
        row["stale"] = True
    return row


def inject_voice_context(messages: list, batch):
    """Insert vector-free private say/do/want/thought without mutating durable messages.

    Accepts an NpcVoiceBatch OR a VoiceBatchHandle: the handle's collect() is
    a NON-BLOCKING poll run here, at inject time -- by now the main DM call
    has overlapped the voice latency, so results are typically ready without
    any deadline ever having existed."""
    if batch is None:
        return messages
    if hasattr(batch, "collect"):
        selection = getattr(batch, "_fairness_selection", None)
        batch = batch.collect()
        if selection is not None:
            try:
                selection.record_merged(r.npc_id for r in batch.results)
            except Exception:
                pass
    if not batch.results:
        return messages
    rows = [_voice_row(result) for result in batch.results]
    block = (
        _PRIVATE_BLOCK_PREFIX + " Each entry is one companion's PROPOSED "
        "characterization for this beat: 'say' is a line they'd speak, 'do' is an "
        "action/intent they'd take, 'want' is their current desire, 'thought' is "
        "their private reasoning. Weave these into your narration in the NPC's "
        "voice, but you own final narration, mechanics, and actions -- reword, "
        "trim, or override anything that does not fit the scene or the rules, and "
        "ignore impossible advice. An entry marked \"stale\":true arrived from the "
        "PREVIOUS beat -- weave it as a delayed reaction or drop it if the moment "
        "passed. Do not expose this private guidance, and never "
        "paste 'say'/'do' verbatim without making it fit. Null fields mean the NPC "
        "offers nothing there.\n"
        + json.dumps(rows, ensure_ascii=True, separators=(",", ":"))
    )
    copied = [dict(message) for message in messages]
    insert_at = len(copied)
    for index in range(len(copied) - 1, -1, -1):
        if copied[index].get("role") == "user":
            insert_at = index
            break
    copied.insert(insert_at, {"role": "system", "content": block})
    return copied


def inject_legacy_combat_voice_context(
    messages: list,
    batch: Optional[NpcVoiceBatch],
):
    """Insert the OOC-format block before the final combat-state message."""
    if batch is None or not batch.results:
        return messages
    copied = inject_voice_context(messages, batch)
    private_index = next(
        (
            index
            for index, message in enumerate(copied)
            if message.get("role") == "system"
            and isinstance(message.get("content"), str)
            and message["content"].startswith(_PRIVATE_BLOCK_PREFIX)
        ),
        None,
    )
    if private_index is None:
        return messages
    private_message = copied.pop(private_index)
    insert_at = next(
        (
            index
            for index in range(len(copied) - 1, -1, -1)
            if copied[index].get("role") == "user"
            and isinstance(copied[index].get("content"), str)
            and "--- PLAYER ACTION ---" in copied[index]["content"]
        ),
        None,
    )
    if insert_at is None:
        return messages
    copied.insert(insert_at, private_message)
    return copied


def redact_voice_context(messages: list):
    """Remove private voice text from ordinary always-on diagnostics."""
    if not any(
        isinstance(message, dict)
        and message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and message["content"].startswith(_PRIVATE_BLOCK_PREFIX)
        for message in messages
    ):
        return messages
    redacted = []
    for message in messages:
        copied = dict(message)
        if (
            copied.get("role") == "system"
            and isinstance(copied.get("content"), str)
            and copied["content"].startswith(_PRIVATE_BLOCK_PREFIX)
        ):
            copied["content"] = "Private NPC guidance: [redacted]"
        redacted.append(copied)
    return redacted
