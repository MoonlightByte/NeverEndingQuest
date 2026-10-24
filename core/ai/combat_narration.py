# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Authoritative context and fallback combat narration.

The helpers in this module are deterministic. They never call a model and
never mutate encounter or character state. They build the compact scene
dossier from committed combat facts; the model's narration is not checked
against it by keyword (D-KW-4).
"""

from __future__ import annotations

from copy import deepcopy

from core.managers.combat_state import combatant_presentation_name, display_status


_SHEET_FIELDS = (
    "name",
    "class",
    "level",
    "race",
    "hitPoints",
    "temporaryHitPoints",
    "maxHitPoints",
    "concentration",
    "armorClass",
    "speed",
    "status",
    "condition",
    "condition_affected",
    "abilities",
    "abilityScores",
    "proficiencyBonus",
    "savingThrows",
    "skills",
    "ammunition",
    "temporaryEffects",
    "activeEffects",
    "damageResistances",
    "damageImmunities",
    "damageVulnerabilities",
    "conditionImmunities",
    "resistances",
    "immunities",
    "vulnerabilities",
    "senses",
)

def _public_copy(value):
    """Copy complete JSON-like combat data while omitting private keys."""
    if isinstance(value, dict):
        return {
            str(key): _public_copy(child)
            for key, child in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_public_copy(child) for child in value]
    if isinstance(value, str):
        return value
    return deepcopy(value)


def _narrated_riders(riders):
    """The riders records as T097 has always seen them: without the engine flag."""
    if not isinstance(riders, list):
        return riders
    return [{key: value for key, value in rider.items() if key != "engine"} if isinstance(rider, dict) else rider
            for rider in riders]


def _combat_sheet(sheet):
    if not isinstance(sheet, dict):
        return {}
    return {
        key: _public_copy(sheet[key])
        for key in _SHEET_FIELDS
        if key in sheet
    }


def _effective_scene_sheet(creature, sheet):
    raw = deepcopy(sheet) if isinstance(sheet, dict) else {}
    if (creature or {}).get("type") == "enemy":
        for field, creature_field in (
            ("armorClass", "armorClass"),
            ("maxHitPoints", "maxHitPoints"),
            ("speed", "speed"),
        ):
            if creature.get(creature_field) is not None:
                raw[field] = deepcopy(creature[creature_field])
        raw["hitPoints"] = creature.get("currentHitPoints", raw.get("hitPoints"))
        raw["temporaryEffects"] = deepcopy(creature.get("activeEffects") or [])
    try:
        from core.effects.effective import effective_sheet

        return effective_sheet(raw)
    except Exception:
        return raw


def _creature_map(encounter):
    return {
        creature.get("combatantId"): creature
        for creature in (encounter or {}).get("creatures", [])
        if isinstance(creature, dict) and creature.get("combatantId")
    }


def _display_name(
    creatures, combatant_id, fallback="A combatant", presentation=None
):
    if isinstance(presentation, dict):
        name = presentation.get(combatant_id)
        if isinstance(name, str) and name.strip():
            return name
    creature = creatures.get(combatant_id) or {}
    name = creature.get("name")
    return name if isinstance(name, str) and name.strip() else fallback


def _action_name(event):
    intent = event.get("intent") or {}
    for key in ("spellName", "spell", "ability", "itemName", "featureName", "action"):
        value = intent.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "combat action"


def _drawn_item(event):
    """NUM-B2: the weapon drawn after the swing, once the draw landed on the
    sheet. Owner N1/N2: nothing else of the hands record reaches the narrator."""
    hands = event.get("hands")
    draw = hands.get("draw") if isinstance(hands, dict) else None
    if not isinstance(draw, dict) or draw.get("applied") is not True:
        return None
    name = draw.get("item_name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def _bonus_fact(event, creatures, presentation=None):
    """R2: the typed Bonus Action resolved before this event's Action."""
    bonus = event.get("bonusAction")
    if not isinstance(bonus, dict):
        return None
    if bonus.get("featureName"):
        fact = {"featureName": bonus["featureName"]}
    elif isinstance(bonus.get("item"), dict):
        # #1338: the item Bonus Action (#1333) is keyed by its stored id; name it
        # from the engine's resource row, never from the sheet or the player's text.
        row = next((r for r in bonus.get("resources") or []
                    if isinstance(r, dict) and r.get("kind") == "item"), {})
        fact = {"item": _public_copy(bonus["item"])}
        if row.get("name"):
            fact["itemName"] = row["name"]
    else:
        return None
    if bonus.get("option"):
        fact["option"] = bonus["option"]
    if bonus.get("order") == "afterAction":
        # R3: the Off-hand Attack, taken after the Action (or not, its target down).
        fact["after"] = "the Action"
        fact["weapon"] = bonus.get("ability")
        if bonus.get("notTaken"):
            fact["notTaken"] = bonus["notTaken"]
        outcome = bonus.get("outcome") or {}
        for key in ("hit", "critical"):
            if type(outcome.get(key)) is bool:
                fact[key] = outcome[key]
    targets = []
    for target in (bonus.get("outcome") or {}).get("targets") or []:
        before, after = target.get("hpBefore"), target.get("hpAfter")
        targets.append({
            "targetName": _display_name(creatures, target.get("combatantId"), "the target", presentation),
            "hpBefore": before,
            "hpAfter": after,
            "hpDelta": after - before if type(before) is int and type(after) is int else None,
        })
    if targets:
        fact["targets"] = [{k: v for k, v in row.items() if v is not None} for row in targets]
    if bonus.get("resources"):
        fact["resources"] = _public_copy(bonus["resources"])
    return fact


