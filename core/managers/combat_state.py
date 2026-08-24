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
NARRATION_ATTEMPT_STATUSES = frozenset(
    {"rejected", "provider_error", "parse_error", "contract_error"}
)
_NARRATION_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


def valid_pending_delivery(delivery):
    """Return whether a committed narration receipt has the exact safe shape.

    Delivery receipts are new-format transaction data, so there is no legacy
    partial shape to repair. The delivery ID is derived from the turn ID and
    every persisted event needs its own stable identity; accepting anything
    looser risks acknowledging corrupt or colliding output.
    """
    if not isinstance(delivery, dict):
        return False
    turn_id = delivery.get("turnId")
    delivery_id = delivery.get("deliveryId")
    events = delivery.get("events")
    if not isinstance(turn_id, str) or not turn_id:
        return False
    if delivery_id != "combat-turn:%s" % turn_id:
        return False
    if not isinstance(events, list) or not events:
        return False
    event_ids = []
    for event in events:
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("eventId"), str)
            or not event.get("eventId")
            or not isinstance(event.get("actorId"), str)
            or not event.get("actorId")
            or type(event.get("stateVersion")) is not int
            or not isinstance(event.get("intent"), dict)
            or not isinstance(event.get("outcome"), dict)
            or (
                "resources" in event
                and not isinstance(event.get("resources"), list)
            )
            or (
                "effects" in event
                and not isinstance(event.get("effects"), list)
            )
        ):
            return False
        event_ids.append(event["eventId"])
    if len(set(event_ids)) != len(event_ids):
        return False
    for field in ("roundBefore", "roundAfter"):
        if type(delivery.get(field)) is not int or delivery[field] < 1:
            return False
    if not isinstance(delivery.get("historyInput"), str):
        return False
    if not isinstance(delivery.get("displayPrefix"), str):
        return False
    narration = delivery.get("narration")
    if narration is not None and (
        not isinstance(narration, str) or not narration.strip()
    ):
        return False
    fallback = delivery.get("narrationFallback")
    if fallback is not None and not isinstance(fallback, bool):
        return False
    attempts = delivery.get("narrationAttempts", [])
    if not isinstance(attempts, list) or len(attempts) > 12:
        return False
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict) or set(attempt) != {
            "attempt", "status", "candidate", "violations", "warnings"
        }:
            return False
        if attempt.get("attempt") != index:
            return False
        if attempt.get("status") not in NARRATION_ATTEMPT_STATUSES:
            return False
        candidate = attempt.get("candidate")
        if not isinstance(candidate, str) or len(candidate) > 12000:
            return False
        for field in ("violations", "warnings"):
            codes = attempt.get(field)
            if (
                not isinstance(codes, list)
                or len(codes) > 24
                or any(
                    not isinstance(code, str)
                    or not _NARRATION_CODE_RE.fullmatch(code)
                    for code in codes
                )
            ):
                return False
    return True


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


def is_combatant_targetable(creature):
    """Return whether a combatant is alive and remains a legal target."""
    if not isinstance(creature, dict):
        return False
    if normalize_status(creature.get("status")) != ACTIVE_STATUS:
        return False
    hit_points = creature.get("currentHitPoints")
    return not isinstance(hit_points, (int, float)) or hit_points > 0


def is_turn_eligible(creature):
    if not is_combatant_targetable(creature):
        return False
    return creature.get("effectIncapacitated") is not True


def is_hostile(creature):
    return isinstance(creature, dict) and (
        creature.get("faction") == "hostile" or creature.get("type") == "enemy"
    )


def combat_provenance(encounter):
    """Return the accepted combat route, or require recovery for invalid typed state.

    - "typed"     : a new agentic encounter carrying sceneFacts.contractVersion.
    - "pre_typed" : an opted-in agentic encounter from before typed scene facts.
    - "legacy"    : everything else, including every pre-existing encounter.
    - "recovery_required": sceneFacts is present without the supported contract.

    An encounter that lacks all of the new fields is always "legacy" and is
    handled exactly as on origin/main. Absence is never an error and no
    migration is performed: old, completed encounters keep working untouched.
    """
    if not isinstance(encounter, dict):
        return "legacy"
    if "sceneFacts" in encounter:
        scene = encounter.get("sceneFacts")
        if (
            isinstance(scene, dict)
            and scene.get("contractVersion") == "typed-agentic-v1"
        ):
            return "typed"
        return "recovery_required"
    state = encounter.get("combatState")
    if isinstance(state, dict) and state.get("pipelineMode") == "agentic":
        return "pre_typed"
    return "legacy"


