# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Deterministic, persisted combat sequencing and recovery primitives.

Models may propose and narrate combat actions.  This module is the authority
for actor identity, initiative progression, rounds, duplicate prevention, and
the durable boundary around an in-progress turn.
"""

import re
import uuid
from copy import deepcopy


COMBAT_STATE_VERSION = 1
ACTIVE_STATUS = "alive"
RESOLVED_HOSTILE_STATUSES = frozenset({"dead", "defeated", "unconscious"})
VALID_PHASES = frozenset(
    {"initializing", "awaiting_actor", "resolving_turn", "complete", "recovery_required"}
)


class CombatStateConflict(ValueError):
    """Raised when stale or out-of-order work attempts to mutate combat."""


def _slug(value):
    value = re.sub(r"[^a-z0-9]+", "-", str(value or "unknown").lower()).strip("-")
    return value or "unknown"


def normalize_status(value):
    status = str(value or ACTIVE_STATUS).strip().lower()
    return {
        "destroyed": "dead",
        "fled": "defeated",
        "fleeing": "defeated",
        "dying": "unconscious",
        "panicked": "alive",
    }.get(status, status)


def is_turn_eligible(creature):
    if not isinstance(creature, dict):
        return False
    if normalize_status(creature.get("status")) != ACTIVE_STATUS:
        return False
    hit_points = creature.get("currentHitPoints")
    return not isinstance(hit_points, (int, float)) or hit_points > 0


def is_hostile(creature):
    return isinstance(creature, dict) and (
        creature.get("faction") == "hostile" or creature.get("type") == "enemy"
    )


def all_hostiles_resolved(encounter):
    hostiles = [c for c in encounter.get("creatures", []) if is_hostile(c)]
    return bool(hostiles) and all(
        normalize_status(c.get("status")) in RESOLVED_HOSTILE_STATUSES
        or (isinstance(c.get("currentHitPoints"), (int, float)) and c["currentHitPoints"] <= 0)
        for c in hostiles
    )


def player_control_unavailable(encounter):
    """Return whether the encounter's player cannot take an ordinary turn."""
    players = [
        creature
        for creature in encounter.get("creatures", [])
        if isinstance(creature, dict) and creature.get("type") == "player"
    ]
    return bool(players) and all(not is_turn_eligible(player) for player in players)


def all_party_resolved(encounter):
    """Return whether every player/NPC combatant has been taken out."""
    party = [
        creature
        for creature in encounter.get("creatures", [])
        if isinstance(creature, dict)
        and (creature.get("type") in ("player", "npc") or creature.get("faction") == "party")
    ]
    return bool(party) and all(not is_turn_eligible(creature) for creature in party)


def ensure_combatant_ids(encounter):
    """Upgrade a roster with persisted unique IDs and deterministic tie breaks."""
    if not isinstance(encounter, dict):
        raise ValueError("Encounter must be an object")
    creatures = encounter.get("creatures")
    if not isinstance(creatures, list) or not creatures:
        raise ValueError("Encounter requires at least one creature")

    used = set()
    counters = {}
    for index, creature in enumerate(creatures):
        if not isinstance(creature, dict):
            raise ValueError("Every combatant must be an object")
        role = str(creature.get("type") or "creature").lower()
        base = f"cmb-{role}-{_slug(creature.get('name'))}"
        combatant_id = creature.get("combatantId")
        if combatant_id:
            combatant_id = str(combatant_id)
            if combatant_id in used:
                raise ValueError(f"Duplicate combatantId: {combatant_id}")
        else:
            counters[base] = counters.get(base, 0) + 1
            combatant_id = f"{base}-{counters[base]}"
            while combatant_id in used:
                counters[base] += 1
                combatant_id = f"{base}-{counters[base]}"
            creature["combatantId"] = combatant_id
        used.add(combatant_id)
        creature.setdefault("faction", "hostile" if role == "enemy" else "party")
        creature.setdefault("initiativeTieBreaker", len(creatures) - index)
    return encounter