def _fact_event(event, creatures, presentation=None):
    outcome = event.get("outcome") or {}
    intent = event.get("intent") or {}
    declared_deltas = {
        target.get("combatantId"): target.get("hpDelta")
        for target in intent.get("targets", []) or []
        if isinstance(target, dict)
        and isinstance(target.get("combatantId"), str)
        and type(target.get("hpDelta")) is int
    }
    actor_id = event.get("actorId")
    targets = []
    for target in outcome.get("targets", []) or []:
        if not isinstance(target, dict):
            continue
        before = target.get("hpBefore")
        after = target.get("hpAfter")
        hp_delta = after - before if type(before) is int and type(after) is int else None
        row = {
            "targetId": target.get("combatantId"),
            "targetName": _display_name(
                creatures, target.get("combatantId"), "the target", presentation
            ),
            "hpBefore": before,
            "hpAfter": after,
            "hpDelta": hp_delta,
            "declaredHpDelta": declared_deltas.get(target.get("combatantId")),
            "tempHpBefore": target.get("tempHpBefore"),
            "tempHpAfter": target.get("tempHpAfter"),
            "statusAfter": display_status(
                creatures.get(target.get("combatantId")) or {}, target.get("statusAfter"),
                hp=after,
            ),
            # CC: the engine's concentration save lines and what ended on a failure
            "engineChecks": target.get("engineChecks"),
            "concentrationEnded": target.get("concentrationEnded"),
            "concentrationEndedEffects": target.get("concentrationEndedEffects"),
            # MS-b: a hit's rider save (venom): ability, save, dc, saved, damage, conditions
            # (K1's `engine` flag is bookkeeping, not part of the story.)
            "riders": _narrated_riders(target.get("riders")),
            # #669: a class-feature heal clamped to its typed limit (supplied, allowed)
            "featureHeal": target.get("featureHeal"),
        }
        targets.append({key: value for key, value in row.items() if value is not None})
    fact = {
        "eventId": event.get("eventId"),
        "actorId": actor_id,
        "actorName": _display_name(creatures, actor_id, presentation=presentation),
        "actionName": _action_name(event),
        "kind": outcome.get("kind"),
        "targets": targets,
        "hit": outcome.get("hit"),
        "critical": outcome.get("critical"),
        "damage": outcome.get("damage"),
        "attackRoll": outcome.get("attackRoll"),
        "totalAttack": outcome.get("totalAttack"),
        "targetAC": outcome.get("targetAC"),
        "resources": _public_copy(event.get("resources") or []),
        "effects": _public_copy(event.get("effects") or []),
        # MS-b: recharge abilities spent by this action, and the d6 draws made
        # at the start of the actor's turn (name, value, rechargesOn, recharged)
        "rechargeSpent": [spent.get("name") for spent in event.get("recharge") or [] if spent.get("name")] or None,
        "rechargeRolls": _public_copy(event.get("rechargeRolls")) if event.get("rechargeRolls") else None,
        # NUM-B2: a carried weapon drawn after this swing (item name)
        "drew": _drawn_item(event),
        # R2: the Bonus Action taken first (feature, option, its HP changes)
        "bonusAction": _bonus_fact(event, creatures, presentation),
    }
    return {key: value for key, value in fact.items() if value is not None}