def resolve_creature_controller(creature, combat_state=None):
    """Resolve who controls a creature ("human" or "actor_agent").

    Prefers the accepted combatState.controllers entry when present; otherwise
    falls back to the existing type-based rule (player -> human, everything else
    -> actor_agent). Absence-safe: for any encounter without the controller map
    this is byte-identical in effect to today's behavior.
    """
    combatant_id = creature.get("combatantId") if isinstance(creature, dict) else None
    if isinstance(combat_state, dict) and combatant_id is not None:
        controllers = combat_state.get("controllers")
        entry = controllers.get(combatant_id) if isinstance(controllers, dict) else None
        controller = entry.get("controller") if isinstance(entry, dict) else None
        if controller in ("human", "actor_agent"):
            return controller
    if isinstance(creature, dict) and str(creature.get("type") or "").lower() == "player":
        return "human"
    return "actor_agent"


def all_hostiles_resolved(encounter):
    hostiles = [c for c in encounter.get("creatures", []) if is_hostile(c)]
    return bool(hostiles) and all(
        normalize_status(c.get("status")) in RESOLVED_HOSTILE_STATUSES
        or (isinstance(c.get("currentHitPoints"), (int, float)) and c["currentHitPoints"] <= 0)
        for c in hostiles
    )


def player_control_unavailable(encounter):
    """Return whether the encounter's player is physically down.

    A temporary ``effectIncapacitated`` projection means the player loses an
    ordinary action, but combat and the effect clock still have to advance.
    The shipped recovery pause is reserved for a player who is actually at
    zero HP or has a resolved non-active status.
    """
    if combat_provenance(encounter) == "typed":
        state = encounter.get("combatState") or {}
        human_actors = [
            creature
            for creature in encounter.get("creatures", [])
            if isinstance(creature, dict)
            and creature.get("combatantId") in initiative_eligible_ids(encounter)
            and resolve_creature_controller(creature, state) == "human"
        ]
        return bool(human_actors) and all(
            normalize_status(actor.get("status")) != ACTIVE_STATUS
            or (
                isinstance(actor.get("currentHitPoints"), (int, float))
                and actor["currentHitPoints"] <= 0
            )
            for actor in human_actors
        )
    players = [
        creature
        for creature in encounter.get("creatures", [])
        if isinstance(creature, dict) and creature.get("type") == "player"
    ]
    return bool(players) and all(
        normalize_status(player.get("status")) != ACTIVE_STATUS
        or (
            isinstance(player.get("currentHitPoints"), (int, float))
            and player["currentHitPoints"] <= 0
        )
        for player in players
    )


def all_party_resolved(encounter):
    """Return whether every player/NPC combatant is physically down."""
    party = [
        creature
        for creature in encounter.get("creatures", [])
        if isinstance(creature, dict)
        and (creature.get("type") in ("player", "npc") or creature.get("faction") == "party")
    ]
    return bool(party) and all(
        normalize_status(creature.get("status")) != ACTIVE_STATUS
        or (
            isinstance(creature.get("currentHitPoints"), (int, float))
            and creature["currentHitPoints"] <= 0
        )
        for creature in party
    )


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
    eligible_ids = initiative_eligible_ids(encounter)
    ordered = sorted(
        (
            creature
            for creature in encounter["creatures"]
            if creature["combatantId"] in eligible_ids
        ),
        key=lambda creature: (
            -int(creature.get("initiative", 0)),
            -int(creature.get("initiativeTieBreaker", 0)),
            creature["combatantId"],
        ),
    )
    return [creature["combatantId"] for creature in ordered]


