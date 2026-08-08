# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure combat resolution: intent -> deterministic mechanical outcome.

Contract with core.managers.combat_state:
- The caller claims a turn (begin_turn), asks a model or the player for an
  intent, then calls validate_intent / resolve_intent / apply_resolution
  here, stages the produced event (stage_turn_events), persists the new
  encounter+character state atomically, and finally commit_turn.
- Nothing here mutates its inputs. apply_resolution returns deep copies.
- Nothing here performs I/O or imports managers, updaters, or model code.

Two validation regimes:
- NPC/monster intents are STRICT: unknown actions, dead targets, and
  exhausted resources are rejected with the legal alternatives so the
  caller can issue a narrow model correction.
- Player intents are ADJUDICATED: unknown/creative actions are allowed
  through as mode="adjudicated"; the DM model proposes mechanics, and
  apply_resolution clamps every quantity to legal bounds instead of
  whitelisting the action itself.
"""

import re
from copy import deepcopy

from core.effects.effective import effective_sheet, modifier_total
from core.effects.lifecycle import apply_effect_ops
from core.effects.model import normalize_effect, validate_effect
from core.managers.combat_state import (
    combatant_by_id,
    is_turn_eligible,
    normalize_status,
)

_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$")
_STAMPED_EFFECT_ROUND_RE = re.compile(
    r"-R(\d+)-(?:[0-9a-f]{16}|.{1,8})-A\d+-\d+$"
)

PLAYER_UNCONSCIOUS = "unconscious"
NONPLAYER_DEAD = "dead"


class Rejection(dict):
    """Invalid intent: {reason, legalActions?, legalTargets?, retryable}."""


class Resolution(dict):
    """resolve_intent output: {event, charDeltas, creatureDeltas, violations}."""


class DeterministicRollSource(object):
    """Injected dice. take('d20') pops the next value for that die.

    Tests seed exact sequences; production seeds from the encounter's
    preroll pools. Exhaustion raises IndexError - callers must supply
    enough dice, silent invention of rolls is not allowed here.
    """

    def __init__(self, pools):
        self._pools = {die: list(values) for die, values in dict(pools or {}).items()}

    def take(self, die):
        pool = self._pools.get(die)
        if not pool:
            raise IndexError("Roll pool exhausted for %s" % die)
        return pool.pop(0)

    def remaining(self, die):
        return len(self._pools.get(die, []))


def parse_dice(expression):
    """'2d6+3' -> (count, sides, modifier). Raises ValueError on junk."""
    match = _DICE_RE.match(str(expression or ""))
    if not match:
        raise ValueError("Unparseable dice expression: %r" % expression)
    count, sides = int(match.group(1)), int(match.group(2))
    modifier = int(match.group(3).replace(" ", "")) if match.group(3) else 0
    if count < 1 or count > 100 or sides not in (2, 4, 6, 8, 10, 12, 20, 100):
        raise ValueError("Unsupported dice expression: %r" % expression)
    return count, sides, modifier


def _take_roll(rolls, die, purpose, actor_id=None, target_id=None, ability=None):
    scoped = getattr(rolls, "take_for", None)
    if callable(scoped):
        return scoped(
            die,
            purpose=purpose,
            actor_id=actor_id,
            target_id=target_id,
            ability=ability,
        )
    return rolls.take(die)


def _action_entries(actor_sheet):
    sheet = actor_sheet or {}
    entries = sheet.get("attacksAndSpellcasting")
    if not isinstance(entries, list):
        entries = sheet.get("actions")
    return entries if isinstance(entries, list) else []


def _known_actions(actor_sheet):
    return [a.get("name") for a in _action_entries(actor_sheet)
            if isinstance(a, dict) and a.get("name")]


def _find_action(actor_sheet, name):
    wanted = str(name or "").strip().lower()
    for entry in _action_entries(actor_sheet):
        if isinstance(entry, dict) and str(entry.get("name", "")).strip().lower() == wanted:
            return entry
    return None


def _living_target_ids(encounter):
    return [c["combatantId"] for c in encounter.get("creatures", [])
            if is_turn_eligible(c)]


def validate_intent(encounter, characters, intent, strict=None):
    """Return (True, None) or (False, Rejection).

    strict=None derives the regime from the actor: players are
    adjudicated, everything else is strict.
    """
    if not isinstance(intent, dict):
        return False, Rejection(reason="intent must be an object", retryable=True)
    actor_id = intent.get("actorId")
    actor = combatant_by_id(encounter, actor_id)
    if actor is None:
        return False, Rejection(reason="unknown actorId: %r" % actor_id, retryable=False)
    if not is_turn_eligible(actor):
        return False, Rejection(
            reason="%s cannot act (status %s)" % (actor_id, actor.get("status")),
            retryable=False)

    state = encounter.get("combatState") or {}
    version = intent.get("stateVersion")
    if version is not None and version != state.get("revision"):
        return False, Rejection(
            reason="stale intent: stateVersion %s != revision %s"
                   % (version, state.get("revision")),
            retryable=True)
    pending = state.get("pendingTurn")
    if pending and actor_id not in (pending.get("actorIds") or []):
        return False, Rejection(
            reason="%s is not part of the pending turn window" % actor_id,
            retryable=False)

    if strict is None:
        strict = actor.get("type") != "player"

    action_kind = intent.get("action")
    if action_kind in (
        "defend", "dodge", "disengage", "dash", "hide", "help", "flee", "yield"
    ):
        return True, None

    sheet = (characters or {}).get(actor.get("name")) or {}
    target_id = intent.get("targetId")
    if action_kind == "attack":
        if strict and not target_id:
            return False, Rejection(
                reason="attack requires a targetId",
                legalTargets=[
                    target
                    for target in _living_target_ids(encounter)
                    if (combatant_by_id(encounter, target) or {}).get("faction")
                    != actor.get("faction")
                ],
                retryable=True,
            )
        if target_id is not None and combatant_by_id(encounter, target_id) is None:
            return False, Rejection(
                reason="unknown targetId: %r" % target_id,
                legalTargets=_living_target_ids(encounter), retryable=True)
        target = combatant_by_id(encounter, target_id) if target_id else None
        if target is not None and not is_turn_eligible(target):
            return False, Rejection(
                reason="target %s is already down" % target_id,
                legalTargets=_living_target_ids(encounter), retryable=True)
        if strict and target is not None and target.get("faction") == actor.get("faction"):
            return False, Rejection(
                reason="%s cannot attack ally %s" % (actor_id, target_id),
                legalTargets=[t for t in _living_target_ids(encounter)
                              if (combatant_by_id(encounter, t) or {}).get("faction")
                              != actor.get("faction")],
                retryable=True)
        if strict:
            entry = _find_action(sheet, intent.get("ability"))
            if entry is None:
                return False, Rejection(
                    reason="%s does not have %r" % (actor.get("name"), intent.get("ability")),
                    legalActions=_known_actions(sheet), retryable=True)
            if entry.get("type") == "ranged" and _ammo_quantity(sheet) == 0:
                return False, Rejection(
                    reason="%s has no ammunition left" % actor.get("name"),
                    legalActions=[n for n in _known_actions(sheet)
                                  if (_find_action(sheet, n) or {}).get("type") != "ranged"],
                    retryable=True)
        return True, None

    if strict:
        return False, Rejection(
            reason="unsupported strict action %r" % action_kind,
            legalActions=_known_actions(sheet) + [
                "defend", "dodge", "disengage", "flee", "yield"
            ],
            retryable=True)
    # Player creativity: pass through for DM adjudication; bounds are
    # enforced at apply time, not by whitelist.
    return True, None


def _ammo_quantity(sheet, name=None):
    total = 0
    for item in (sheet or {}).get("ammunition", []):
        if isinstance(item, dict) and (name is None or item.get("name") == name):
            total += max(0, int(item.get("quantity", 0) or 0))
    return total


def _raw_combatant_sheet(encounter, characters, creature):
    """Return the canonical effect input for any combatant.

    Player/NPC effects live on their character sheet. Sheet-less encounter
    actors keep a small base-stat snapshot plus ``activeEffects`` so the same
    declarative arithmetic can protect monsters, summons, and hazards too.
    """
    creature = creature or {}
    sheet = (characters or {}).get(creature.get("name"))
    if creature.get("type") in ("player", "npc") and isinstance(sheet, dict):
        return sheet
    result = deepcopy(sheet) if isinstance(sheet, dict) else {}
    base = creature.get("effectBaseStats") or {}
    result["armorClass"] = base.get(
        "armorClass",
        creature.get("armorClass", result.get("armorClass", 10)),
    )
    result["maxHitPoints"] = base.get(
        "maxHitPoints",
        creature.get("maxHitPoints", result.get("maxHitPoints", 0)),
    )
    result["hitPoints"] = creature.get(
        "currentHitPoints",
        result.get("hitPoints", 0),
    )
    result["temporaryEffects"] = creature.get("activeEffects", []) or []
    return result


def _effective_combatant_sheet(encounter, characters, creature):
    return effective_sheet(_raw_combatant_sheet(encounter, characters, creature))


def _combatant_ac(encounter, characters, creature):
    sheet = _effective_combatant_sheet(encounter, characters, creature)
    if isinstance(sheet.get("armorClass"), (int, float)):
        return int(sheet["armorClass"])
    return int((creature or {}).get("armorClass", 10) or 10)


def _combatant_max_hp(encounter, characters, creature):
    sheet = _effective_combatant_sheet(encounter, characters, creature)
    if isinstance(sheet.get("maxHitPoints"), (int, float)):
        return int(sheet["maxHitPoints"])
    return int((creature or {}).get("maxHitPoints", 0) or 0)


def resolve_intent(encounter, characters, intent, rolls, event_id):
    """Resolve a validated attack intent into an event + deltas.

    Only 'attack' (and the no-op stances) resolve mechanically here;
    adjudicated player actions arrive as pre-shaped outcome proposals via
    resolve_adjudicated. Inputs are not mutated.
    """
    actor = combatant_by_id(encounter, intent.get("actorId"))
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    event = {
        "eventId": event_id,
        "actorId": intent["actorId"],
        "stateVersion": int((encounter.get("combatState") or {}).get("revision", 0)),
        "intent": deepcopy(intent),
        "rolls": [],
        "outcome": {"kind": intent.get("action"), "targets": []},
        "resources": [],
    }
    resolution = Resolution(event=event, charDeltas={}, creatureDeltas={}, violations=[])

    if intent.get("action") in ("flee", "yield"):
        hp = int(actor.get("currentHitPoints", 0) or 0)
        event["outcome"]["targets"].append({
            "combatantId": actor["combatantId"],
            "hpBefore": hp,
            "hpAfter": hp,
            "statusAfter": "defeated",
        })
        resolution["creatureDeltas"][actor["combatantId"]] = {
            "status": "defeated"
        }
        if actor.get("type") == "npc" and actor.get("name") in (characters or {}):
            resolution["charDeltas"][actor["name"]] = {"status": "defeated"}
        return resolution

    if intent.get("action") != "attack":
        return resolution

    entry = _find_action(sheet, intent.get("ability")) or {}
    target = combatant_by_id(encounter, intent.get("targetId"))
    attack_bonus = int(entry.get("attackBonus", 0) or 0) + modifier_total(
        sheet, "attackRolls"
    )
    target_ac = _combatant_ac(encounter, characters, target)
    attack_counter = getattr(rolls, "attack_count", None)
    attack_count = attack_counter(intent.get("actorId")) if callable(attack_counter) else 1
    attack_count = max(1, min(8, int(attack_count or 1)))
    if entry.get("type") == "ranged":
        attack_count = min(attack_count, _ammo_quantity(sheet))

    hp_before = int((target or {}).get("currentHitPoints", 0) or 0)
    hp_after = hp_before
    swings = []
    total_damage = 0
    for swing_number in range(1, attack_count + 1):
        if target is None or hp_after <= 0:
            break
        attack_die = _take_roll(
            rolls,
            "d20",
            "attack",
            actor_id=intent.get("actorId"),
            target_id=intent.get("targetId"),
        )
        total = attack_die + attack_bonus
        critical = attack_die == 20
        hit = critical or (attack_die != 1 and total >= target_ac)
        event["rolls"].append(
            {"die": "d20", "value": attack_die, "purpose": "attack"}
        )
        damage = 0
        if hit:
            count, sides, modifier = parse_dice(entry.get("damageDice", "1d4"))
            if critical:
                count *= 2
            damage_rolls = [
                _take_roll(
                    rolls,
                    "d%d" % sides,
                    "damage",
                    actor_id=intent.get("actorId"),
                    target_id=intent.get("targetId"),
                )
                for _ in range(count)
            ]
            for value in damage_rolls:
                event["rolls"].append(
                    {"die": "d%d" % sides, "value": value, "purpose": "damage"}
                )
            damage = max(
                0,
                sum(damage_rolls)
                + modifier
                + int(entry.get("damageBonus", 0) or 0)
                + modifier_total(sheet, "damageRolls"),
            )
            hp_after = max(0, hp_after - damage)
            total_damage += damage
        swings.append(
            {
                "number": swing_number,
                "attackRoll": attack_die,
                "totalAttack": total,
                "targetAC": target_ac,
                "hit": hit,
                "critical": critical,
                "damage": damage,
            }
        )

    event["outcome"]["swings"] = swings
    event["outcome"]["hit"] = any(swing["hit"] for swing in swings)
    event["outcome"]["critical"] = any(swing["critical"] for swing in swings)
    event["outcome"]["damage"] = total_damage
    if swings:
        event["outcome"].update(
            {
                "attackRoll": swings[0]["attackRoll"],
                "totalAttack": swings[0]["totalAttack"],
                "targetAC": target_ac,
            }
        )
    if target is not None and swings:
        status_after = target.get("status", "alive")
        if hp_after == 0:
            status_after = (
                PLAYER_UNCONSCIOUS
                if target.get("type") == "player"
                else NONPLAYER_DEAD
            )
        event["outcome"]["targets"].append({
            "combatantId": target["combatantId"], "hpBefore": hp_before,
            "hpAfter": hp_after, "statusAfter": status_after,
        })
        resolution["creatureDeltas"][target["combatantId"]] = {
            "currentHitPoints": hp_after, "status": status_after,
        }
        # Only players/NPCs have character files; monsters can share a
        # name (Twig Blight x2), so syncing their sheets by name would
        # clobber the wrong record.
        target_name = target.get("name")
        if target.get("type") in ("player", "npc") and target_name in (characters or {}):
            resolution["charDeltas"][target_name] = {"hitPoints": hp_after}
            if status_after != normalize_status(target.get("status")):
                resolution["charDeltas"][target_name]["status"] = status_after

    if entry.get("type") == "ranged" and swings:
        for item in sheet.get("ammunition", []):
            if isinstance(item, dict) and int(item.get("quantity", 0) or 0) > 0:
                before = int(item.get("quantity", 0) or 0)
                spent = min(len(swings), before)
                event["resources"].append({
                    "owner": actor.get("name"), "kind": "ammunition",
                    "name": item.get("name"), "delta": -spent,
                    "before": before, "after": before - spent,
                })
                break
    return resolution


def _resource_snapshot(sheet, kind, name):
    """Return (before, max_or_None) for a resource, or None if unresolvable."""
    if kind == "ammunition":
        for item in (sheet or {}).get("ammunition", []):
            if isinstance(item, dict) and item.get("name") == name:
                return int(item.get("quantity", 0) or 0), None
        return None
    if kind == "spellSlot":
        level = ((sheet or {}).get("spellcasting") or {}).get("spellSlots", {}).get(name)
        if isinstance(level, dict):
            return int(level.get("current", 0) or 0), int(level.get("max", 0) or 0)
        return None
    if kind == "featureUse":
        for feature in (sheet or {}).get("classFeatures", []):
            if isinstance(feature, dict) and feature.get("name") == name:
                usage = feature.get("usage")
                if isinstance(usage, dict):
                    return int(usage.get("current", 0) or 0), int(usage.get("max", 0) or 0)
        return None
    if kind == "item":
        for item in (sheet or {}).get("equipment", []):
            if isinstance(item, dict) and item.get("item_name") == name:
                return int(item.get("quantity", 0) or 0), None
        return None
    return None


def _save_bonus(encounter, characters, creature, save_type):
    raw_sheet = _raw_combatant_sheet(encounter, characters, creature)
    sheet = effective_sheet(raw_sheet)
    saves = sheet.get("savingThrows") or []
    ability = str(save_type or "").strip().lower()
    if isinstance(saves, dict):
        try:
            return (
                int(saves.get(ability, saves.get(ability[:3], 0)) or 0)
                + modifier_total(raw_sheet, "savingThrows")
                + modifier_total(raw_sheet, "savingThrow.%s" % ability)
            )
        except (TypeError, ValueError):
            return 0
    scores = sheet.get("abilities") or sheet.get("abilityScores") or {}
    try:
        score = int(scores.get(ability, 10) or 10)
    except (AttributeError, TypeError, ValueError):
        score = 10
    bonus = (score - 10) // 2
    if isinstance(saves, list) and any(
        str(item).strip().lower().startswith(ability[:3]) for item in saves
    ):
        try:
            bonus += int(sheet.get("proficiencyBonus", 0) or 0)
        except (TypeError, ValueError):
            pass
    return (
        bonus
        + modifier_total(raw_sheet, "savingThrows")
        + modifier_total(raw_sheet, "savingThrow.%s" % ability)
    )


def resolve_adjudicated(encounter, characters, proposal, rolls, event_id):
    """General adjudicated-outcome contract for anything beyond weapon attacks.

    The DM model (or player-facing DM turn) proposes MECHANICS, not state:
    {
      "actorId": "...", "stateVersion": N, "description": "...",
      "save": {"type": "dexterity", "dc": 13, "halfOnSave": true},   # optional
      "targets": [{"combatantId": "...", "hpDelta": -7}],            # +N heals
      "resources": [{"owner": "...", "kind": "spellSlot",
                     "name": "level1", "delta": -1}],
      "effects": [{"op": "add", "owner": "...", "effect": {...}},
                  {"op": "remove", "owner": "...", "name": "Bless"}]
    }
    This one shape expresses attack-like damage, saves, healing, resource
    spends, and effect changes. Determinism: any save is rolled HERE from
    the injected RollSource (d20 + the target's sheet save bonus when one
    exists); a successful save halves negative hpDelta when halfOnSave,
    else negates it. All quantities are clamped in apply_resolution -
    the proposal can never push state outside legal bounds.
    """
    event = {
        "eventId": event_id,
        "actorId": proposal.get("actorId"),
        "stateVersion": int((encounter.get("combatState") or {}).get("revision", 0)),
        "intent": deepcopy(proposal),
        "rolls": [],
        "outcome": {"kind": "adjudicated",
                    "description": proposal.get("description", ""),
                    "targets": []},
        "resources": [],
    }
    resolution = Resolution(event=event, charDeltas={}, creatureDeltas={},
                            effectOps=[], violations=[])

    resources = proposal.get("resources", []) or []
    effects = proposal.get("effects", []) or []
    targets = proposal.get("targets", []) or []
    if not isinstance(resources, list) or len(resources) > 16:
        resolution["violations"].append("resources must be an array of at most 16 records")
        resources = []
    if not isinstance(effects, list) or len(effects) > 16:
        resolution["violations"].append("effects must be an array of at most 16 records")
        effects = []
    if not isinstance(targets, list) or len(targets) > len(encounter.get("creatures", [])):
        resolution["violations"].append(
            "targets must contain at most one record per combatant"
        )
        targets = []
    if any(not isinstance(entry, dict) for entry in targets):
        resolution["violations"].append("every adjudicated target must be an object")
        targets = []
    target_ids = [
        entry.get("combatantId") for entry in targets if isinstance(entry, dict)
    ]
    if len(target_ids) != len(set(target_ids)):
        resolution["violations"].append("duplicate adjudicated targets are not allowed")
        targets = []

    # Resources: validate owner/kind/name, reject overspend, and record
    # absolute before/after so a crash-replay of this event is idempotent.
    for record in resources:
        if not isinstance(record, dict):
            resolution["violations"].append("non-object resource record dropped")
            continue
        owner, kind, name = record.get("owner"), record.get("kind"), record.get("name")
        sheet = (characters or {}).get(owner)
        try:
            delta = int(record.get("delta"))
        except (TypeError, ValueError):
            resolution["violations"].append(
                "non-integer resource delta for %r dropped" % owner)
            continue
        snapshot = _resource_snapshot(sheet, kind, name) if isinstance(sheet, dict) else None
        if snapshot is None:
            resolution["violations"].append(
                "unresolvable resource %r/%r/%r dropped" % (owner, kind, name))
            continue
        before, cap = snapshot
        after = before + delta
        if after < 0:
            resolution["violations"].append(
                "overspend rejected: %s %s %s (%d%+d)" % (owner, kind, name, before, delta))
            continue
        if cap is not None:
            after = min(after, cap)
        event["resources"].append({"owner": owner, "kind": kind, "name": name,
                                   "delta": delta, "before": before, "after": after})

    # Effects: a sheet owner and an encounter combatantId are deliberately
    # distinct durable destinations. Monster display names can be duplicated,
    # so hostile effects must use their stable combatantId.
    normalized_effects = []
    for index, op in enumerate(effects):
        if not isinstance(op, dict) or op.get("op") not in ("add", "remove"):
            resolution["violations"].append("malformed effect op dropped")
            continue
        op = deepcopy(op)
        owner = op.get("owner")
        combatant_id = op.get("combatantId")
        if bool(owner) == bool(combatant_id):
            resolution["violations"].append(
                "effect op requires exactly one owner or combatantId"
            )
            continue
        if owner:
            roster_matches = [
                creature
                for creature in encounter.get("creatures", [])
                if creature.get("name") == owner
            ]
            if any(creature.get("type") == "enemy" for creature in roster_matches):
                resolution["violations"].append(
                    "enemy effect target %r must use combatantId" % owner
                )
                continue
            if not isinstance((characters or {}).get(owner), dict):
                resolution["violations"].append(
                    "effect owner %r has no durable character sheet" % owner
                )
                continue
        if combatant_id:
            target = combatant_by_id(encounter, combatant_id)
            if target is None:
                resolution["violations"].append(
                    "unknown effect combatantId %r" % combatant_id
                )
                continue
            if target.get("type") in ("player", "npc"):
                resolution["violations"].append(
                    "sheet-backed effect target %r must use owner" % combatant_id
                )
                continue
        if op["op"] == "add":
            if not isinstance(op.get("effect"), dict):
                resolution["violations"].append("effect add without effect object dropped")
                continue
            op["effect"].setdefault("effectId", "EFF-%s-%d" % (event_id, index))
            if "applyOn" in op["effect"] and "applyOn" not in op:
                resolution["violations"].append(
                    "applyOn belongs on the effect op, not inside effect"
                )
                continue
            actor = combatant_by_id(encounter, proposal.get("actorId")) or {}
            op["effect"]["authoredBy"] = "engine"
            op["effect"]["sourceEncounterId"] = encounter.get("encounterId")
            op["effect"].setdefault(
                "source",
                actor.get("name") or "combat",
            )
            if not op["effect"].get("durationKind"):
                op["effect"]["durationKind"] = (
                    "rounds"
                    if isinstance(op["effect"].get("roundsRemaining"), int)
                    else "encounter"
                )
            op["effect"].setdefault(
                "duration",
                (
                    "%s rounds" % op["effect"].get("roundsRemaining")
                    if op["effect"].get("durationKind") == "rounds"
                    else "encounter"
                ),
            )
            op["effect"].setdefault("modifiers", [])
            op["effect"].setdefault("conditions", [])
            op["effect"].setdefault(
                "created",
                {"encounterId": encounter.get("encounterId")},
            )
            if actor.get("combatantId"):
                op["effect"]["sourceCombatantId"] = actor.get("combatantId")
            if op["effect"].get("concentration"):
                op["effect"]["concentrationId"] = event_id
                op["effect"]["source"] = actor.get(
                    "name", op["effect"].get("source", op.get("owner"))
                )
            try:
                op["effect"] = normalize_effect(op["effect"])
            except ValueError as exc:
                resolution["violations"].append(
                    "effect contract rejected: %s" % exc
                )
                continue
            effect_problems = validate_effect(
                op["effect"],
                require_managed=True,
            )
            if effect_problems:
                resolution["violations"].append(
                    "effect contract rejected: %s" % "; ".join(effect_problems)
                )
                continue
        elif not (
            op.get("effectId")
            or op.get("name")
            or (isinstance(op.get("effect"), dict)
                and (op["effect"].get("effectId") or op["effect"].get("name")))
        ):
            resolution["violations"].append(
                "effect remove requires a name or effectId"
            )
            continue
        apply_on = op.get("applyOn", "always")
        if apply_on not in ("always", "failedSave", "successfulSave"):
            resolution["violations"].append(
                "effect applyOn must be always, failedSave, or successfulSave"
            )
            continue
        op["_applyOnExplicit"] = "applyOn" in op
        op["applyOn"] = apply_on
        normalized_effects.append(op)

    # One-time effect resource changes and target HP deltas are alternative
    # representations of the same mechanic. Reject a proposal that supplies
    # both, otherwise a weak model can grant Aid-style current HP twice.
    target_hp_changes = set()
    for entry in targets:
        if not isinstance(entry, dict):
            continue
        try:
            has_hp_change = int(entry.get("hpDelta", 0) or 0) != 0
        except (TypeError, ValueError):
            has_hp_change = False
        if has_hp_change:
            target_hp_changes.add(entry.get("combatantId"))
    for op in normalized_effects:
        if op.get("op") != "add":
            continue
        on_apply = (op.get("effect") or {}).get("onApply", []) or []
        if not any(
            isinstance(item, dict)
            and item.get("stat") == "hitPoints"
            and int(item.get("delta", 0) or 0) != 0
            for item in on_apply
        ):
            continue
        target_id = op.get("combatantId")
        if not target_id and op.get("owner"):
            matches = [
                creature.get("combatantId")
                for creature in encounter.get("creatures", []) or []
                if creature.get("name") == op.get("owner")
                and creature.get("type") in ("player", "npc")
            ]
            target_id = matches[0] if len(matches) == 1 else None
        if target_id in target_hp_changes:
            resolution["violations"].append(
                "effect onApply and target hpDelta duplicate one HP change"
            )
    save_spec = proposal.get("save") if isinstance(proposal.get("save"), dict) else None
    if save_spec and not targets:
        resolution["violations"].append(
            "a declared save requires at least one target (use hpDelta 0 for control)"
        )

    for entry in targets:
        target = combatant_by_id(encounter, entry.get("combatantId"))
        if target is None:
            resolution["violations"].append(
                "unknown target %r dropped" % entry.get("combatantId"))
            continue
        try:
            hp_delta = int(entry.get("hpDelta", 0) or 0)
        except (TypeError, ValueError):
            resolution["violations"].append(
                "non-integer hpDelta for %s dropped" % target["combatantId"])
            continue
        saved = None
        if save_spec and hp_delta <= 0:
            die = _take_roll(
                rolls,
                "d20",
                "save",
                actor_id=proposal.get("actorId"),
                target_id=target.get("combatantId"),
                ability=save_spec.get("type"),
            )
            bonus = _save_bonus(encounter, characters, target, save_spec.get("type"))
            saved = die + bonus >= int(save_spec.get("dc", 10) or 10)
            event["rolls"].append({"die": "d20", "value": die, "purpose": "save",
                                   "combatantId": target["combatantId"],
                                   "bonus": bonus, "success": saved})
            if saved and hp_delta < 0:
                hp_delta = hp_delta // 2 if save_spec.get("halfOnSave") else 0
        hp_before = int(target.get("currentHitPoints", 0) or 0)
        ceiling = _combatant_max_hp(encounter, characters, target) or hp_before
        hp_after = max(0, min(hp_before + hp_delta, ceiling))
        status_after = normalize_status(target.get("status"))
        if hp_after == 0 and hp_delta < 0:
            status_after = (PLAYER_UNCONSCIOUS if target.get("type") == "player"
                            else NONPLAYER_DEAD)
        elif hp_after > 0 and status_after == PLAYER_UNCONSCIOUS and hp_delta > 0:
            status_after = "alive"
        record = {"combatantId": target["combatantId"], "hpBefore": hp_before,
                  "hpAfter": hp_after, "statusAfter": status_after}
        if saved is not None:
            record["saved"] = saved
        event["outcome"]["targets"].append(record)
        resolution["creatureDeltas"][target["combatantId"]] = {
            "currentHitPoints": hp_after, "status": status_after}
        if target.get("type") in ("player", "npc") and target.get("name") in (characters or {}):
            delta = {"hitPoints": hp_after}
            if status_after != normalize_status(target.get("status")):
                delta["status"] = status_after
            resolution["charDeltas"][target["name"]] = delta

    save_results = {
        record.get("combatantId"): record.get("saved")
        for record in event["outcome"]["targets"]
        if "saved" in record
    }
    for op in normalized_effects:
        apply_on = op.get("applyOn", "always")
        save_target_candidates = []
        if op.get("combatantId") in save_results:
            save_target_candidates = [op.get("combatantId")]
        elif op.get("owner"):
            save_target_candidates = [
                combatant_id
                for combatant_id in save_results
                if (
                    combatant_by_id(encounter, combatant_id) or {}
                ).get("name") == op.get("owner")
            ]
        if save_spec and save_target_candidates and not op.get("_applyOnExplicit"):
            resolution["violations"].append(
                "an effect on a save target requires explicit applyOn"
            )
            continue
        if apply_on != "always":
            save_target_id = op.get("saveTargetId") or op.get("combatantId")
            if not save_target_id and op.get("owner"):
                owner_matches = [
                    combatant_id
                    for combatant_id in save_results
                    if (
                        combatant_by_id(encounter, combatant_id) or {}
                    ).get("name") == op.get("owner")
                ]
                if len(owner_matches) == 1:
                    save_target_id = owner_matches[0]
            save_target = combatant_by_id(encounter, save_target_id)
            if save_target_id not in save_results or save_target is None:
                resolution["violations"].append(
                    "save-gated effect requires a target with a resolved save"
                )
                continue
            if op.get("owner") and save_target.get("name") != op.get("owner"):
                resolution["violations"].append(
                    "owner effect saveTargetId must identify the same character"
                )
                continue
            saved = save_results[save_target_id]
            should_apply = (
                (apply_on == "failedSave" and saved is False)
                or (apply_on == "successfulSave" and saved is True)
            )
            if not should_apply:
                continue
            op["saveTargetId"] = save_target_id
        op.pop("_applyOnExplicit", None)
        resolution["effectOps"].append(op)
    # The staged event is the durable record recovery replays. It contains
    # only effects that passed their deterministic save gate.
    event["effects"] = deepcopy(resolution["effectOps"])
    return resolution


def resolution_from_event(encounter, characters, event):
    """Reconstruct an applyable Resolution from a durable staged event.

    Recovery path: after process death, the coordinator holds only the
    serialized pendingTurn.events. This rebuilds the absolute deltas from
    outcome.targets / event.resources / event.effects WITHOUT rerolling
    anything or consulting a model, so replaying is exact. Raises
    ValueError if the event fails validate_event.
    """
    from core.combat.events import validate_event as _validate
    problems = _validate(event)
    if problems:
        raise ValueError("Cannot reconstruct from invalid event: %s" % "; ".join(problems))
    resolution = Resolution(event=deepcopy(event), charDeltas={}, creatureDeltas={},
                            effectOps=[deepcopy(op) for op in event.get("effects", []) or []],
                            violations=[])
    for record in (event.get("outcome") or {}).get("targets", []) or []:
        combatant_id = record.get("combatantId")
        resolution["creatureDeltas"][combatant_id] = {
            "currentHitPoints": int(record["hpAfter"]),
            "status": record["statusAfter"],
        }
        creature = combatant_by_id(encounter, combatant_id)
        if (creature is not None and creature.get("type") in ("player", "npc")
                and creature.get("name") in (characters or {})):
            delta = {"hitPoints": int(record["hpAfter"])}
            if record["statusAfter"] != normalize_status(creature.get("status")):
                delta["status"] = record["statusAfter"]
            resolution["charDeltas"][creature["name"]] = delta
    return resolution


def _effect_containers(encounter, characters):
    """Yield every durable effect container with its stable owner identity."""
    for owner, sheet in (characters or {}).items():
        if isinstance(sheet, dict):
            yield {"owner": owner}, sheet.setdefault("temporaryEffects", [])
    for creature in (encounter or {}).get("creatures", []):
        if not isinstance(creature, dict):
            continue
        # Character-backed combatants retain their canonical sheet as the
        # single source of truth. Encounter storage is for sheet-less actors.
        if creature.get("type") in ("player", "npc"):
            continue
        yield {
            "combatantId": creature.get("combatantId"),
            "name": creature.get("name"),
        }, creature.setdefault("activeEffects", [])


def _effect_destination(encounter, characters, op):
    if op.get("combatantId"):
        creature = combatant_by_id(encounter, op.get("combatantId"))
        if creature is None or creature.get("type") in ("player", "npc"):
            return None
        return creature.setdefault("activeEffects", [])
    sheet = (characters or {}).get(op.get("owner"))
    if not isinstance(sheet, dict):
        return None
    return sheet.setdefault("temporaryEffects", [])


def _apply_encounter_effect_operation(creature, operation):
    """Apply one lifecycle operation to a sheet-less combatant safely."""
    if not isinstance(creature, dict):
        raise ValueError("Encounter effect target is unavailable")
    effects = creature.setdefault("activeEffects", [])
    if not isinstance(effects, list):
        raise ValueError("Encounter activeEffects must be an array")
    if operation.get("op") == "add" and not isinstance(
        creature.get("effectBaseStats"), dict
    ):
        creature["effectBaseStats"] = {
            "armorClass": int(creature.get("armorClass", 10) or 10),
            "maxHitPoints": int(creature.get("maxHitPoints", 0) or 0),
        }
    raw = _raw_combatant_sheet(None, None, creature)
    updated = apply_effect_ops(raw, [operation])
    creature["activeEffects"] = updated.get("temporaryEffects", [])
    rendered = effective_sheet(updated)
    for sheet_field, encounter_field in (
        ("hitPoints", "currentHitPoints"),
        ("maxHitPoints", "maxHitPoints"),
        ("armorClass", "armorClass"),
    ):
        value = rendered.get(sheet_field)
        if isinstance(value, (int, float)):
            creature[encounter_field] = int(value)
    if not creature["activeEffects"]:
        creature.pop("effectBaseStats", None)
    return creature


def _drop_concentration(encounter, characters, source_combatant_id, keep_id=None):
    """Remove concentration owned by one source across all durable targets."""
    for owner, sheet in list((characters or {}).items()):
        if not isinstance(sheet, dict):
            continue
        remove_ops = []
        for effect in sheet.get("temporaryEffects", []) or []:
            if (
                isinstance(effect, dict)
                and effect.get("concentration")
                and effect.get("sourceCombatantId") == source_combatant_id
                and effect.get("concentrationId") != keep_id
            ):
                remove_ops.append(
                    {
                        "op": "remove",
                        "effectId": effect.get("effectId"),
                        "name": effect.get("name"),
                    }
                )
        if remove_ops:
            characters[owner] = apply_effect_ops(sheet, remove_ops)
    for creature in (encounter or {}).get("creatures", []) or []:
        effects = creature.get("activeEffects") if isinstance(creature, dict) else None
        if not isinstance(effects, list):
            continue
        remove_ops = [
            {
                "op": "remove",
                "effectId": effect.get("effectId"),
                "name": effect.get("name"),
            }
            for effect in effects
            if isinstance(effect, dict)
            and effect.get("concentration")
            and effect.get("sourceCombatantId") == source_combatant_id
            and effect.get("concentrationId") != keep_id
        ]
        for operation in remove_ops:
            _apply_encounter_effect_operation(creature, operation)


def _refresh_effect_control_flags(encounter, characters):
    """Project sheet effect control into encounter turn eligibility."""
    for creature in (encounter or {}).get("creatures", []) or []:
        if not isinstance(creature, dict):
            continue
        effects = []
        if creature.get("type") in ("player", "npc"):
            sheet = (characters or {}).get(creature.get("name")) or {}
            effects = sheet.get("temporaryEffects", []) or []
        else:
            effects = creature.get("activeEffects", []) or []
        creature["effectIncapacitated"] = any(
            isinstance(effect, dict) and effect.get("incapacitates") is True
            for effect in effects
        )


def _refresh_character_effect_projections(encounter, characters):
    """Keep encounter display/cache fields aligned with canonical sheets.

    Character sheets own current HP and declarative effects.  Encounter
    copies are operational projections used by turn sequencing and narration;
    refreshing them after every effect operation prevents an Aid-like maximum
    HP change from producing contradictory values such as 15/10 HP.
    """
    for creature in (encounter or {}).get("creatures", []) or []:
        if not isinstance(creature, dict) or creature.get("type") not in (
            "player",
            "npc",
        ):
            continue
        sheet = (characters or {}).get(creature.get("name"))
        if not isinstance(sheet, dict):
            continue
        rendered = effective_sheet(sheet)
        for sheet_field, encounter_field in (
            ("hitPoints", "currentHitPoints"),
            ("maxHitPoints", "maxHitPoints"),
            ("armorClass", "armorClass"),
        ):
            value = rendered.get(sheet_field)
            if isinstance(value, (int, float)):
                creature[encounter_field] = int(value)


def apply_resolution(encounter, characters, resolution):
    """Copy-on-write application with hard bounds. Returns (enc, chars).

    Refuses events already recorded in combatState.appliedEventIds
    (idempotency backstop under commit_turn's primary guard). Clamps:
    HP within [0, max], resource quantities >= 0.
    """
    event = resolution["event"]
    state = (encounter.get("combatState") or {})
    if event["eventId"] in (state.get("appliedEventIds") or []):
        raise ValueError("Event already applied: %s" % event["eventId"])

    new_encounter = deepcopy(encounter)
    new_characters = deepcopy(characters or {})

    for combatant_id, delta in (resolution.get("creatureDeltas") or {}).items():
        creature = combatant_by_id(new_encounter, combatant_id)
        if creature is None:
            continue
        if "currentHitPoints" in delta:
            ceiling = _combatant_max_hp(
                new_encounter,
                new_characters,
                creature,
            ) or int(creature.get("maxHitPoints", delta["currentHitPoints"]) or 0)
            creature["currentHitPoints"] = max(0, min(int(delta["currentHitPoints"]), ceiling))
        if "status" in delta:
            creature["status"] = delta["status"]

    for name, delta in (resolution.get("charDeltas") or {}).items():
        sheet = new_characters.get(name)
        if not isinstance(sheet, dict):
            continue
        if "hitPoints" in delta:
            ceiling = int(
                effective_sheet(sheet).get("maxHitPoints", delta["hitPoints"])
                or 0
            )
            sheet["hitPoints"] = max(0, min(int(delta["hitPoints"]), ceiling))
        if "status" in delta:
            sheet["status"] = delta["status"]

    for resource in event.get("resources", []) or []:
        sheet = new_characters.get(resource.get("owner"))
        if not isinstance(sheet, dict):
            continue
        # Absolute 'after' values make replay idempotent: re-applying the
        # same staged event to an already-updated sheet is a no-op. The
        # delta fallback exists only for events staged before this format.
        if "after" in resource:
            value = max(0, int(resource["after"]))
            setter = lambda current: value
        else:
            setter = lambda current: max(0, current + int(resource["delta"]))
        if resource["kind"] == "ammunition":
            for item in sheet.get("ammunition", []):
                if isinstance(item, dict) and item.get("name") == resource.get("name"):
                    item["quantity"] = setter(int(item.get("quantity", 0) or 0))
                    break
        elif resource["kind"] == "spellSlot":
            level = ((sheet.get("spellcasting") or {}).get("spellSlots") or {}).get(
                resource.get("name"))
            if isinstance(level, dict):
                cap = int(level.get("max", 0) or 0)
                level["current"] = min(cap, setter(int(level.get("current", 0) or 0)))
        elif resource["kind"] == "featureUse":
            for feature in sheet.get("classFeatures", []):
                if isinstance(feature, dict) and feature.get("name") == resource.get("name"):
                    usage = feature.get("usage")
                    if isinstance(usage, dict):
                        cap = int(usage.get("max", 0) or 0)
                        usage["current"] = min(cap, setter(int(usage.get("current", 0) or 0)))
                    break
        elif resource["kind"] == "item":
            for item in sheet.get("equipment", []):
                if isinstance(item, dict) and item.get("item_name") == resource.get("name"):
                    item["quantity"] = setter(int(item.get("quantity", 0) or 0))
                    break

    for op in (resolution.get("effectOps") or event.get("effects") or []):
        if op.get("op") == "add" and isinstance(op.get("effect"), dict):
            added_effect = op["effect"]
            if added_effect.get("concentration") and added_effect.get(
                "sourceCombatantId"
            ):
                _drop_concentration(
                    new_encounter,
                    new_characters,
                    added_effect.get("sourceCombatantId"),
                    keep_id=added_effect.get("concentrationId"),
                )
        if op.get("owner"):
            sheet = new_characters.get(op.get("owner"))
            if not isinstance(sheet, dict):
                raise ValueError("Effect owner is not durably addressable")
            new_characters[op.get("owner")] = apply_effect_ops(sheet, [op])
            continue
        if op.get("combatantId"):
            creature = combatant_by_id(new_encounter, op.get("combatantId"))
            if creature is None or creature.get("type") in ("player", "npc"):
                raise ValueError("Effect combatant is not durably addressable")
            _apply_encounter_effect_operation(creature, op)
            continue
        effects = _effect_destination(new_encounter, new_characters, op)
        if effects is None:
            raise ValueError("Effect target is not durably addressable")
        if op.get("op") == "add" and isinstance(op.get("effect"), dict):
            effect = deepcopy(op["effect"])
            effect_id = effect.get("effectId")
            if effect.get("concentration"):
                source_id = effect.get("sourceCombatantId")
                source = effect.get("source")
                concentration_id = effect.get("concentrationId")
                for identity, candidate_effects in _effect_containers(
                    new_encounter, new_characters
                ):
                    retained = []
                    for existing_effect in candidate_effects:
                        if not (
                            isinstance(existing_effect, dict)
                            and existing_effect.get("concentration")
                        ):
                            retained.append(existing_effect)
                            continue
                        existing_source_id = existing_effect.get(
                            "sourceCombatantId"
                        )
                        if existing_source_id and source_id:
                            same_caster = existing_source_id == source_id
                        else:
                            same_caster = (
                                existing_effect.get("source")
                                or identity.get("owner")
                                or identity.get("name")
                            ) == source
                        same_spell = (
                            concentration_id
                            and existing_effect.get("concentrationId")
                            == concentration_id
                        )
                        if not same_caster or same_spell:
                            retained.append(existing_effect)
                    candidate_effects[:] = retained
            existing = next((i for i, e in enumerate(effects)
                             if isinstance(e, dict) and effect_id is not None
                             and e.get("effectId") == effect_id), None)
            if existing is None:
                effects.append(effect)
            else:
                effects[existing] = effect  # replay-safe upsert
        elif op.get("op") == "remove":
            name = op.get("name") or (op.get("effect") or {}).get("name")
            effect_id = op.get("effectId") or (op.get("effect") or {}).get("effectId")
            retained = [
                e for e in effects
                if not (isinstance(e, dict)
                        and ((effect_id is not None and e.get("effectId") == effect_id)
                             or (effect_id is None and e.get("name") == name)))]
            effects[:] = retained

    new_characters = apply_effect_ticks(
        new_characters,
        event.get("effectTicks") or [],
    )
    new_encounter = apply_encounter_effect_ticks(
        new_encounter,
        event.get("effectTicks") or [],
    )
    down_sources = {
        creature.get("combatantId")
        for creature in new_encounter.get("creatures", []) or []
        if isinstance(creature, dict)
        and creature.get("currentHitPoints") == 0
        and creature.get("combatantId")
    }
    for source_id in down_sources:
        _drop_concentration(new_encounter, new_characters, source_id)
    _refresh_character_effect_projections(new_encounter, new_characters)
    _refresh_effect_control_flags(new_encounter, new_characters)
    return new_encounter, new_characters


def _effect_was_created_in_round(effect, round_number):
    """Recognize resolver-stamped effect IDs created in ``round_number``."""
    if round_number is None or not isinstance(effect, dict):
        return False
    effect_id = effect.get("effectId")
    if not isinstance(effect_id, str):
        return False
    match = _STAMPED_EFFECT_ROUND_RE.search(effect_id)
    if not match:
        return False
    try:
        return int(match.group(1)) == int(round_number)
    except (TypeError, ValueError):
        return False


def plan_effect_ticks(characters, trigger, encounter=None, created_in_round=None):
    """Return absolute, replay-safe duration changes for one trigger.

    At an end-of-round boundary, effects created during that round have not
    yet lasted for a full round.  Callers may identify that round so those
    newly stamped effects begin aging at the following boundary.  Legacy or
    unrecognized effect IDs retain their established tick behavior.
    """
    ticks = []
    for owner, sheet in (characters or {}).items():
        if not isinstance(sheet, dict):
            continue
        for effect in sheet.get("temporaryEffects", []) or []:
            if not isinstance(effect, dict):
                continue
            rounds = effect.get("roundsRemaining")
            if not isinstance(rounds, int):
                continue
            if effect.get("tickTrigger", "end_of_round") != trigger:
                continue
            if _effect_was_created_in_round(effect, created_in_round):
                continue
            after = max(0, rounds - 1)
            ticks.append(
                {
                    "owner": owner,
                    "effectId": effect.get("effectId"),
                    "name": effect.get("name"),
                    "roundsBefore": rounds,
                    "roundsAfter": after,
                    "expired": after == 0,
                    "trigger": trigger,
                }
            )
    for creature in (encounter or {}).get("creatures", []):
        if not isinstance(creature, dict):
            continue
        for effect in creature.get("activeEffects", []) or []:
            if not isinstance(effect, dict):
                continue
            rounds = effect.get("roundsRemaining")
            if not isinstance(rounds, int):
                continue
            if effect.get("tickTrigger", "end_of_round") != trigger:
                continue
            if _effect_was_created_in_round(effect, created_in_round):
                continue
            after = max(0, rounds - 1)
            ticks.append(
                {
                    "combatantId": creature.get("combatantId"),
                    "effectId": effect.get("effectId"),
                    "name": effect.get("name"),
                    "roundsBefore": rounds,
                    "roundsAfter": after,
                    "expired": after == 0,
                    "trigger": trigger,
                }
            )
    return ticks


def apply_effect_ticks(characters, ticks):
    """Apply absolute duration records; safe to replay after partial writes."""
    new_characters = deepcopy(characters or {})
    for tick in ticks or []:
        if not isinstance(tick, dict):
            continue
        sheet = new_characters.get(tick.get("owner"))
        if not isinstance(sheet, dict):
            continue
        effects = sheet.get("temporaryEffects")
        if not isinstance(effects, list):
            continue
        effect_id = tick.get("effectId")
        name = tick.get("name")
        matching = [
            effect
            for effect in effects
            if isinstance(effect, dict)
            and (
                (effect_id is not None and effect.get("effectId") == effect_id)
                or (effect_id is None and effect.get("name") == name)
            )
        ]
        if tick.get("expired"):
            for effect in matching:
                sheet = apply_effect_ops(
                    sheet,
                    [
                        {
                            "op": "remove",
                            "effectId": effect.get("effectId"),
                            "name": effect.get("name"),
                        }
                    ],
                )
            new_characters[tick.get("owner")] = sheet
        else:
            for effect in matching:
                effect["roundsRemaining"] = max(
                    0,
                    int(tick.get("roundsAfter", 0) or 0),
                )
    return new_characters


def apply_encounter_effect_ticks(encounter, ticks):
    """Apply absolute duration records to sheet-less encounter creatures."""
    new_encounter = deepcopy(encounter)
    for tick in ticks or []:
        combatant_id = tick.get("combatantId") if isinstance(tick, dict) else None
        if not combatant_id:
            continue
        creature = combatant_by_id(new_encounter, combatant_id)
        if creature is None:
            continue
        effects = creature.get("activeEffects")
        if not isinstance(effects, list):
            continue
        effect_id = tick.get("effectId")
        name = tick.get("name")
        matching = [
            effect for effect in effects
            if isinstance(effect, dict)
            and (
                (effect_id is not None and effect.get("effectId") == effect_id)
                or (effect_id is None and effect.get("name") == name)
            )
        ]
        if tick.get("expired"):
            for effect in matching:
                _apply_encounter_effect_operation(
                    creature,
                    {
                        "op": "remove",
                        "effectId": effect.get("effectId"),
                        "name": effect.get("name"),
                    },
                )
        else:
            for effect in matching:
                effect["roundsRemaining"] = max(
                    0,
                    int(tick.get("roundsAfter", 0) or 0),
                )
    return new_encounter


def tick_effects(encounter, characters, trigger):
    """Advance round-based effects for one trigger point.

    Only effects carrying the OPTIONAL roundsRemaining field participate;
    legacy wall-clock temporaryEffects (datetime expiration) are ignored
    here and continue to expire elsewhere. Returns (chars, expired) where
    expired lists {owner, name} for narration.
    """
    # Compatibility helper for callers that manage character-sheet effects.
    # The transaction pipeline separately applies encounter-creature ticks.
    ticks = plan_effect_ticks(characters, trigger)
    new_characters = apply_effect_ticks(characters, ticks)
    expired = [
        {"owner": tick.get("owner"), "name": tick.get("name")}
        for tick in ticks
        if tick.get("expired")
    ]
    return new_characters, expired


def check_invariants(encounter, characters):
    """Return violation strings; empty means consistent."""
    violations = []
    state = encounter.get("combatState") or {}
    ids = set()
    for creature in encounter.get("creatures", []):
        cid = creature.get("combatantId")
        if cid in ids:
            violations.append("duplicate combatantId %s" % cid)
        ids.add(cid)
        hp = creature.get("currentHitPoints")
        max_hp = creature.get("maxHitPoints")
        if isinstance(hp, int) and isinstance(max_hp, int) and not 0 <= hp <= max_hp:
            violations.append("%s HP %s outside [0, %s]" % (cid, hp, max_hp))
        if isinstance(hp, int) and hp == 0 and normalize_status(creature.get("status")) == "alive":
            violations.append("%s has 0 HP but status alive" % cid)
        name = creature.get("name")
        sheet = (characters or {}).get(name) if creature.get("type") in ("player", "npc") else None
        if isinstance(sheet, dict) and isinstance(hp, int):
            char_hp = sheet.get("hitPoints")
            if isinstance(char_hp, int) and char_hp != hp:
                violations.append(
                    "%s encounter HP %s != character file HP %s" % (cid, hp, char_hp))
    for actor_id in state.get("actedThisRound", []) or []:
        if actor_id not in ids:
            violations.append("actedThisRound references unknown %s" % actor_id)
    order = state.get("initiativeOrder") or []
    cursor = state.get("turnCursor")
    if order and isinstance(cursor, int) and not 0 <= cursor < len(order):
        violations.append("turnCursor %s outside initiative order" % cursor)
    for name, sheet in (characters or {}).items():
        if not isinstance(sheet, dict):
            continue
        for item in sheet.get("ammunition", []) or []:
            if isinstance(item, dict) and int(item.get("quantity", 0) or 0) < 0:
                violations.append("%s negative ammunition %s" % (name, item.get("name")))
        slots = (sheet.get("spellcasting") or {}).get("spellSlots") or {}
        for level, entry in slots.items():
            if isinstance(entry, dict):
                current, cap = int(entry.get("current", 0) or 0), int(entry.get("max", 0) or 0)
                if current < 0 or current > cap:
                    violations.append("%s %s slots %s outside [0, %s]"
                                      % (name, level, current, cap))
    return violations