def _spell_references(facts):
    names = {
        fact.get("actionName")
        for fact in facts
        if isinstance(fact.get("actionName"), str)
    }
    if not names:
        return []
    try:
        from core.ai.srd_reference import load_srd_reference_index

        index = load_srd_reference_index()
    except Exception:
        return []
    references = []
    for name in sorted(names):
        try:
            reference = index.reference(name)
        except Exception:
            reference = None
        if not reference:
            continue
        entry = reference.get("entry") or {}
        references.append(
            {
                "key": reference.get("key"),
                "name": entry.get("name", name),
                "level": entry.get("level"),
                "compactGuidance": entry.get("compactGuidance"),
                "source": entry.get("source"),
                "version": entry.get("version"),
            }
        )
    return references


def party_scene_time(path="party_tracker.json"):
    """The hour outside from the party tracker's clock (#1423): the time of day
    label the game's prompts use and the clock, or None when unreadable."""
    from utils.encoding_utils import safe_json_load
    from utils.time_context import get_time_context

    try:
        tracker = safe_json_load(path)
    except Exception:
        # A corrupt tracker never blocks the narration; it goes without the hour.
        return None
    world = tracker.get("worldConditions") if isinstance(tracker, dict) else None
    time_str = world.get("time") if isinstance(world, dict) else None
    if not isinstance(time_str, str):
        return None
    label = get_time_context(time_str)
    if label == "unknown time":
        return None
    return {"timeOfDay": label, "clock": time_str[:5]}