def initiative_eligible_ids(encounter):
    """Return the committed initiative membership for this provenance route."""
    creature_ids = {
        creature["combatantId"] for creature in encounter.get("creatures", [])
    }
    if combat_provenance(encounter) != "typed":
        return creature_ids
    scene = encounter.get("sceneFacts") or {}
    return {
        participant.get("combatantId")
        for participant in scene.get("participants", [])
        if isinstance(participant, dict)
        and participant.get("initiativeEligible") is True
        and participant.get("combatantId") in creature_ids
    }


def initiative_ui_projection(encounter):
    """Project initiative order and typed input ownership for UI consumers.

    Legacy encounters retain the existing living-roster/raw-initiative shape.
    Typed encounters are projected strictly from the committed stable ledger;
    observers never appear merely because they are alive, and source ``type``
    never decides who owns the current input window.
    """
    creatures = [
        creature
        for creature in encounter.get("creatures", [])
        if isinstance(creature, dict) and is_combatant_targetable(creature)
    ]
    if combat_provenance(encounter) != "typed":
        return [
            deepcopy(creature)
            for creature in sorted(
                creatures,
                key=lambda creature: creature.get("initiative", 0),
                reverse=True,
            )
        ]

    state = encounter.get("combatState")
    if not isinstance(state, dict):
        return []
    order = state.get("initiativeOrder")
    if not isinstance(order, list):
        return []
    by_id = {
        creature.get("combatantId"): creature
        for creature in creatures
        if isinstance(creature.get("combatantId"), str)
    }
    eligible = initiative_eligible_ids(encounter)
    committed_order = [
        combatant_id
        for combatant_id in order
        if combatant_id in eligible and combatant_id in by_id
    ]

    current_id = None
    if state.get("phase") not in {"complete", "recovery_required"} and committed_order:
        cursor = state.get("turnCursor", 0)
        if type(cursor) is not int:
            cursor = 0
        cursor = max(0, min(cursor, len(committed_order) - 1))
        acted = set(state.get("actedThisRound", []))
        for offset in range(len(committed_order)):
            combatant_id = committed_order[(cursor + offset) % len(committed_order)]
            creature = by_id[combatant_id]
            if combatant_id not in acted and is_turn_eligible(creature):
                current_id = combatant_id
                break

    projection = []
    for combatant_id in committed_order:
        creature = deepcopy(by_id[combatant_id])
        creature["controller"] = resolve_creature_controller(creature, state)
        creature["isCurrent"] = combatant_id == current_id
        projection.append(creature)
    return projection


def _history_marks_encounter(history, encounter_id):
    prefix = "Current Combat Encounter:"
    markers = [
        message.get("content", "").strip()[len(prefix):].strip()
        for message in history
        if isinstance(message, dict)
        and message.get("role") == "system"
        and isinstance(message.get("content"), str)
        and message["content"].strip().startswith(prefix)
    ] if isinstance(history, list) else []
    return bool(markers) and markers[-1] == encounter_id