def combatant_by_id(encounter, combatant_id):
    return next(
        (c for c in encounter.get("creatures", []) if c.get("combatantId") == combatant_id),
        None,
    )


def canonical_initiative_order(encounter):
    ensure_combatant_ids(encounter)
    ordered = sorted(
        encounter["creatures"],
        key=lambda creature: (
            -int(creature.get("initiative", 0)),
            -int(creature.get("initiativeTieBreaker", 0)),
            creature["combatantId"],
        ),
    )
    return [creature["combatantId"] for creature in ordered]


def _completion_state(existing=None):
    completion = deepcopy(existing) if isinstance(existing, dict) else {}
    completion.setdefault("recordId", uuid.uuid4().hex)
    completion.setdefault("status", "active")
    completion.setdefault("rewardsApplied", False)
    completion.setdefault("summaryPublished", False)
    completion.setdefault("transcriptArchived", False)
    return completion


def ensure_combat_state(encounter, new_encounter=False, pipeline_mode=None):
    """Add/repair backward-compatible combat metadata in memory."""
    ensure_combatant_ids(encounter)
    legacy_round = encounter.get("combat_round", encounter.get("current_round", 1))
    if type(legacy_round) is not int or legacy_round < 1:
        legacy_round = 1

    state = encounter.get("combatState")
    if not isinstance(state, dict):
        state = {}
    state.setdefault("version", COMBAT_STATE_VERSION)
    requested_mode = pipeline_mode if pipeline_mode in {"legacy", "agentic"} else None
    state.setdefault(
        "pipelineMode",
        requested_mode if new_encounter and requested_mode else "legacy",
    )
    state.setdefault("revision", 0)
    state.setdefault("phase", "initializing" if new_encounter else "awaiting_actor")
    state.setdefault("round", legacy_round)
    state.setdefault("initiativeOrder", canonical_initiative_order(encounter))
    state.setdefault("turnCursor", 0)
    state.setdefault("actedThisRound", [])
    state.setdefault("pendingTurn", None)
    state.setdefault("appliedTurnIds", [])
    state.setdefault("appliedEventIds", [])
    state["completion"] = _completion_state(state.get("completion"))

    valid_ids = {c["combatantId"] for c in encounter["creatures"]}
    order = state.get("initiativeOrder")
    if not isinstance(order, list) or len(order) != len(valid_ids) or set(order) != valid_ids:
        state["initiativeOrder"] = canonical_initiative_order(encounter)
        order = state["initiativeOrder"]
    if state.get("phase") not in VALID_PHASES:
        state["phase"] = "recovery_required"
    if state.get("pipelineMode") not in {"legacy", "agentic"}:
        state["phase"] = "recovery_required"
    if type(state.get("revision")) is not int or state["revision"] < 0:
        state["revision"] = 0
    if type(state.get("round")) is not int or state["round"] < 1:
        state["round"] = legacy_round
    if type(state.get("turnCursor")) is not int:
        state["turnCursor"] = 0
    state["turnCursor"] = max(0, min(state["turnCursor"], max(len(order) - 1, 0)))
    state["actedThisRound"] = list(dict.fromkeys(
        actor_id for actor_id in state.get("actedThisRound", []) if actor_id in valid_ids
    ))
    state["appliedTurnIds"] = list(dict.fromkeys(
        str(item) for item in state.get("appliedTurnIds", []) if item
    ))[-200:]
    state["appliedEventIds"] = list(dict.fromkeys(
        str(item) for item in state.get("appliedEventIds", []) if item
    ))[-1000:]

    encounter["combatState"] = state
    encounter["combat_round"] = state["round"]
    encounter["current_round"] = state["round"]
    return state