def build_scene_dossier(encounter, events, characters=None, scene_time=None):
    """Build the complete compact T097 scene, with exact facts last.
    `scene_time` is the hour outside (party_scene_time), when known."""
    encounter = encounter if isinstance(encounter, dict) else {}
    events = [event for event in (events or []) if isinstance(event, dict)]
    characters = characters if isinstance(characters, dict) else {}
    state = encounter.get("combatState") or {}
    creatures = _creature_map(encounter)
    presentation = {
        combatant_id: combatant_presentation_name(encounter, combatant_id)
        for combatant_id in creatures
    }
    combatants = []
    for creature in encounter.get("creatures", []) or []:
        if not isinstance(creature, dict):
            continue
        mechanical_name = creature.get("name")
        name = presentation.get(creature.get("combatantId"), mechanical_name)
        sheet = (
            characters.get(mechanical_name)
            if isinstance(mechanical_name, str)
            else None
        )
        effective = _effective_scene_sheet(creature, sheet)
        sheet_is_state_authority = (
            creature.get("type") in ("player", "npc") and isinstance(sheet, dict)
        )
        combatants.append(
            {
                "combatantId": creature.get("combatantId"),
                "name": name,
                "type": creature.get("type"),
                "faction": creature.get("faction"),
                "initiative": creature.get("initiative"),
                "currentHitPoints": (
                    sheet.get("hitPoints")
                    if sheet_is_state_authority
                    else creature.get("currentHitPoints", effective.get("hitPoints"))
                ),
                "maxHitPoints": effective.get(
                    "maxHitPoints", creature.get("maxHitPoints")
                ),
                "armorClass": effective.get(
                    "armorClass", creature.get("armorClass")
                ),
                # #1404: shown after the sheet-authority choice; stored unchanged.
                "status": display_status(
                    creature,
                    sheet.get("status", creature.get("status"))
                    if sheet_is_state_authority
                    else creature.get("status"),
                    encounter=encounter,
                ),
                "condition": (
                    sheet.get("condition", creature.get("condition"))
                    if sheet_is_state_authority
                    else creature.get("condition")
                ),
                "activeEffects": _public_copy(creature.get("activeEffects") or []),
                "sheet": _combat_sheet(effective),
            }
        )
    order = []
    for actor_id in state.get("initiativeOrder", []) or []:
        creature = creatures.get(actor_id) or {}
        order.append(
            {
                "combatantId": actor_id,
                "name": _display_name(
                    creatures, actor_id, presentation=presentation
                ),
                "initiative": creature.get("initiative"),
                "status": display_status(creature, encounter=encounter),
                "actedThisRound": actor_id in (state.get("actedThisRound") or []),
            }
        )
    facts = [_fact_event(event, creatures, presentation) for event in events]
    delivery = state.get("pendingDelivery") or {}
    permitted = sorted(
        {
            str(value).strip()
            for value in (
                [row.get("name") for row in combatants]
                + [fact.get("actionName") for fact in facts]
                + [fact.get("drew") for fact in facts]
                + [encounter.get("locationName"), encounter.get("location")]
            )
            if isinstance(value, str) and value.strip()
        },
        key=str.lower,
    )
    dossier = {
        "contextVersion": 1,
        "encounterId": encounter.get("encounterId"),
        "location": encounter.get("locationName") or encounter.get("location"),
        **({"scene": dict(scene_time)} if isinstance(scene_time, dict) else {}),
        "combatants": combatants,
        "initiative": {
            "round": state.get("round"),
            "order": order,
            "turnCursor": state.get("turnCursor"),
            "actedThisRound": list(state.get("actedThisRound") or []),
        },
        "committedSlice": {
            "roundBefore": delivery.get("roundBefore"),
            "roundAfter": delivery.get("roundAfter"),
            "actorIds": [event.get("actorId") for event in events],
            "actorNames": [
                _display_name(
                    creatures, event.get("actorId"), presentation=presentation
                )
                for event in events
            ],
        },
        "ruleReferences": _spell_references(facts),
        "permittedNamedEntities": permitted,
        # This must remain the final payload item. Provider adapters serialize
        # dict insertion order, keeping the exact facts at the attention tip.
        "authoritativeFacts": {
            "round": state.get("round"),
            "events": facts,
        },
    }
    return dossier


def narration_coverage_violations(covered_event_ids, dossier):
    """Validate the narrator's ordered acknowledgement of committed events."""
    expected = [
        event.get("eventId")
        for event in (
            ((dossier or {}).get("authoritativeFacts") or {}).get("events") or []
        )
        if isinstance(event, dict) and isinstance(event.get("eventId"), str)
    ]
    if not isinstance(covered_event_ids, list) or any(
        not isinstance(event_id, str) for event_id in covered_event_ids
    ):
        return ["committed_event_coverage_missing"]
    if covered_event_ids != expected:
        return ["committed_event_coverage_mismatch"]
    return []