def activate_encounter(expected_tracker_value, encounter_id, history_marker):
    """Durably publish a prepared typed encounter using conditional activation.

    The complete combat history is written before the tracker can point at the
    encounter.  The short party-transition authority covers the comparison and
    all three writes.  A competing active encounter wins without allowing this
    candidate to replace its history or tracker authority.
    """
    from core.managers.campaign_manager import _party_module_transition_lock
    from utils.encoding_utils import safe_json_load
    from utils.file_operations import safe_write_json

    encounter_id = str(encounter_id or "").strip()
    if not encounter_id or not _history_marks_encounter(history_marker, encounter_id):
        raise CombatStateConflict("Activation requires a full matching combat history")
    expected = str(expected_tracker_value or "").strip()
    encounter_path = "modules/encounters/encounter_%s.json" % encounter_id
    history_path = "modules/conversation_history/combat_conversation_history.json"

    with _party_module_transition_lock():
        tracker = safe_json_load("party_tracker.json")
        encounter = safe_json_load(encounter_path)
        if not isinstance(tracker, dict) or not isinstance(encounter, dict):
            raise CombatStateConflict("Activation authority files are unavailable")
        state = encounter.get("combatState")
        activation = state.get("activation") if isinstance(state, dict) else None
        if (
            combat_provenance(encounter) != "typed"
            or not isinstance(activation, dict)
            or activation.get("encounterId") != encounter_id
        ):
            raise CombatStateConflict("Encounter lacks matching typed activation authority")

        world = tracker.setdefault("worldConditions", {})
        current = str(world.get("activeCombatEncounter") or "").strip()
        if current not in ("", expected, encounter_id):
            activation["status"] = "superseded"
            activation["trackerActivated"] = False
            if not safe_write_json(encounter_path, encounter):
                raise CombatStateConflict("Could not persist superseded activation")
            return False

        # A cleared expected encounter is a legitimate fresh retry. Record the
        # exact value actually compared while authority remains continuously held.
        activation["expectedTrackerEncounterId"] = current or None
        if current != encounter_id:
            if not safe_write_json(history_path, history_marker):
                raise CombatStateConflict("Could not persist combat history before activation")
            world["activeCombatEncounter"] = encounter_id
            if not safe_write_json("party_tracker.json", tracker):
                raise CombatStateConflict("Could not conditionally activate encounter")
        else:
            existing_history = safe_json_load(history_path)
            if not _history_marks_encounter(existing_history, encounter_id):
                if not safe_write_json(history_path, history_marker):
                    raise CombatStateConflict("Could not repair activated combat history")

        activation["status"] = "active"
        activation["historyMarkerEncounterId"] = encounter_id
        activation["trackerActivated"] = True
        if not safe_write_json(encounter_path, encounter):
            raise CombatStateConflict("Could not finalize encounter activation receipt")
        return encounter


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
    state.setdefault("pendingDelivery", None)
    state.setdefault("appliedTurnIds", [])
    state.setdefault("appliedEventIds", [])
    state.setdefault("deliveredDeliveryIds", [])
    state.setdefault("narrationActivity", {})
    state["completion"] = _completion_state(state.get("completion"))

    valid_ids = {c["combatantId"] for c in encounter["creatures"]}
    initiative_ids = initiative_eligible_ids(encounter)
    order = state.get("initiativeOrder")
    if (
        not isinstance(order, list)
        or len(order) != len(initiative_ids)
        or set(order) != initiative_ids
    ):
        state["initiativeOrder"] = canonical_initiative_order(encounter)
        order = state["initiativeOrder"]
    if state.get("phase") not in VALID_PHASES:
        state["phase"] = "recovery_required"
    if state.get("pipelineMode") not in {"legacy", "agentic"}:
        state["phase"] = "recovery_required"
    # Absence-safe typed scene-facts guard: an encounter WITHOUT sceneFacts (every
    # pre-existing/legacy encounter) is untouched here. A present-but-malformed or
    # unknown-version sceneFacts fails closed to recovery rather than being silently
    # misread; only the supported typed contract is accepted.
    scene = encounter.get("sceneFacts")
    if "sceneFacts" in encounter and (
        not isinstance(scene, dict)
        or scene.get("contractVersion") != "typed-agentic-v1"
    ):
        state["phase"] = "recovery_required"
    elif isinstance(scene, dict) and scene.get("contractVersion") == "typed-agentic-v1":
        state.setdefault("recoveryConflict", None)
    if type(state.get("revision")) is not int or state["revision"] < 0:
        state["revision"] = 0
    if type(state.get("round")) is not int or state["round"] < 1:
        state["round"] = legacy_round
    if type(state.get("turnCursor")) is not int:
        state["turnCursor"] = 0
    state["turnCursor"] = max(0, min(state["turnCursor"], max(len(order) - 1, 0)))
    state["actedThisRound"] = list(dict.fromkeys(
        actor_id
        for actor_id in state.get("actedThisRound", [])
        if actor_id in initiative_ids
    ))
    state["appliedTurnIds"] = list(dict.fromkeys(
        str(item) for item in state.get("appliedTurnIds", []) if item
    ))[-200:]
    state["appliedEventIds"] = list(dict.fromkeys(
        str(item) for item in state.get("appliedEventIds", []) if item
    ))[-1000:]
    state["deliveredDeliveryIds"] = list(dict.fromkeys(
        str(item) for item in state.get("deliveredDeliveryIds", []) if item
    ))[-200:]
    if not isinstance(state.get("narrationActivity"), dict):
        state["narrationActivity"] = {}

    delivery = state.get("pendingDelivery")
    if delivery is not None and not valid_pending_delivery(delivery):
        state["phase"] = "recovery_required"
        state["pauseReason"] = "invalid_combat_delivery_receipt"

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
        if stop_after_player and _current_controller(encounter, creature) == "human":
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
        if _current_controller(encounter, creature) == "human":
            break
        result.append(actor_id)
    return result


