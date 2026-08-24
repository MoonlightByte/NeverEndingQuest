"""Typed combat-scene reconciliation at the model/code authority boundary.

The model proposes semantic participation, control, relationships, objectives,
and disclosure.  This module accepts only exact participant keys from a
canonical snapshot and returns persistence-ready values; it performs no I/O.
"""

from __future__ import annotations


CONTRACT_VERSION = "typed-agentic-v1"
PARTICIPATION_VALUES = {"active", "observer", "hidden", "unaware", "departed"}
PERSISTENCE_VALUES = {"encounter", "canonical_character", "owner_gated_companion"}
CONTROLLER_VALUES = {"human", "actor_agent"}
CONTROLLER_SCOPE_VALUES = {"encounter", "turn", "temporary", "persistent"}
OBJECTIVE_STATUS_VALUES = {"active", "satisfied", "failed", "abandoned"}


class SceneReconciliationError(ValueError):
    """A scene proposal cannot be reconciled to exact canonical identities."""


def _require_object(value, label):
    if not isinstance(value, dict):
        raise SceneReconciliationError(f"{label} must be an object")
    return value


def _require_list(value, label):
    if not isinstance(value, list):
        raise SceneReconciliationError(f"{label} must be a list")
    return value


def _require_string(value, label):
    if not isinstance(value, str) or not value:
        raise SceneReconciliationError(f"{label} must be a non-empty string")
    return value


def _canonical_index(canonical_snapshot):
    canonical = {}
    combatant_ids = set()
    for index, raw in enumerate(_require_list(canonical_snapshot, "canonical snapshot")):
        item = _require_object(raw, f"canonical participant {index}")
        key = _require_string(item.get("participantKey"), "canonical participantKey")
        combatant_id = _require_string(item.get("combatantId"), "canonical combatantId")
        if key in canonical:
            raise SceneReconciliationError(f"duplicate canonical participantKey: {key}")
        if combatant_id in combatant_ids:
            raise SceneReconciliationError(f"duplicate canonical combatantId: {combatant_id}")
        canonical[key] = {
            "combatantId": combatant_id,
            "sourceKind": _require_string(item.get("sourceKind"), "canonical sourceKind"),
            "sourceRef": _require_string(item.get("sourceRef"), "canonical sourceRef"),
            "displayName": _require_string(item.get("displayName"), "canonical displayName"),
        }
        combatant_ids.add(combatant_id)
    if not canonical:
        raise SceneReconciliationError("canonical snapshot must contain participants")
    return canonical


def _participant_id(key, canonical, label):
    if key not in canonical:
        raise SceneReconciliationError(f"{label} references unknown participant key: {key}")
    return canonical[key]["combatantId"]


def reconcile_scene_manifest(parameters, canonical_snapshot):
    """Reconcile one T067 scene proposal against exact canonical participants."""
    params = _require_object(parameters, "createEncounter parameters")
    scene = _require_object(params.get("scene"), "scene")
    canonical = _canonical_index(canonical_snapshot)

    proposed_by_key = {}
    for index, raw in enumerate(_require_list(scene.get("participants"), "scene participants")):
        item = _require_object(raw, f"scene participant {index}")
        key = _require_string(item.get("participantKey"), "scene participantKey")
        if key in proposed_by_key:
            raise SceneReconciliationError(f"duplicate scene participantKey: {key}")
        proposed_by_key[key] = item
    if set(proposed_by_key) != set(canonical):
        raise SceneReconciliationError("scene participant keys must exactly match canonical participant keys")

    participants = []
    controllers = {}
    for key, source in canonical.items():
        proposal = proposed_by_key[key]
        participation = proposal.get("participation")
        persistence = proposal.get("persistence")
        controller = proposal.get("controller")
        if participation not in PARTICIPATION_VALUES:
            raise SceneReconciliationError(f"invalid participation for {key}")
        if type(proposal.get("initiativeEligible")) is not bool:
            raise SceneReconciliationError(f"initiativeEligible must be boolean for {key}")
        if persistence not in PERSISTENCE_VALUES:
            raise SceneReconciliationError(f"invalid persistence for {key}")
        if controller not in CONTROLLER_VALUES:
            raise SceneReconciliationError(f"invalid controller for {key}")
        scope = proposal.get("controllerScope", "encounter")
        if scope not in CONTROLLER_SCOPE_VALUES:
            raise SceneReconciliationError(f"invalid controller scope for {key}")
        expires_at = proposal.get("controllerExpiresAtRevision")
        if expires_at is not None and (type(expires_at) is not int or expires_at < 0):
            raise SceneReconciliationError(f"invalid controller expiry for {key}")

        combatant_id = source["combatantId"]
        participants.append(
            {
                **source,
                "participation": participation,
                "initiativeEligible": proposal["initiativeEligible"],
                "persistence": persistence,
            }
        )
        controllers[combatant_id] = {
            "controller": controller,
            "revision": 0,
            "cause": proposal.get("controllerCause", "initial_scene"),
            "scope": scope,
            "expiresAtRevision": expires_at,
            "consentEventId": proposal.get("consentEventId"),
        }

    relations = []
    for index, raw in enumerate(_require_list(scene.get("relations"), "scene relations")):
        item = _require_object(raw, f"scene relation {index}")
        relations.append(
            {
                "relationId": f"scene-relation-{index + 1}",
                "subjectId": _participant_id(item.get("subjectKey"), canonical, "relation subject"),
                "objectId": _participant_id(item.get("objectKey"), canonical, "relation object"),
                "disposition": _require_string(item.get("disposition"), "relation disposition"),
                "revision": 0,
            }
        )

    objectives = []
    for index, raw in enumerate(_require_list(scene.get("objectives"), "scene objectives")):
        item = _require_object(raw, f"scene objective {index}")
        status = item.get("status", "active")
        if status not in OBJECTIVE_STATUS_VALUES:
            raise SceneReconciliationError(f"invalid objective status at index {index}")
        objectives.append(
            {
                "objectiveId": f"scene-objective-{index + 1}",
                "ownerIds": [
                    _participant_id(key, canonical, "objective owner")
                    for key in _require_list(item.get("ownerKeys"), "objective ownerKeys")
                ],
                "kind": _require_string(item.get("kind"), "objective kind"),
                "targetIds": [
                    _participant_id(key, canonical, "objective target")
                    for key in _require_list(item.get("targetKeys"), "objective targetKeys")
                ],
                "status": status,
            }
        )

    grants = []
    for index, raw in enumerate(_require_list(scene.get("disclosureGrants"), "disclosure grants")):
        item = _require_object(raw, f"disclosure grant {index}")
        fact_paths = _require_list(item.get("factPaths"), "disclosure factPaths")
        if any(not isinstance(path, str) or not path for path in fact_paths):
            raise SceneReconciliationError("disclosure factPaths must contain non-empty strings")
        grants.append(
            {
                "grantId": f"scene-disclosure-{index + 1}",
                "observerId": _participant_id(item.get("observerKey"), canonical, "disclosure observer"),
                "factPaths": list(fact_paths),
                "sceneRevision": 0,
                "status": "active",
            }
        )

    return {
        "sceneFacts": {
            "contractVersion": CONTRACT_VERSION,
            "revision": 0,
            "participants": participants,
            "relations": relations,
            "objectives": objectives,
            "disclosureGrants": grants,
        },
        "controllers": controllers,
    }