def expected_actor_ids(encounter, stop_after_player=True):
    """Return the exact eligible sequence starting at the durable cursor."""
    state = ensure_combat_state(encounter)
    order = state["initiativeOrder"]
    if not order:
        return []
    result = []
    for offset in range(len(order)):
        actor_id = order[(state["turnCursor"] + offset) % len(order)]
        if actor_id in state["actedThisRound"]:
            continue
        creature = combatant_by_id(encounter, actor_id)
        if not creature or not is_turn_eligible(creature):
            continue
        result.append(actor_id)
        if stop_after_player and creature.get("type") == "player":
            break
    return result


def expected_automatic_actor_ids(encounter):
    """Return only NPC/enemy turns before control must return to the player."""
    state = ensure_combat_state(encounter)
    order = state["initiativeOrder"]
    result = []
    for offset in range(len(order)):
        actor_id = order[(state["turnCursor"] + offset) % len(order)]
        if actor_id in state["actedThisRound"]:
            continue
        creature = combatant_by_id(encounter, actor_id)
        if not creature or not is_turn_eligible(creature):
            continue
        if creature.get("type") == "player":
            break
        result.append(actor_id)
    return result


def expected_player_window_ids(encounter):
    """Return the player's turn followed by all remaining turns this round."""
    state = ensure_combat_state(encounter)
    order = state["initiativeOrder"]
    result = []
    found_player = False
    for offset in range(len(order)):
        actor_id = order[(state["turnCursor"] + offset) % len(order)]
        if actor_id in state["actedThisRound"]:
            continue
        creature = combatant_by_id(encounter, actor_id)
        if not creature or not is_turn_eligible(creature):
            continue
        if not found_player:
            if creature.get("type") != "player":
                return []
            found_player = True
        result.append(actor_id)
    return result


def begin_turn(encounter, actor_ids, turn_id=None, expected_revision=None):
    """Persist a recoverable turn claim before any model or mechanical work."""
    state = ensure_combat_state(encounter)
    if expected_revision is not None and expected_revision != state["revision"]:
        raise CombatStateConflict("Combat changed before this turn could begin")
    if state.get("pendingTurn"):
        pending = state["pendingTurn"]
        if turn_id and pending.get("turnId") == turn_id:
            return pending
        raise CombatStateConflict("Another combat turn is already pending recovery")
    actor_ids = list(actor_ids)
    if not actor_ids:
        raise CombatStateConflict("A turn must contain at least one eligible actor")
    legal_windows = [
        window
        for window in (
            expected_automatic_actor_ids(encounter),
            expected_player_window_ids(encounter),
        )
        if window
    ]
    if actor_ids not in legal_windows:
        raise CombatStateConflict(
            f"Out-of-order actors: expected one of {legal_windows!r}, received {actor_ids!r}"
        )
    pending = {
        "turnId": turn_id or uuid.uuid4().hex,
        "baseRevision": state["revision"],
        "round": state["round"],
        "actorIds": actor_ids,
        "stage": "intent_pending",
        "events": [],
    }
    state["pendingTurn"] = pending
    state["phase"] = "resolving_turn"
    return pending


