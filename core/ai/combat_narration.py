# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Authoritative context, integrity linting, and fallback combat narration.

The helpers in this module are deterministic. They never call a model and
never mutate encounter or character state. Model prose is accepted only after
it agrees with the compact scene dossier built from committed combat facts.
"""

from __future__ import annotations

import re
from copy import deepcopy

from core.managers.combat_state import combatant_presentation_name


_SHEET_FIELDS = (
    "name",
    "class",
    "level",
    "race",
    "hitPoints",
    "maxHitPoints",
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

_INTERNAL_RE = re.compile(
    r"(?:\bcmb-[a-z0-9-]+\b|\b[A-Za-z0-9_-]+-R\d+-[a-f0-9]{8,}-A\d+\b|"
    r"\b(?:eventId|stateVersion|pendingDelivery|turnCursor|actorId|combatState)\b)",
    re.IGNORECASE,
)
_DAMAGE_RE = re.compile(r"\b(\d+)\s+(?:points?\s+of\s+)?damage\b", re.IGNORECASE)
_HEAL_RE = re.compile(
    r"\b(?:heals?|healed|restores?|regains?)\D{0,24}(\d+)\s+(?:hit points?|hp)\b",
    re.IGNORECASE,
)
_HP_RE = re.compile(
    r"\b(?:at|to|with|has|leaves?\s+\w+\s+at)\s+(\d+)\s+(?:hit points?|hp)\b",
    re.IGNORECASE,
)
_AC_RE = re.compile(r"\bAC\s*(?:of\s*)?(\d+)\b", re.IGNORECASE)
_ROUND_RE = re.compile(r"\bround\s+(\d+)\b", re.IGNORECASE)
_ATTACK_ROLL_RE = re.compile(
    r"\b(?:attack\s+roll|rolls?)(?:\s+of|\s+is|:)?\s*(\d+)\b",
    re.IGNORECASE,
)
_SLOT_RE = re.compile(
    r"\b(?:level\s*)?(\d+)(?:st|nd|rd|th)?[- ]level\s+spell\s+slot\b",
    re.IGNORECASE,
)
_AMMUNITION_RE = re.compile(
    r"\b(?:uses?|used|expends?|expended|spends?|spent|leaving|left(?:\s+with)?)"
    r"\D{0,24}(\d+)\s+(?:arrows?|bolts?|ammunition|ammo)\b",
    re.IGNORECASE,
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
            "statusAfter": target.get("statusAfter"),
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


def build_scene_dossier(encounter, events, characters=None):
    """Build the complete compact T097 scene, with exact facts last."""
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
                "status": (
                    sheet.get("status", creature.get("status"))
                    if sheet_is_state_authority
                    else creature.get("status")
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
                "status": creature.get("status"),
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
                for key in ("owner", "kind", "name", "delta", "before", "after")
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


def _allowed_values(dossier):
    facts = ((dossier or {}).get("authoritativeFacts") or {}).get("events") or []
    values = {
        "damage": set(),
        "healing": set(),
        "hp": set(),
        "ac": set(),
        "attackRoll": set(),
        "slotLevel": set(),
        "round": set(),
    }
    round_number = ((dossier or {}).get("authoritativeFacts") or {}).get("round")
    if type(round_number) is int:
        values["round"].add(round_number)
    committed_slice = (dossier or {}).get("committedSlice") or {}
    for key in ("roundBefore", "roundAfter"):
        value = committed_slice.get(key)
        if type(value) is int:
            values["round"].add(value)
    for combatant in (dossier or {}).get("combatants", []) or []:
        if isinstance(combatant, dict) and type(combatant.get("armorClass")) is int:
            values["ac"].add(combatant["armorClass"])
    damage_by_actor = {}
    healing_by_actor = {}
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        for key, bucket in (
            ("damage", "damage"),
            ("attackRoll", "attackRoll"),
            ("totalAttack", "attackRoll"),
            ("targetAC", "ac"),
        ):
            value = fact.get(key)
            if type(value) is int:
                values[bucket].add(value)
        applied_damage = 0
        applied_healing = 0
        declared_damage = 0
        declared_healing = 0
        for target in fact.get("targets", []) or []:
            if not isinstance(target, dict):
                continue
            before, after, delta = (
                target.get("hpBefore"),
                target.get("hpAfter"),
                target.get("hpDelta"),
            )
            if type(before) is int:
                values["hp"].add(before)
            if type(after) is int:
                values["hp"].add(after)
            if type(delta) is int and delta < 0:
                values["damage"].add(abs(delta))
                applied_damage += abs(delta)
            if type(delta) is int and delta > 0:
                values["healing"].add(delta)
                applied_healing += delta
            declared = target.get("declaredHpDelta")
            if type(declared) is int and declared < 0:
                values["damage"].add(abs(declared))
                declared_damage += abs(declared)
            if type(declared) is int and declared > 0:
                values["healing"].add(declared)
                declared_healing += declared
        for resource in fact.get("resources", []) or []:
            if not isinstance(resource, dict):
                continue
            if resource.get("kind") == "spellSlot":
                match = re.search(r"(\d+)", str(resource.get("name") or ""))
                if match:
                    values["slotLevel"].add(int(match.group(1)))
        actor_id = fact.get("actorId")
        event_damage = (
            fact.get("damage")
            if type(fact.get("damage")) is int
            else declared_damage or applied_damage
        )
        event_healing = declared_healing or applied_healing
        if isinstance(actor_id, str) and type(event_damage) is int and event_damage > 0:
            damage_by_actor[actor_id] = damage_by_actor.get(actor_id, 0) + event_damage
        if isinstance(actor_id, str) and event_healing > 0:
            healing_by_actor[actor_id] = healing_by_actor.get(actor_id, 0) + event_healing
    values["damage"].update(value for value in damage_by_actor.values() if value > 0)
    values["healing"].update(value for value in healing_by_actor.values() if value > 0)
    if damage_by_actor:
        values["damage"].add(sum(damage_by_actor.values()))
    if healing_by_actor:
        values["healing"].add(sum(healing_by_actor.values()))
    return values


def lint_combat_narration(narration, dossier):
    """Return conservative rejecting violations and warning-only findings."""
    text = str(narration or "").strip()
    rejects = []
    warnings = []
    if not text:
        return {"reject": ["empty_narration"], "warnings": []}
    if _INTERNAL_RE.search(text):
        rejects.append("internal_identifier_leak")
    mechanical_checks = (
        _DAMAGE_RE,
        _HEAL_RE,
        _HP_RE,
        _AC_RE,
        _ROUND_RE,
        _ATTACK_ROLL_RE,
        _SLOT_RE,
        _AMMUNITION_RE,
    )
    for pattern in mechanical_checks:
        if pattern.search(text):
            rejects.append("mechanical_bookkeeping_leak")
            break
    facts = ((dossier or {}).get("authoritativeFacts") or {}).get("events") or []
    combatants = [
        row
        for row in (dossier or {}).get("combatants", []) or []
        if isinstance(row, dict)
    ]
    combatants_by_name = {
        str(row.get("name") or "").casefold(): row
        for row in combatants
        if isinstance(row.get("name"), str)
    }
    living_hostiles = [
        row
        for row in combatants
        if row.get("type") == "enemy"
        and str(row.get("status") or "alive").casefold()
        not in {"dead", "defeated", "unconscious"}
        and (
            type(row.get("currentHitPoints")) is not int
            or row.get("currentHitPoints") > 0
        )
    ]
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        for target in fact.get("targets", []) or []:
            if not isinstance(target, dict) or target.get("statusAfter") not in {
                "dead", "defeated", "unconscious"
            }:
                continue
            target_name = str(target.get("targetName") or "").strip()
            if not target_name:
                continue
            base_name = re.sub(r"[_ ]\d+$", "", target_name).strip()
            same_kind_remains = any(
                re.sub(r"[_ ]\d+$", "", str(row.get("name") or "")).casefold()
                == base_name.casefold()
                for row in living_hostiles
            )
            if same_kind_remains and re.search(
                r"\b(?:last|final|only\s+remaining)\s+" + re.escape(base_name) + r"\b",
                text,
                re.IGNORECASE,
            ):
                rejects.append("hostile_count_mismatch")

            target_row = combatants_by_name.get(target_name.casefold()) or {}
            hp_before = target.get("hpBefore")
            max_hp = target_row.get("maxHitPoints")
            if (
                type(hp_before) is int
                and type(max_hp) is int
                and hp_before >= max_hp
                and (
                    re.search(
                        r"\b(?:wounded|injured|bloodied|weakened|battered)\s+"
                        + re.escape(target_name)
                        + r"\b",
                        text,
                        re.IGNORECASE,
                    )
                    or re.search(
                        r"\b"
                        + re.escape(base_name)
                        + r"\b\s*,?\s*(?:though\s+)?(?:already\s+|still\s+)?"
                        r"(?:wounded|injured|bloodied|weakened|battered)\b",
                        text,
                        re.IGNORECASE,
                    )
                )
            ):
                rejects.append("stale_condition_mismatch")

    for action_name in {
        str(fact.get("actionName") or "").strip()
        for fact in facts
        if isinstance(fact, dict)
        and isinstance(fact.get("actionName"), str)
        and str(fact.get("actionName") or "").strip()
    }:
        if not re.search(r"\b%s\b" % re.escape(action_name), text, re.IGNORECASE):
            warnings.append("committed_action_name_missing")
            break
    names = [
        row.get("name")
        for row in (dossier or {}).get("combatants", [])
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    ]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        actor = fact.get("actorName")
        action = fact.get("actionName")
        if not isinstance(actor, str) or not isinstance(action, str):
            continue
        for other in names:
            if other == actor:
                continue
            for sentence in sentences:
                if re.match(
                    r"^\s*%s\b" % re.escape(other), sentence, re.IGNORECASE
                ) and re.search(r"\b%s\b" % re.escape(action), sentence, re.IGNORECASE):
                    warnings.append("actor_attribution_mismatch")
                    break
    return {
        "reject": list(dict.fromkeys(rejects)),
        "warnings": list(dict.fromkeys(warnings)),
    }


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
            if fact.get("hit"):
                damage = fact.get("damage")
                if type(damage) is not int and isinstance(target, dict):
                    delta = target.get("hpDelta")
                    damage = abs(delta) if type(delta) is int and delta < 0 else None
                sentence = "%s attacks %s with %s and hits" % (
                    actor,
                    target_name or "the target",
                    action,
                )
                if type(damage) is int:
                    sentence += " for %d damage" % damage
            else:
                sentence = "%s attacks %s with %s and misses" % (
                    actor,
                    target_name or "the target",
                    action,
                )
        else:
            sentence = "%s uses %s" % (actor, action)
            if target_name:
                sentence += " on %s" % target_name
        if isinstance(target, dict) and type(target.get("hpAfter")) is int:
            sentence += "; %s has %d HP remaining" % (
                target.get("targetName", "the target"),
                target["hpAfter"],
            )
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