def validate_scene_proposal_shape(parameters):
    """Validate the typed proposal before canonical files are loaded.

    This validates only exact structure and positional references. The builder
    later replaces these placeholders with authoritative canonical sources and
    runs the same reconciliation boundary again before persistence.
    """
    params = _require_object(parameters, "createEncounter parameters")
    player = _require_string(params.get("player"), "createEncounter player")
    npcs = _require_list(params.get("npcs"), "createEncounter npcs")
    monsters = _require_list(params.get("monsters"), "createEncounter monsters")
    if any(not isinstance(name, str) or not name for name in npcs + monsters):
        raise SceneReconciliationError("createEncounter participant arrays require non-empty strings")

    placeholder = [
        {
            "participantKey": "player:0",
            "combatantId": "proposal-player-0",
            "sourceKind": "character",
            "sourceRef": f"proposal:player:{player}",
            "displayName": player,
        }
    ]
    placeholder.extend(
        {
            "participantKey": f"npc:{index}",
            "combatantId": f"proposal-npc-{index}",
            "sourceKind": "character",
            "sourceRef": f"proposal:npc:{index}",
            "displayName": name,
        }
        for index, name in enumerate(npcs)
    )
    placeholder.extend(
        {
            "participantKey": f"monster:{index}",
            "combatantId": f"proposal-monster-{index}",
            "sourceKind": "monster",
            "sourceRef": f"proposal:monster:{index}",
            "displayName": name,
        }
        for index, name in enumerate(monsters)
    )
    reconcile_scene_manifest(params, placeholder)


def validate_typed_encounter_actions(response):
    """Reject incomplete typed encounter actions before any stateful handler runs."""
    payload = _require_object(response, "DM response")
    actions = _require_list(payload.get("actions"), "DM response actions")
    for index, raw_action in enumerate(actions):
        if not isinstance(raw_action, dict) or raw_action.get("action") != "createEncounter":
            continue
        parameters = _require_object(
            raw_action.get("parameters"),
            f"createEncounter action {index} parameters",
        )
        expected_keys = ["player:0"]
        expected_keys.extend(
            f"npc:{position}"
            for position, _ in enumerate(parameters.get("npcs", []))
        )
        expected_keys.extend(
            f"monster:{position}"
            for position, _ in enumerate(parameters.get("monsters", []))
        )
        try:
            validate_scene_proposal_shape(parameters)
        except SceneReconciliationError as exc:
            keys = ", ".join(expected_keys)
            raise SceneReconciliationError(
                f"{exc}. Use participant keys exactly [{keys}]. scene must contain "
                "participants, relations, objectives, and disclosureGrants arrays. "
                "Every participant requires participantKey, participation, "
                "initiativeEligible boolean, persistence, and controller. "
                "participation is one of active, observer, hidden, unaware, departed; "
                "persistence is one of encounter, canonical_character, "
                "owner_gated_companion; controller is human or actor_agent. "
                "Each relation is {subjectKey, objectKey, disposition}. Each objective "
                "is {ownerKeys array, kind, targetKeys array, status}; status is active, "
                "satisfied, failed, or abandoned. Each disclosure grant is "
                "{observerKey, factPaths array}. Empty arrays are valid."
            ) from exc
