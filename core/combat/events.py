# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Combat event construction and validation.

A combat event is the single committed record of one resolved intent.
Narration is generated FROM committed events, never the reverse. Events
are staged through core.managers.combat_state.stage_turn_events and made
durable by commit_turn; this module only defines their shape.
"""

import hashlib

REQUIRED_EVENT_FIELDS = ("eventId", "actorId", "intent", "outcome", "stateVersion")

# outcome.targets[] entries carry before/after so replays and audits can
# verify application without re-running the resolver.
REQUIRED_TARGET_FIELDS = ("combatantId", "hpBefore", "hpAfter", "statusAfter")

VALID_RESOURCE_KINDS = frozenset({"ammunition", "spellSlot", "featureUse", "item"})


def make_event_id(encounter_id, round_number, turn_id, sequence):
    """Stable, human-readable event ID, unique within an encounter.

    The fixed-width digest covers the complete persisted turn ID. It remains
    deterministic across recovery without allowing free-form caller IDs to
    inject delimiters or grow the bounded applied-event ledger indefinitely.
    """
    turn_digest = hashlib.sha256(str(turn_id).encode("utf-8")).hexdigest()[:16]
    return "%s-R%d-%s-A%d" % (
        encounter_id,
        int(round_number),
        turn_digest,
        int(sequence),
    )


def validate_event(event):
    """Return a list of problem strings; empty list means valid."""
    problems = []
    if not isinstance(event, dict):
        return ["event must be an object"]
    for field in REQUIRED_EVENT_FIELDS:
        if field not in event or event[field] in (None, ""):
            problems.append("missing field: %s" % field)
    if "stateVersion" in event and not isinstance(event.get("stateVersion"), int):
        problems.append("stateVersion must be an integer")
    outcome = event.get("outcome")
    if isinstance(outcome, dict):
        for target in outcome.get("targets", []) or []:
            if not isinstance(target, dict):
                problems.append("outcome.targets entries must be objects")
                continue
            for field in REQUIRED_TARGET_FIELDS:
                if field not in target:
                    problems.append(
                        "target %s missing %s" % (target.get("combatantId", "?"), field))
    elif "outcome" in event:
        problems.append("outcome must be an object")
    for resource in event.get("resources", []) or []:
        if not isinstance(resource, dict):
            problems.append("resources entries must be objects")
            continue
        if resource.get("kind") not in VALID_RESOURCE_KINDS:
            problems.append("unknown resource kind: %r" % resource.get("kind"))
        if not isinstance(resource.get("delta"), int):
            problems.append("resource delta must be an integer")
    for effect_op in event.get("effects", []) or []:
        if not isinstance(effect_op, dict):
            problems.append("effects entries must be objects")
            continue
        if effect_op.get("op") not in ("add", "remove"):
            problems.append("effect op must be add or remove")
        if effect_op.get("applyOn", "always") not in (
            "always", "failedSave", "successfulSave"
        ):
            problems.append("effect applyOn is invalid")
        if (
            effect_op.get("applyOn", "always") != "always"
            and not (effect_op.get("saveTargetId") or effect_op.get("combatantId"))
        ):
            problems.append("save-gated effect requires a saveTargetId")
        targets = int(bool(effect_op.get("owner"))) + int(
            bool(effect_op.get("combatantId"))
        )
        if targets != 1:
            problems.append("effect op requires exactly one owner or combatantId")
        if effect_op.get("op") == "add":
            effect = effect_op.get("effect")
            if not isinstance(effect, dict):
                problems.append("effect add requires an effect object")
            elif not effect.get("effectId"):
                problems.append("effect add requires an effectId")
        elif effect_op.get("op") == "remove" and not (
            effect_op.get("effectId")
            or effect_op.get("name")
            or (isinstance(effect_op.get("effect"), dict)
                and (effect_op["effect"].get("effectId")
                     or effect_op["effect"].get("name")))
        ):
            problems.append("effect remove requires a name or effectId")
    for tick in event.get("effectTicks", []) or []:
        if not isinstance(tick, dict):
            problems.append("effectTicks entries must be objects")
            continue
        targets = int(bool(tick.get("owner"))) + int(
            bool(tick.get("combatantId"))
        )
        if targets != 1:
            problems.append("effect tick requires exactly one owner or combatantId")
        if not tick.get("effectId") and not tick.get("name"):
            problems.append("effect tick requires effectId or name")
        for field in ("roundsBefore", "roundsAfter"):
            if type(tick.get(field)) is not int or tick.get(field) < 0:
                problems.append(
                    "effect tick %s must be a nonnegative integer" % field
                )
    character_state = event.get("characterStateAfter")
    if character_state is not None:
        if not isinstance(character_state, dict):
            problems.append("characterStateAfter must be an object")
        else:
            for owner, snapshot in character_state.items():
                if not isinstance(owner, str) or not owner:
                    problems.append("characterStateAfter owner must be a name")
                    continue
                if not isinstance(snapshot, dict):
                    problems.append(
                        "characterStateAfter %s must be an object" % owner
                    )
                    continue
                if any(
                    field not in ("hitPoints", "status")
                    for field in snapshot
                ):
                    problems.append(
                        "characterStateAfter %s has an unknown field" % owner
                    )
                if "hitPoints" in snapshot and (
                    type(snapshot["hitPoints"]) is not int
                    or snapshot["hitPoints"] < 0
                ):
                    problems.append(
                        "characterStateAfter %s hitPoints must be nonnegative"
                        % owner
                    )
                if "status" in snapshot and not isinstance(
                    snapshot["status"], str
                ):
                    problems.append(
                        "characterStateAfter %s status must be a string" % owner
                    )
    return problems