def stage_turn_events(encounter, turn_id, events):
    """Durably attach proposed deterministic events before committing them."""
    state = ensure_combat_state(encounter)
    pending = state.get("pendingTurn")
    if not pending or pending.get("turnId") != turn_id:
        raise CombatStateConflict("No matching pending turn")
    if pending.get("baseRevision") != state["revision"]:
        raise CombatStateConflict("Pending turn was based on stale combat state")
    event_ids = []
    normalized = []
    for event in events:
        if not isinstance(event, dict) or not event.get("eventId"):
            raise ValueError("Every combat event requires an eventId")
        event_id = str(event["eventId"])
        if event_id in event_ids:
            raise ValueError(f"Duplicate eventId in turn: {event_id}")
        event_ids.append(event_id)
        normalized.append(deepcopy(event))
    # Every still-capable actor needs exactly one event in initiative order.
    # An earlier event may defeat a later actor before that actor's turn; that
    # actor is then legitimately absent instead of receiving a fabricated turn.
    pending_actor_ids = pending.get("actorIds") or []
    event_index = 0
    rendered_ineligible = set()
    for actor_id in pending_actor_ids:
        if (
            event_index < len(normalized)
            and normalized[event_index].get("actorId") == actor_id
        ):
            event = normalized[event_index]
            event_index += 1
            for target in (event.get("outcome") or {}).get("targets", []) or []:
                if (
                    target.get("hpAfter") == 0
                    or normalize_status(target.get("statusAfter"))
                    in RESOLVED_HOSTILE_STATUSES
                ):
                    rendered_ineligible.add(target.get("combatantId"))
        elif actor_id not in rendered_ineligible:
            raise CombatStateConflict(
                "Staged events omitted a pending actor that remained eligible"
            )
    if event_index != len(normalized):
        raise CombatStateConflict(
            "Staged events include an actor outside the pending initiative order"
        )
    if any(
        event.get("stateVersion") != pending.get("baseRevision")
        for event in normalized
    ):
        raise CombatStateConflict(
            "Staged events were resolved from a stale combat revision"
        )
    pending["events"] = normalized
    pending["stage"] = "events_staged"
    return pending


def commit_turn(encounter, turn_id, applied_event_ids):
    """Advance once after callers atomically apply the staged event effects."""
    state = ensure_combat_state(encounter)
    if turn_id in state["appliedTurnIds"]:
        return state
    pending = state.get("pendingTurn")
    if not pending or pending.get("turnId") != turn_id:
        raise CombatStateConflict("No matching pending turn to commit")
    staged_ids = [str(event["eventId"]) for event in pending.get("events", [])]
    supplied_ids = [str(event_id) for event_id in applied_event_ids]
    if staged_ids != supplied_ids:
        raise CombatStateConflict("Committed events do not match the staged event sequence")
    duplicate = set(staged_ids).intersection(state["appliedEventIds"])
    if duplicate:
        raise CombatStateConflict(f"Combat events were already applied: {sorted(duplicate)!r}")

    actor_ids = pending["actorIds"]
    for actor_id in actor_ids:
        if actor_id not in state["actedThisRound"]:
            state["actedThisRound"].append(actor_id)
    eligible_ids = {
        c["combatantId"] for c in encounter["creatures"] if is_turn_eligible(c)
    }
    if eligible_ids and eligible_ids.issubset(set(state["actedThisRound"])):
        state["round"] += 1
        state["actedThisRound"] = []
        state["turnCursor"] = 0
    else:
        last_index = state["initiativeOrder"].index(actor_ids[-1])
        state["turnCursor"] = (last_index + 1) % len(state["initiativeOrder"])

    state["appliedTurnIds"] = (state["appliedTurnIds"] + [turn_id])[-200:]
    state["appliedEventIds"] = (state["appliedEventIds"] + staged_ids)[-1000:]
    state["pendingTurn"] = None
    state["revision"] += 1
    if all_hostiles_resolved(encounter):
        state["phase"] = "complete"
        state["completion"]["status"] = "complete"
    else:
        state["phase"] = "awaiting_actor"
    encounter["combat_round"] = state["round"]
    encounter["current_round"] = state["round"]
    return state


def recovery_action(encounter):
    """Describe the only safe action after reconnecting during a pending turn."""
    state = ensure_combat_state(encounter)
    pending = state.get("pendingTurn")
    if not pending:
        automatic = expected_automatic_actor_ids(encounter)
        actors = automatic or expected_player_window_ids(encounter)
        return {"action": "continue", "actorIds": actors}
    if pending.get("stage") == "events_staged":
        return {"action": "apply_staged_events", "pendingTurn": deepcopy(pending)}
    return {"action": "regenerate_intent", "pendingTurn": deepcopy(pending)}