def update_narration_activity(activity, events):
    """Accumulate a per-combatant summary from committed typed facts."""
    result = deepcopy(activity) if isinstance(activity, dict) else {}

    def row_for(combatant_id):
        row = result.get(combatant_id)
        if not isinstance(row, dict):
            row = {}
        normalized = {
            "actions": list(row.get("actions") or []),
            "damageDealt": max(0, int(row.get("damageDealt", 0) or 0)),
            "damageTaken": max(0, int(row.get("damageTaken", 0) or 0)),
            "healingDealt": max(0, int(row.get("healingDealt", 0) or 0)),
            "healingReceived": max(0, int(row.get("healingReceived", 0) or 0)),
            "recentFacts": list(row.get("recentFacts") or []),
        }
        result[combatant_id] = normalized
        return normalized

    for event in events or []:
        if not isinstance(event, dict) or not isinstance(event.get("actorId"), str):
            continue
        actor_id = event["actorId"]
        actor = row_for(actor_id)
        action = _action_name(event)
        actor["actions"] = actor["actions"] + [action]
        target_facts = []
        for target in (event.get("outcome") or {}).get("targets", []) or []:
            if not isinstance(target, dict):
                continue
            target_id = target.get("combatantId")
            before, after = target.get("hpBefore"), target.get("hpAfter")
            delta = after - before if type(before) is int and type(after) is int else 0
            if isinstance(target_id, str):
                target_row = row_for(target_id)
                if delta < 0:
                    actor["damageDealt"] += abs(delta)
                    target_row["damageTaken"] += abs(delta)
                elif delta > 0:
                    actor["healingDealt"] += delta
                    target_row["healingReceived"] += delta
            target_facts.append(
                {
                    key: value
                    for key, value in {
                        "targetId": target_id,
                        "hpDelta": delta,
                        "statusAfter": target.get("statusAfter"),
                    }.items()
                    if value is not None
                }
            )
        resources = [
            {
                key: resource.get(key)
                for key in ("owner", "kind", "name", "delta", "before", "after", "exhausted")
                if key in resource
            }
            for resource in event.get("resources", []) or []
            if isinstance(resource, dict)
        ]
        effects = []
        for operation in event.get("effects", []) or []:
            if not isinstance(operation, dict):
                continue
            effect = operation.get("effect") or {}
            effects.append(
                {
                    key: value
                    for key, value in {
                        "op": operation.get("op"),
                        "owner": operation.get("owner"),
                        "combatantId": operation.get("combatantId"),
                        "name": (
                            effect.get("name")
                            if isinstance(effect, dict)
                            else operation.get("name")
                        ),
                    }.items()
                    if value is not None
                }
            )
        actor["recentFacts"] = actor["recentFacts"] + [
            {
                "action": action,
                "targets": target_facts,
                "resources": resources,
                "effects": effects,
            }
        ]
    return result


def render_committed_events(encounter, events):
    """Render a truthful last-resort sentence from committed typed facts."""
    creatures = _creature_map(encounter if isinstance(encounter, dict) else {})
    parts = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        fact = _fact_event(event, creatures)
        actor = fact.get("actorName", "A combatant")
        action = fact.get("actionName", "combat action")
        targets = fact.get("targets") or []
        target = targets[0] if targets else None
        target_name = target.get("targetName") if isinstance(target, dict) else None
        if fact.get("kind") == "attack":
            # NUM-B2: a committed draw is part of the swing
            attacker = "%s draws the %s and" % (actor, fact["drew"]) if fact.get("drew") else actor
            if fact.get("hit"):
                sentence = "%s attacks %s with %s and hits" % (
                    attacker,
                    target_name or "the target",
                    action,
                )
            else:
                sentence = "%s attacks %s with %s and misses" % (
                    attacker,
                    target_name or "the target",
                    action,
                )
        else:
            sentence = "%s uses %s" % (actor, action)
            if target_name:
                sentence += " on %s" % target_name
        # #511: no damage or HP numbers in this sentence; a target the
        # committed facts leave at 0 HP is down.
        if isinstance(target, dict) and type(target.get("hpAfter")) is int and target["hpAfter"] == 0:
            sentence += "; %s is down" % target.get("targetName", "the target")
        parts.append(sentence + ".")
    return " ".join(parts) or "The committed combat actions resolve, and the battle continues."


def progressive_narration_feedback(previous_attempt, dossier):
    """Build the legacy-proven keep/fix/correct retry payload."""
    previous_attempt = previous_attempt if isinstance(previous_attempt, dict) else {}
    violations = [
        str(code)
        for code in previous_attempt.get("violations", [])
        if isinstance(code, str)
    ]
    warnings = [
        str(code)
        for code in previous_attempt.get("warnings", [])
        if isinstance(code, str)
    ]
    return {
        "previousCandidate": str(previous_attempt.get("candidate") or ""),
        "violationCodes": violations,
        "warningCodes": warnings,
        "Keep This": (
            "Preserve any vivid wording that does not conflict with the scene dossier."
        ),
        "You Must Fix This": (
            "Correct every listed violation; do not repeat or introduce an entity, "
            "action, or mechanical bookkeeping detail."
        ),
        "Corrective Action Required": (
            "Return one corrected JSON narration object grounded only in the supplied "
            "scene dossier and final authoritative facts."
        ),
        "authoritativeFacts": deepcopy(
            (dossier or {}).get("authoritativeFacts") or {}
        ),
    }