def expected_player_window_ids(encounter):
    """Return the next human-controlled turn and the remaining round window."""
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
            if _current_controller(encounter, creature) != "human":
                return []
            found_player = True
        result.append(actor_id)
    return result


def _current_controller(encounter, creature):
    state = encounter.get("combatState") if isinstance(encounter, dict) else None
    return resolve_creature_controller(creature, state)


def _skipped_actor_ids_through_window(encounter, actor_ids):
    """Return already-passed ineligible actors covered by one legal window.

    Incapacitated combatants are omitted from model work, but their initiative
    position still has to be consumed. Persisting that fact with the turn claim
    prevents an effect that ends later in the same transaction from granting a
    retroactive turn or making the round clock tick twice.
    """
    state = ensure_combat_state(encounter)
    order = state["initiativeOrder"]
    if not order:
        return []
    if not actor_ids:
        # A clock-only window is legal only when every unresolved living
        # combatant is temporarily unable to act. Consume those initiative
        # positions so a deterministic duration tick can advance the round.
        return [
            actor_id
            for offset in range(len(order))
            for actor_id in (order[(state["turnCursor"] + offset) % len(order)],)
            if actor_id not in state["actedThisRound"]
            and is_combatant_targetable(combatant_by_id(encounter, actor_id))
            and not is_turn_eligible(combatant_by_id(encounter, actor_id))
        ]
    claimed = set(actor_ids)
    last_actor = actor_ids[-1]
    remaining_eligible = {
        actor_id
        for actor_id in order
        if actor_id not in state["actedThisRound"]
        and actor_id not in claimed
        and is_turn_eligible(combatant_by_id(encounter, actor_id))
    }
    consume_full_round = not remaining_eligible
    skipped = []
    for offset in range(len(order)):
        actor_id = order[(state["turnCursor"] + offset) % len(order)]
        if actor_id in state["actedThisRound"]:
            continue
        if actor_id in claimed:
            if actor_id == last_actor and not consume_full_round:
                break
            continue
        creature = combatant_by_id(encounter, actor_id)
        if creature is None or not is_turn_eligible(creature):
            skipped.append(actor_id)
    return skipped


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
    if state.get("pendingDelivery") is not None:
        raise CombatStateConflict(
            "The previous committed combat turn must be delivered first"
        )
    actor_ids = list(actor_ids)
    legal_windows = [
        window
        for window in (
            expected_automatic_actor_ids(encounter),
            expected_player_window_ids(encounter),
        )
        if window
    ]
    skipped_actor_ids = _skipped_actor_ids_through_window(encounter, actor_ids)
    clock_only = not actor_ids
    if clock_only and (legal_windows or not skipped_actor_ids):
        raise CombatStateConflict(
            "An empty turn is allowed only to advance timed incapacitation"
        )
    if not clock_only and actor_ids not in legal_windows:
        raise CombatStateConflict(
            f"Out-of-order actors: expected one of {legal_windows!r}, received {actor_ids!r}"
        )
    pending = {
        "turnId": turn_id or uuid.uuid4().hex,
        "baseRevision": state["revision"],
        "round": state["round"],
        "actorIds": actor_ids,
        "skippedActorIds": skipped_actor_ids,
        "clockOnly": clock_only,
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
    # A clock-only claim has one engine event and no model actor. It exists
    # solely to durably tick timed effects when every living combatant is
    # temporarily incapacitated.
    if not pending.get("actorIds"):
        if not (
            pending.get("clockOnly") is True
            and len(normalized) == 1
            and normalized[0].get("actorId") == "combat-clock"
            and (normalized[0].get("outcome") or {}).get("kind")
            == "effectClock"
        ):
            raise CombatStateConflict(
                "Clock-only turns require exactly one engine effect-clock event"
            )
        if normalized[0].get("stateVersion") != pending.get("baseRevision"):
            raise CombatStateConflict(
                "The effect-clock event was resolved from a stale combat revision"
            )
        pending["events"] = normalized
        pending["stage"] = "events_staged"
        return pending

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
    consumed_actor_ids = list(pending.get("skippedActorIds") or []) + actor_ids
    for actor_id in consumed_actor_ids:
        if actor_id not in state["actedThisRound"]:
            state["actedThisRound"].append(actor_id)
    round_actor_ids = {
        actor_id
        for actor_id in state["initiativeOrder"]
        if is_combatant_targetable(combatant_by_id(encounter, actor_id))
    }
    if round_actor_ids and round_actor_ids.issubset(set(state["actedThisRound"])):
        state["round"] += 1
        state["actedThisRound"] = []
        state["turnCursor"] = 0
    else:
        last_consumed = (actor_ids or consumed_actor_ids)[-1]
        last_index = state["initiativeOrder"].index(last_consumed)
        state["turnCursor"] = (last_index + 1) % len(state["initiativeOrder"])

    state["appliedTurnIds"] = (state["appliedTurnIds"] + [turn_id])[-200:]
    state["appliedEventIds"] = (state["appliedEventIds"] + staged_ids)[-1000:]
    from core.ai.combat_narration import update_narration_activity

    state["narrationActivity"] = update_narration_activity(
        state.get("narrationActivity"), pending.get("events") or []
    )
    delivery_context = pending.get("deliveryContext")
    if not isinstance(delivery_context, dict):
        delivery_context = {}
    state["pendingDelivery"] = {
        "deliveryId": "combat-turn:%s" % turn_id,
        "turnId": str(turn_id),
        "roundBefore": pending.get("round"),
        "roundAfter": state["round"],
        "events": deepcopy(pending.get("events") or []),
        "historyInput": str(delivery_context.get("historyInput") or "")[:24000],
        "displayPrefix": str(delivery_context.get("displayPrefix") or "")[:4000],
        "narration": None,
        "narrationFallback": None,
        "narrationAttempts": [],
    }
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
    delivery = state.get("pendingDelivery")
    if not pending:
        if valid_pending_delivery(delivery):
            return {
                "action": "deliver_committed_events",
                "pendingDelivery": deepcopy(delivery),
            }
        if delivery is not None:
            return {
                "action": "pause_invalid_delivery",
                "actorIds": [],
                "reason": "invalid_combat_delivery_receipt",
            }
        automatic = expected_automatic_actor_ids(encounter)
        actors = automatic or expected_player_window_ids(encounter)
        if not actors:
            skipped = _skipped_actor_ids_through_window(encounter, [])
            if skipped:
                return {
                    "action": "advance_effect_clock",
                    "actorIds": [],
                    "skippedActorIds": skipped,
                }
        return {"action": "continue", "actorIds": actors}
    conflict = state.get("recoveryConflict")
    if (
        isinstance(conflict, dict)
        and conflict.get("status") == "pending"
    ):
        return {
            "action": "pause_recovery_conflict",
            "pendingTurn": deepcopy(pending),
            "recoveryConflict": deepcopy(conflict),
        }
    if (
        pending.get("clockOnly") is True
        and state.get("phase") == "recovery_required"
        and state.get("pauseReason") == "untimed_total_incapacitation"
    ):
        return {
            "action": "pause_untimed_incapacitation",
            "pendingTurn": deepcopy(pending),
        }
    if pending.get("stage") == "events_staged":
        return {"action": "apply_staged_events", "pendingTurn": deepcopy(pending)}
    return {"action": "regenerate_intent", "pendingTurn": deepcopy(pending)}
