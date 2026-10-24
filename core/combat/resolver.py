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

from core.combat.attacks import (
    attack_sequence,
    FLAT_DAMAGE_DICE,
    is_executable_attack,
)
from core.effects.effective import effective_sheet, modifier_dice, modifier_total
from core.effects.lifecycle import (
    INCAPACITATING_CONDITIONS,
    apply_effect_ops,
    effect_incapacitates,
    sync_condition_states,
)
from core.effects.model import normalize_effect, validate_effect
from core.managers.combat_state import (
    combatant_by_id,
    has_left_fight,
    initiative_eligible_ids,
    is_combatant_targetable,
    is_hostile,
    is_party_member,
    is_turn_eligible,
    normalize_status,
)

_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$")
_STAMPED_EFFECT_ROUND_RE = re.compile(
    r"-R(\d+)-(?:[0-9a-f]{16}|.{1,8})-A\d+-\d+$"
)

PLAYER_UNCONSCIOUS = "unconscious"
NONPLAYER_DEAD = "dead"

# These are corruption/safety envelopes, not implementations of individual
# SRD spells. Normal play sits far below them; values outside the envelope are
# almost certainly a malformed weak-model proposal and must be retried before
# they can become durable state.
_COMBAT_EFFECT_MODIFIER_LIMITS = {
    "armorClass": 20,
    "speed": 300,
    "maxHitPoints": 500,
    "attackRolls": 30,
    "damageRolls": 30,
    "abilityChecks": 30,
    "savingThrows": 30,
    "initiative": 30,
    "spellSaveDC": 30,
    "spellAttackBonus": 30,
}


def _combat_modifier_problem(modifier):
    """Return a retryable problem for an implausibly large effect modifier."""
    stat = modifier.get("stat") if isinstance(modifier, dict) else None
    value = modifier.get("value") if isinstance(modifier, dict) else None
    if type(value) is not int:
        return None
    if isinstance(stat, str) and stat.startswith("abilities."):
        limit = 30
    else:
        limit = _COMBAT_EFFECT_MODIFIER_LIMITS.get(stat, 30)
    if abs(value) > limit:
        return "effect modifier %s=%s exceeds combat safety bound +/- %s" % (
            stat,
            value,
            limit,
        )
    return None


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

    def peek(self, die, count):
        """The next ``count`` values for that die, not consumed."""
        return list(self._pools.get(die) or [])[:max(0, int(count))]


def parse_dice(expression, flat_ok=False):
    """'2d6+3' -> (count, sides, modifier). Raises ValueError on junk.
    With ``flat_ok``, exactly "flat" (a flat-damage row, NUM-H3c) is (0, 0, 0)."""
    if flat_ok and str(expression or "").strip() == FLAT_DAMAGE_DICE:
        return 0, 0, 0
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


# K1 (D-KW-12, D-HC-5): the row the model chose is named by its typed position
# in the list sent to it in that request, {combatantId, family, index}
# (abilityRow, the payload's rowRef); the name the model writes is display
# text and never finds a row. Q-P6-2: positions and value compares, no digest.
ROW_FAMILIES = ("attacksAndSpellcasting", "actions", "specialAbilities")


def json_ref(ref):
    """A row reference as the model writes it, for correction text."""
    import json
    return json.dumps(ref, sort_keys=True) if isinstance(ref, dict) else "(none)"


def json_ref_list(rows):
    """[{rowRef, name}] as correction text."""
    import json
    return json.dumps(rows, sort_keys=True)


def attack_family(actor_sheet):
    """The one list the actor's attacks are read from (_action_entries)."""
    return ("attacksAndSpellcasting"
            if isinstance((actor_sheet or {}).get("attacksAndSpellcasting"), list) else "actions")


def row_at(actor_sheet, ref, families, actor_id):
    """The dict row at ``ref`` when it names ``actor_id``'s own list (F6), a
    family in ``families`` and an index in range; None otherwise."""
    if actor_id is None or not isinstance(ref, dict) or ref.get("combatantId") != actor_id:
        return None
    family, index = ref.get("family"), ref.get("index")
    if family not in families or type(index) is not int or index < 0:
        return None
    entries = (actor_sheet or {}).get(family)
    if not isinstance(entries, list) or index >= len(entries):
        return None
    row = entries[index]
    return row if isinstance(row, dict) else None


def attack_row(actor_sheet, ref, actor_id):
    """The row ``ref`` names in the actor's attack list, or None."""
    return row_at(actor_sheet, ref, (attack_family(actor_sheet),), actor_id)


def is_save_row(entry):
    return isinstance(entry, dict) and isinstance(entry.get("save"), dict) and entry.get("kind", "save") == "save"


def save_row(actor_sheet, ref, actor_id):
    """MS-a: the listed save ability ``ref`` names, or None."""
    row = row_at(actor_sheet, ref, ROW_FAMILIES, actor_id)
    return row if is_save_row(row) else None


def row_refs(actor_sheet, actor_id, families, keep=None):
    """[{rowRef, name}] for the actor's dict rows in ``families`` (list order)
    that ``keep`` accepts: the rows a correction lists for the model."""
    listed = []
    for family in families:
        entries = (actor_sheet or {}).get(family)
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if isinstance(entry, dict) and (keep is None or keep(entry)):
                listed.append({"rowRef": {"combatantId": actor_id, "family": family, "index": index},
                               "name": entry.get("name")})
    return listed


def attack_row_refs(actor_sheet, actor_id, keep=None):
    """row_refs over the actor's attack list, executable rows only."""
    return row_refs(actor_sheet, actor_id, (attack_family(actor_sheet),),
                    lambda e: is_executable_attack(e) and (keep is None or keep(e)))


def _sheet_combatants(encounter):
    """{sheet name: combatantId} for names exactly one combatant carries
    (P-4: a name two combatants share gets no row references)."""
    seen = {}
    for creature in (encounter or {}).get("creatures") or []:
        if isinstance(creature, dict) and isinstance(creature.get("name"), str) and creature.get("combatantId"):
            seen.setdefault(creature["name"], []).append(creature["combatantId"])
    return {name: ids[0] for name, ids in seen.items() if len(ids) == 1}


def sent_row_lists(encounter, characters):
    """{combatantId: {family: [rows]}}: a deep copy of the row lists T096 is
    sent, kept beside the request for the reply's value check (P-2)."""
    owners = _sheet_combatants(encounter)
    kept = {}
    for name, sheet in (characters or {}).items():
        cid = owners.get(name)
        if cid is not None and isinstance(sheet, dict):
            kept[cid] = {family: deepcopy(sheet[family]) for family in ROW_FAMILIES
                         if isinstance(sheet.get(family), list)}
    return kept


def with_row_refs(sheets, encounter):
    """The payload sheets, each dict row of ROW_FAMILIES carrying its own
    ``rowRef``. The lists are deep-copied first: _relevant_sheet hands over
    the saved sheet's own lists, which are never written (P-2)."""
    owners = _sheet_combatants(encounter)
    out = {}
    for name, sheet in (sheets or {}).items():
        cid = owners.get(name)
        if cid is None or not isinstance(sheet, dict):
            out[name] = sheet
            continue
        sheet = dict(sheet)
        for family in ROW_FAMILIES:
            if not isinstance(sheet.get(family), list):
                continue
            copied = deepcopy(sheet[family])
            for index, entry in enumerate(copied):
                if isinstance(entry, dict):
                    entry["rowRef"] = {"combatantId": cid, "family": family, "index": index}
            sheet[family] = copied
        out[name] = sheet
    return out


def stale_row_refs(batch, sent, encounter, characters):
    """The reply's value check (2.1): [(actorId, problem, rows)] for each
    abilityRow or bonusAction.abilityRow whose row on the sheet no longer
    equals the row sent at that position. Values are compared; nothing is
    hashed. A reference to nothing that was sent is left to its reader."""
    problems = []
    for intent in ((batch or {}).get("intents") or []):
        if not isinstance(intent, dict):
            continue
        actor_id = intent.get("actorId")
        actor = combatant_by_id(encounter, actor_id)
        if actor is None:
            continue
        bonus = intent.get("bonusAction")
        refs = [intent.get("abilityRow"), bonus.get("abilityRow") if isinstance(bonus, dict) else None]
        sheet = _raw_combatant_sheet(encounter, characters, actor)
        for ref in refs:
            if not isinstance(ref, dict) or ref.get("combatantId") != actor_id:
                continue
            family, index = ref.get("family"), ref.get("index")
            kept = ((sent or {}).get(actor_id) or {}).get(family)
            if not isinstance(kept, list) or type(index) is not int or not 0 <= index < len(kept):
                continue
            if row_at(sheet, ref, ROW_FAMILIES, actor_id) != kept[index]:
                problems.append((actor_id, "%s's row %s[%d] changed since it was sent" % (
                    actor.get("name"), family, index), row_refs(sheet, actor_id, ROW_FAMILIES)))
    return problems


def _stated_save_spec(entry, key="save"):
    """The intent-shaped save {type, dc, halfOnSave} a stat-block entry states.

    ``key`` is "save" (a save ability) or "rider" (the save a hit forces).
    """
    save = (entry or {}).get(key) or {}
    try:
        dc = int(save.get("dc"))
    except (TypeError, ValueError):
        return None
    ability = str(save.get("ability") or "").strip().lower()
    if not ability or dc < 1:
        return None
    return {"type": ability, "dc": dc, "halfOnSave": bool(save.get("halfOnSave"))}


def _stated_on_fail(entry, key="save"):
    """(dice, conditions, roundsRemaining) a stat-block save states on a failure.

    ``dice`` is (count, sides, flat) when the entry carries rollable damage
    dice, else None; ``conditions`` is the typed SRD list, lowercased.
    """
    on_fail = ((entry or {}).get(key) or {}).get("onFail") or {}
    dice = None
    try:
        count, sides, modifier = parse_dice(on_fail.get("damageDice"))
        dice = (count, sides, modifier + int(on_fail.get("damageBonus", 0) or 0))
    except (TypeError, ValueError):
        dice = None
    conditions = [
        str(name).strip().lower()
        for name in (on_fail.get("conditions") or [])
        if isinstance(name, str) and name.strip()
    ]
    rounds = on_fail.get("roundsRemaining")
    return dice, conditions, (rounds if type(rounds) is int and rounds > 0 else None)


def _save_ability_feedback(entry):
    """Rejection feedback that tells the model how to declare a listed save ability."""
    spec = _stated_save_spec(entry) or {}
    _dice, conditions, _rounds = _stated_on_fail(entry)
    return {
        "name": entry.get("name"),
        "type": spec.get("type"),
        "dc": spec.get("dc"),
        "halfOnSave": spec.get("halfOnSave", False),
        "conditions": conditions,
    }


def _recharge_spec(entry):
    """(min, max) on a d6 when a stat-block entry recharges (MS-b), else None."""
    recharge = (entry or {}).get("recharge")
    if not isinstance(recharge, dict):
        return None
    try:
        low, high = int(recharge.get("min")), int(recharge.get("max"))
    except (TypeError, ValueError):
        return None
    if not 1 <= low <= high <= 6:
        return None
    return low, high


def _recharge_spent(creature, name):
    """True when the creature's recharge record marks the named ability spent."""
    records = (creature or {}).get("recharge")
    if not isinstance(records, dict):
        return False
    wanted = str(name or "").strip().lower()
    for key, record in records.items():
        if str(key).strip().lower() == wanted and isinstance(record, dict):
            return record.get("state") == "spent"
    return False


def _spend_recharge(resolution, event, actor, entry):
    """MS-b: using a recharge ability marks it spent on the actor's record.

    The record rides on the creature (the T096 projection shows it), the
    journal carries the same record so a replay rebuilds it, and the next
    start of the actor's turn draws the d6 (recharge_at_turn_start).
    """
    spec = _recharge_spec(entry)
    if spec is None or not actor or not actor.get("combatantId"):
        return
    name = str(entry.get("name") or "").strip()
    record = {"state": "spent", "min": spec[0], "max": spec[1],
              "rechargesOn": "%d-%d" % spec}
    current = deepcopy(actor.get("recharge")) if isinstance(actor.get("recharge"), dict) else {}
    current[name] = record
    resolution["creatureDeltas"].setdefault(actor["combatantId"], {})["recharge"] = current
    event.setdefault("recharge", []).append(dict(record, actorId=actor["combatantId"], name=name))


def recharge_at_turn_start(encounter, actor_ids, rolls):
    """SRD recharge: at the start of its turn a creature rolls a d6 per spent ability.

    Called at the turn claim, before any model work; the draws come from the
    persisted roll source so the pending turn's ``rechargeRolls`` is the
    replay authority, and the creature record is cleared in place when the
    die lands in the ability's range. Returns the records.
    """
    records = []
    for actor_id in actor_ids or []:
        creature = combatant_by_id(encounter, actor_id)
        if creature is None or not isinstance(creature.get("recharge"), dict):
            continue
        for name, record in list(creature["recharge"].items()):
            if not isinstance(record, dict) or record.get("state") != "spent":
                continue
            try:
                low, high = int(record.get("min")), int(record.get("max"))
            except (TypeError, ValueError):
                continue
            value = _take_roll(rolls, "d6", "recharge", actor_id=actor_id)
            recharged = low <= value <= high
            if recharged:
                del creature["recharge"][name]
            records.append({
                "actorId": actor_id, "name": name, "die": "d6", "value": value,
                "rechargesOn": "%d-%d" % (low, high), "recharged": recharged,
            })
        if not creature["recharge"]:
            creature.pop("recharge", None)
    return records


def stage_dodge(encounter, resolution):
    """SRD Dodge: a committed ``dodge`` action marks its actor.

    The typed action is the only input; ``defend`` stays an empty outcome.
    The event's ``dodge`` record is the journal authority (resolution_from_event
    rebuilds the marker from it) and the creature's ``dodging`` record makes
    attack rolls against it disadvantaged until the start of its next turn.
    """
    event = resolution["event"]
    actor = combatant_by_id(encounter, event.get("actorId"))
    if actor is None or not actor.get("combatantId"):
        return
    event["dodge"] = {"actorId": actor["combatantId"]}
    resolution["creatureDeltas"].setdefault(actor["combatantId"], {})["dodging"] = {
        "sinceEventId": event["eventId"]
    }


def end_dodge(event, creature, resolution=None):
    """The Dodge ends at the start of the dodger's next turn: the actor's own
    next event (resolved or skipped) records ``dodgeEnded``, whatever the
    window's shape, and only that actor's marker clears. A Dodge taken in
    the same event is staged after this and stands."""
    if not isinstance((creature or {}).get("dodging"), dict) or not creature.get("combatantId"):
        return
    event["dodgeEnded"] = {"actorId": creature["combatantId"]}
    if resolution is not None:
        resolution["creatureDeltas"].setdefault(creature["combatantId"], {})["dodging"] = None


def _last_weapon_kind(row_type, thrown):
    """#851: the lastWeaponRows slot a swung row fills, or None. A monster
    stat-block action carries no type and a spell row is not a weapon: both
    fill nothing."""
    if row_type == "melee":
        return "melee"
    if row_type == "ranged":
        return "thrown" if thrown is True else "ranged"
    return None


def _stage_last_weapon_rows(encounter, characters, resolution):
    """#851: put the actor's lastWeaponRows into the resolution's creatureDeltas.
    Called where an event is resolved and where a staged one is replayed, so
    the live resolution and its replay carry the same value."""
    last_rows = last_weapon_rows_delta(encounter, characters, resolution["event"])
    if last_rows is not None:
        resolution["creatureDeltas"].setdefault(last_rows[0], {})["lastWeaponRows"] = last_rows[1]


def last_weapon_rows_delta(encounter, characters, event):
    """#851: ``(combatantId, lastWeaponRows)`` after this event, or None.

    The actor's last swung weapon row per kind (melee, ranged, thrown), read
    from the event's typed swings, so resolve_intent, resolve_adjudicated and
    resolution_from_event write the same value. A swing staged before
    #851 names only its row; its type is read from the actor's sheet. The
    record lives on the encounter combatant for this fight only.

    The player's own attacks are adjudicated and carry no swings: an
    adjudicated ``attack`` whose abilityRow names a listed row on the actor's
    sheet records that row (K1: never by the ability text).
    """
    swings = ((event or {}).get("outcome") or {}).get("swings") or []
    actor = combatant_by_id(encounter, (event or {}).get("actorId"))
    if actor is None or not actor.get("combatantId"):
        return None
    rows = {}
    sheet = None
    intent = (event or {}).get("intent") or {}
    adjudicated = ((event or {}).get("outcome") or {}).get("kind") == "adjudicated"
    # A known attack with no swing (no ammunition left) fired nothing: no row.
    if not swings and adjudicated and intent.get("action") == "attack" and intent.get("abilityRow"):
        entry = attack_row(_raw_combatant_sheet(encounter, characters, actor), intent["abilityRow"],
                           actor["combatantId"])
        if isinstance(entry, dict):
            swings = [{"ability": entry.get("name"), "rowType": entry.get("type"),
                       "thrown": entry.get("thrown") is True}]
    for swing in swings:
        if not isinstance(swing, dict) or not swing.get("ability"):
            continue
        if "rowType" in swing:
            row_type, thrown = swing.get("rowType"), swing.get("thrown")
        else:
            if sheet is None:
                sheet = _raw_combatant_sheet(encounter, characters, actor)
            entry = _find_action(sheet, swing["ability"]) or {}
            row_type, thrown = entry.get("type"), entry.get("thrown")
        kind = _last_weapon_kind(row_type, thrown)
        if kind:
            rows[kind] = {"ability": swing["ability"], "eventId": event.get("eventId")}
    if not rows:
        return None
    current = actor.get("lastWeaponRows")
    merged = deepcopy(current) if isinstance(current, dict) else {}
    merged.update(rows)
    return actor["combatantId"], merged


def _stat_block_condition_op(encounter, event_id, actor, target, entry, conditions, rounds, index):
    """A failed-save condition effect the stat block states, normalized like a model op.

    Returns (op, problems); op is None when the effect contract refuses it.
    """
    effect = {
        "name": str(entry.get("name") or "").strip(),
        "description": str(entry.get("description") or entry.get("name") or "").strip(),
        "effectId": "EFF-%s-%d" % (event_id, index),
        "authoredBy": "engine",
        "sourceEncounterId": encounter.get("encounterId"),
        "source": actor.get("name") or "combat",
        "modifiers": [],
        "conditions": list(conditions),
        "incapacitates": False,
        "created": {"encounterId": encounter.get("encounterId")},
    }
    if rounds:
        effect.update({"roundsRemaining": rounds, "tickTrigger": "end_of_round",
                       "durationKind": "rounds", "duration": "%s rounds" % rounds})
    else:
        effect.update({"durationKind": "encounter", "duration": "encounter"})
    if effect_incapacitates(effect):
        effect["incapacitates"] = True
    if actor.get("combatantId"):
        effect["sourceCombatantId"] = actor["combatantId"]
    try:
        effect = normalize_effect(effect)
    except ValueError as exc:
        return None, [str(exc)]
    problems = validate_effect(effect, require_managed=True)
    if problems:
        return None, problems
    op = {"op": "add", "applyOn": "failedSave", "saveTargetId": target["combatantId"], "effect": effect}
    if target.get("type") in ("player", "npc"):
        op["owner"] = target.get("name")
    else:
        op["combatantId"] = target["combatantId"]
    return op, []


def _target_save(encounter, characters, sheet, target, spec, rolls, actor_id, event, focus):
    """One target's save for a stat-block rider: engine for a party sheet, else arithmetic.

    Journals the roll record (and the engine line on ``focus``) exactly as
    resolve_adjudicated does, and returns the verdict.
    """
    engine_save = (
        _engine_save(sheet, spec.get("type"), spec.get("dc", 10) or 10, rolls, actor_id, target.get("combatantId"))
        if sheet is not None else None
    )
    if engine_save is not None:
        from core.nql import checks as nql_checks
        result, faces, added = engine_save
        saved = bool(result.success)
        event["rolls"].append({
            "die": "d20", "value": result.kept if result.kept is not None else 0,
            "purpose": "save", "combatantId": target["combatantId"],
            "bonus": result.bonus, "success": saved, "engine": True,
            "faces": faces, "kept": result.kept, "mode": result.mode,
            "sources": result.sources, "total": result.total, "margin": result.margin,
            **({"added": added} if added else {}),
        })
        line = nql_checks.describe(result)
        event.setdefault("engineChecks", []).append(line)
        focus.setdefault("engineChecks", []).append(line)
        return saved
    die = _take_roll(rolls, "d20", "save", actor_id=actor_id, target_id=target.get("combatantId"), ability=spec.get("type"))
    bonus = _save_bonus(encounter, characters, target, spec.get("type"))
    added = _save_added_dice(encounter, characters, target, spec.get("type"), rolls)
    saved = die + bonus + sum(roll["value"] for roll in added) >= int(spec.get("dc", 10) or 10)
    record = {"die": "d20", "value": die, "purpose": "save", "combatantId": target["combatantId"],
              "bonus": bonus, "success": saved}
    if added:
        record["added"] = added
    if sheet is not None:
        record["engine"] = False
    event["rolls"].append(record)
    return saved


def _living_target_ids(encounter):
    return [c["combatantId"] for c in encounter.get("creatures", [])
            if is_combatant_targetable(c)]


def _living_opponent_ids(encounter, actor):
    # #1397: an observer (initiativeEligible false) is not fighting, so it is
    # never an opponent; legacy encounters keep every row.
    eligible = initiative_eligible_ids(encounter)
    return [
        target_id
        for target_id in _living_target_ids(encounter)
        if target_id in eligible
        and (combatant_by_id(encounter, target_id) or {}).get("faction")
        != actor.get("faction")
    ]


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
                legalTargets=_living_opponent_ids(encounter, actor),
                retryable=True,
            )
        if target_id is not None and combatant_by_id(encounter, target_id) is None:
            return False, Rejection(
                reason="unknown targetId: %r" % target_id,
                legalTargets=_living_opponent_ids(encounter, actor), retryable=True)
        target = combatant_by_id(encounter, target_id) if target_id else None
        if target is not None and has_left_fight(target):
            # #1379: the target left the fight (flee or yield) earlier in this
            # batch; it is not down, and the correction says so.
            return False, Rejection(
                reason="target %s left the fight" % target_id,
                legalTargets=_living_opponent_ids(encounter, actor), retryable=True,
                targetLeft=True)
        if target is not None and not is_combatant_targetable(target):
            # targetDown marks a PROJECTED state: the target fell to an earlier
            # intent of the same ordered batch. The correction text keys on it.
            return False, Rejection(
                reason="target %s is already down" % target_id,
                legalTargets=_living_opponent_ids(encounter, actor), retryable=True,
                targetDown=True)
        if strict and target is not None and target_id not in initiative_eligible_ids(encounter):
            # #1401: an observer (initiativeEligible false) is not fighting; a known
            # attack on it is refused. Legacy encounters list every row.
            return False, Rejection(
                reason="target %s is not in the fight" % target_id,
                legalTargets=_living_opponent_ids(encounter, actor), retryable=True,
                targetNotInFight=True)
        if strict and target is not None and target.get("faction") == actor.get("faction"):
            return False, Rejection(
                reason="%s cannot attack ally %s" % (actor_id, target_id),
                legalTargets=_living_opponent_ids(encounter, actor),
                retryable=True)
        if strict:
            # K1: the row is the one abilityRow names; the ability text is display only.
            ref = intent.get("abilityRow")
            entry = attack_row(sheet, ref, actor_id)
            stated = save_row(sheet, ref, actor_id)
            if stated is not None:
                # MS-a: a save ability is not an attack roll; the correction
                # names the adjudicated shape instead of steering to a bite.
                feedback = _save_ability_feedback(stated)
                feedback["rowRef"] = deepcopy(ref)
                return False, Rejection(
                    reason="%s is a save ability of %s: declare it with mode "
                           "'adjudicated', abilityRow %s, ability %r and save {type: %r, dc: %s}"
                           % (stated.get("name"), actor.get("name"), json_ref(ref), stated.get("name"),
                              feedback.get("type"), feedback.get("dc")),
                    legalRows=attack_row_refs(sheet, actor_id), retryable=True,
                    saveAbility=feedback)
            if entry is None or not is_executable_attack(entry):
                return False, Rejection(
                    reason="%s has no listed attack at abilityRow %s (ability %r)"
                           % (actor.get("name"), json_ref(ref), intent.get("ability")),
                    legalRows=attack_row_refs(sheet, actor_id), retryable=True)
            if _recharge_spent(actor, entry.get("name")):
                # MS-b: a spent recharge ability waits for its d6 at the
                # start of the actor's turn; the correction names the rest.
                return False, Rejection(
                    reason="%s is recharging for %s (it returns on a d6 at the start of its turn)"
                           % (entry.get("name"), actor.get("name")),
                    legalRows=attack_row_refs(sheet, actor_id,
                                              lambda e: not _recharge_spent(actor, e.get("name"))),
                    retryable=True, recharging=entry.get("name"))
            if _spends_ammunition(entry) and _ammunition_left(sheet, entry) == 0:
                return False, Rejection(
                    reason="%s has no ammunition left" % actor.get("name"),
                    legalRows=attack_row_refs(sheet, actor_id, lambda e: not _spends_ammunition(e)),
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


def _spends_ammunition(entry):
    """#801: a ranged row shoots ammunition; a row typed ``thrown`` (the engine's
    thrown grant, startup_rows) is its own projectile and spends none."""
    return isinstance(entry, dict) and entry.get("type") == "ranged" and entry.get("thrown") is not True


def _ammunition_row(sheet, entry):
    """#822, D-HC-1: the one ammunition row a ranged swing of ``entry`` spends from, or None.

    A row is identified only by its typed ``catalog_id``; a row without one is of unknown type. When the
    swung row has an ``ammunitionType`` (both engine definition ids), the first stocked row of that id is
    chosen, else the first stocked row of unknown type; a row typed to another id never is. Without a type,
    the first stocked row, as before. The validation, the cap and the spend all use this row.

    Only rows the rules engine holds are chosen (``genesis.ammunition_rows``, its own stock list): the engine
    keeps one row per stock id, so a second row sharing that id (two rows named "Arrows") is one it would never
    debit, and choosing it would leave the spend and the engine apart (PR-5)."""
    from core.nql import genesis

    wanted = (entry or {}).get("ammunitionType")
    held = {id(row) for _stock, row in genesis.ammunition_rows(sheet or {}, [])}
    stocked = [item for item in (sheet or {}).get("ammunition", []) or []
               if isinstance(item, dict) and id(item) in held and int(item.get("quantity", 0) or 0) > 0]
    if not (isinstance(wanted, str) and wanted):
        return stocked[0] if stocked else None
    for item in stocked:
        if item.get("catalog_id") == wanted:
            return item
    for item in stocked:
        if not (isinstance(item.get("catalog_id"), str) and item.get("catalog_id")):
            return item
    return None


def _ammunition_left(sheet, entry):
    """The quantity of the row ``_ammunition_row`` gives, 0 when none."""
    item = _ammunition_row(sheet, entry)
    return int(item.get("quantity", 0) or 0) if item is not None else 0


def _engine_ammunition(sheet, name, delta, record):
    """AM: the rules engine spends (recoverable) or adds ammunition on a party sheet.

    One request per attack event. The engine's quantity and pending count are
    journaled on the resource record (after, recoverableAfter, engine true) so
    replay writes the same values without the engine. Returns True when the
    engine answered, False when it was unavailable (the caller keeps today's
    arithmetic with engine false), or a refusal string (a short stock).
    """
    if type(delta) is not int or delta == 0 or not isinstance(sheet, dict):
        return False
    try:
        from core.nql import ammunition as nql_ammunition
        if delta < 0:
            outcome = nql_ammunition.spend(sheet, name, -delta, recoverable=True)
        else:
            outcome = nql_ammunition.add(sheet, name, delta)
    except Exception as exc:  # engine wrapper faults never stop a fight
        _warn_ammunition(sheet, name, delta, str(exc))
        return False
    if not outcome.ok:
        if (outcome.fault or {}).get("code") == "E_QUANTITY":
            return outcome.reason
        _warn_ammunition(sheet, name, delta, outcome.reason)
        return False
    record["after"] = int(outcome.quantity or 0)
    record["recoverableAfter"] = int(outcome.recoverable or 0)
    record["engine"] = True
    try:
        from utils.enhanced_logger import info as _info
        _info(
            "AM: %s %s %+d -> %s (%s recoverable) [engine]"
            % (sheet.get("name"), name, delta, record["after"], record["recoverableAfter"]),
            category="combat_events",
        )
    except Exception:
        pass
    return True


def _warn_ammunition(sheet, name, delta, reason):
    try:
        from utils.enhanced_logger import warning as _warning
        _warning(
            "AM: %s %s %+d applied without the engine (%s)" % (sheet.get("name"), name, delta, reason),
            category="combat_events",
        )
    except Exception:
        pass


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


# #669: class-feature heals with a typed SRD 5.2 rule. Keyed by the feature's
# name before " (", as the leveling tables key class features; an intent uses
# one when its typed ability, by that same key (casefolded), names one of the
# actor's own classFeatures. Nothing is read from descriptions. The table
# grows only on an observed failure.
FEATURE_HEALS = {
    # Preserve Life: a pool of 5 x Cleric level, shared among Bloodied
    # creatures (half their Hit Points or fewer), none restored above half
    # its Hit Point maximum. It is paid for with a Channel Divinity use.
    "Preserve Life": {"class": "cleric", "pool_per_level": 5, "resource": "Channel Divinity"},
}


def feature_heal_key(name):
    """The FEATURE_HEALS key of a feature name: the part before " (",
    casefolded. Used wherever an intent's ability is compared to a sheet's
    feature name, so both sides are read the same way."""
    return name.split(" (", 1)[0].strip().casefold() if isinstance(name, str) else None


# #881: class-feature heals whose amount is a typed formula: count d sides
# plus a typed bonus (the class level, or F1's Wisdom modifier). Keyed like
# FEATURE_HEALS (feature_heal_key). The table grows only on an observed
# failure.
FEATURE_HEAL_FORMULAS = {
    "Second Wind": {"class": "fighter", "count": 1, "sides": 10, "plus": "class_level"},
    # F1 (D-FL-2): Divine Spark, SRD 5.2.1 p.36, a Cleric's Channel Divinity
    # option from Cleric 2: 1d8 + Wisdom modifier (2d8/3d8/4d8 at Cleric
    # 7/13/18) to one other creature, never the cleric.
    "Divine Spark": {"class": "cleric", "min_level": 2, "count_by_level": ((18, 4), (13, 3), (7, 2), (2, 1)),
                     "sides": 8, "plus": "wisdom_mod", "target": "other"},
}

# F1 (plan-feature-limit-engine-r0, D-FL-1): the heal options each featureUse
# pool pays for, keyed like the tables above. A heal's limit follows the pool
# the intent spends; the typed featureName (8b), else the ability, picks the
# option, and a pool with one option needs no name. Pools not listed here
# keep #669 and #881 as they were.
POOL_HEALS = {
    "Channel Divinity": ("Preserve Life", "Divine Spark"),
    "Second Wind": ("Second Wind",),
}


def feature_heal_formula(sheet, feature_name):
    """#881: {feature, count, sides, bonus, label, target} of a formula heal
    the sheet's class uses, or None: no row, another class, below the row's
    level, or no typed level or score (logged once)."""
    wanted = feature_heal_key(feature_name)
    key = next((k for k in FEATURE_HEAL_FORMULAS if feature_heal_key(k) == wanted), None)
    if key is None or not isinstance(sheet, dict):
        return None
    row = FEATURE_HEAL_FORMULAS[key]
    if str(sheet.get("class") or "").strip().casefold() != row["class"]:
        return None
    level = sheet.get("level")
    bonus = label = None
    if type(level) is int and level >= row.get("min_level", 1):
        if row["plus"] == "class_level":
            bonus, label = level, "%s level %d" % (row["class"].capitalize(), level)
        else:
            score = (sheet.get("abilities") or {}).get("wisdom")
            if type(score) is int:
                bonus = (score - 10) // 2
                label = "Wisdom modifier %+d" % bonus
    if bonus is None:
        try:
            from utils.enhanced_logger import info as _info
            _info("FH: %s %s formula not applied (level %r)" % (sheet.get("name"), key, level),
                  category="combat_events")
        except Exception:
            pass
        return None
    count = row.get("count") or next(n for floor, n in row["count_by_level"] if level >= floor)
    return {"feature": key, "count": count, "sides": row["sides"], "bonus": bonus, "label": label,
            "target": row.get("target", "self")}


def declared_heal(entry):
    """A target entry's declared hpDelta as an integer (0 when unreadable)."""
    try:
        return int((entry or {}).get("hpDelta", 0) or 0)
    except (TypeError, ValueError):
        return 0


def intent_feature_name(intent):
    """8b: the name that picks a class-feature heal's rule: the typed
    featureName, else (an older or untyped intent) the ability."""
    name = (intent or {}).get("featureName")
    return name if isinstance(name, str) and name.strip() else (intent or {}).get("ability")


def pool_heal_options(sheet, pool):
    """F1: the heal options of ``pool`` the sheet qualifies for, in table
    order, as {option, name}. A FEATURE_HEALS option needs the class and its
    own classFeatures row (H2), and ``name`` is that row as written; a
    formula option needs the class and the row's minimum level."""
    if not isinstance(sheet, dict):
        return []
    sheet_class = str(sheet.get("class") or "").strip().casefold()
    level = sheet.get("level")
    rows = {feature_heal_key(f["name"]): f["name"] for f in sheet.get("classFeatures") or []
            if isinstance(f, dict) and isinstance(f.get("name"), str)}
    options = []
    for option in POOL_HEALS.get(pool, ()):
        key = feature_heal_key(option)
        if option in FEATURE_HEALS:
            if sheet_class == FEATURE_HEALS[option]["class"] and key in rows:
                options.append({"option": option, "name": rows[key]})
            continue
        row = FEATURE_HEAL_FORMULAS[option]
        minimum = row.get("min_level")
        if sheet_class != row["class"] or (minimum is not None and (type(level) is not int or level < minimum)):
            continue
        options.append({"option": option, "name": rows.get(key, option)})
    return options


def feature_heal_names(sheet):
    """8b: the featureName values a sheet may use: the heal options it
    qualifies for, over every POOL_HEALS pool it holds a classFeatures row
    for (the list the T096 payload gives as featureNames)."""
    held = {feature_heal_key(f.get("name")) for f in (sheet or {}).get("classFeatures") or [] if isinstance(f, dict)}
    names = []
    for pool in POOL_HEALS:
        if feature_heal_key(pool) in held:
            names.extend(o["name"] for o in pool_heal_options(sheet, pool) if o["name"] not in names)
    return names


def spent_heal_pool(encounter, proposal):
    """F1: (POOL_HEALS key, its spend records) for the actor's own featureUse
    spend of a pool with heal options, matched by the record's typed name
    (the resource the engine debits), or (None, [])."""
    owner = (combatant_by_id(encounter, proposal.get("actorId")) or {}).get("name")
    for record in proposal.get("resources") or []:
        if not (isinstance(record, dict) and record.get("kind") == "featureUse" and record.get("owner") == owner
                and type(record.get("delta")) is int and record["delta"] < 0):
            continue
        pool = next((p for p in POOL_HEALS if feature_heal_key(p) == feature_heal_key(record.get("name"))), None)
        if pool is not None:
            return pool, [r for r in proposal.get("resources") or [] if isinstance(r, dict)
                          and r.get("kind") == "featureUse" and r.get("owner") == owner
                          and feature_heal_key(r.get("name")) == feature_heal_key(pool)]
    return None, []


def _feature_heal_selection(encounter, characters, proposal, targets):
    """F1: how one intent's class-feature heal is limited, as (feature, pool,
    formula, refusal).

    With the actor's own spend of a POOL_HEALS pool, the option the typed
    featureName (8b), else the ability, names picks the rule: a FEATURE_HEALS
    option gives #669's (feature, pool), a formula option its #881 formula.
    A spend that names none of the actor's options for that pool but
    declares a heal is a refusal {pool, options, ability}. Without such a
    spend #669's name-keyed rule stands as before."""
    picked = intent_feature_name(proposal)
    pool, spends = spent_heal_pool(encounter, proposal)
    if pool is None:
        feature, amount = _feature_heal_rule(encounter, characters, proposal, picked)
        return feature, amount, None, None
    sheet = (characters or {}).get((combatant_by_id(encounter, proposal.get("actorId")) or {}).get("name"))
    options = pool_heal_options(sheet, pool)
    chosen = next((o for o in options if feature_heal_key(o["option"]) == feature_heal_key(picked)), None)
    if chosen is None and len(POOL_HEALS[pool]) == 1 and options:
        chosen = options[0]
    if chosen is None:
        if not any(declared_heal(entry) > 0 for entry in targets):
            return None, None, None, None
        return None, None, None, {"pool": spends[0].get("name"), "options": [o["name"] for o in options],
                                  "ability": picked}
    if chosen["option"] in FEATURE_HEALS:
        feature, amount = _feature_heal_rule(encounter, characters, proposal, chosen["name"])
        return feature, amount, None, None
    return None, None, feature_heal_formula(sheet, chosen["option"]), None


def _feature_heal_rule(encounter, characters, proposal, name=None):
    """(feature name, pool) when the intent's typed ability (or ``name``) is
    one of the actor's own class features with a FEATURE_HEALS rule, else
    (None, None). The pool is None when the class level cannot be read from
    typed fields (the check is then skipped and logged once)."""
    ability = proposal.get("ability") if name is None else name
    actor = combatant_by_id(encounter, proposal.get("actorId"))
    sheet = (characters or {}).get((actor or {}).get("name"))
    if not isinstance(ability, str) or not isinstance(sheet, dict):
        return None, None
    wanted = feature_heal_key(ability)
    feature = next((f.get("name") for f in sheet.get("classFeatures") or []
                    if isinstance(f, dict) and isinstance(f.get("name"), str) and feature_heal_key(f["name"]) == wanted), None)
    rule = next((r for key, r in FEATURE_HEALS.items() if key.casefold() == wanted), None)
    if feature is None or rule is None:
        return None, None
    ability = feature
    level = sheet.get("level")
    if str(sheet.get("class") or "").strip().casefold() != rule["class"] or type(level) is not int or level < 1:
        try:
            from utils.enhanced_logger import info as _info
            _info("FH: %s %s limit not checked (class %r, level %r)"
                  % (sheet.get("name"), ability, sheet.get("class"), level), category="combat_events")
        except Exception:
            pass
        return ability, None
    return ability, rule["pool_per_level"] * level


def _feature_heal_unspent(event, resolution, encounter, proposal, feature, rows, clamp):
    """#669: a FEATURE_HEALS use that spends its typed resource (by value: the
    actor's own featureUse record whose name has the rule's key) but restores
    nothing is refused, so the correction spends nothing and asks. On the
    corrected pass the spend is dropped and journaled instead, and the
    resolution says so (featureHealUnspent): the pipeline pauses for a
    player's actor, an actor_agent's turn goes on with nothing spent."""
    if any(row.get("applied") for row in rows):
        return
    rule = next((r for key, r in FEATURE_HEALS.items() if feature_heal_key(key) == feature_heal_key(feature)), None)
    owner = (combatant_by_id(encounter, proposal.get("actorId")) or {}).get("name")
    spends = [
        record for record in event.get("resources") or []
        if record.get("kind") == "featureUse" and record.get("owner") == owner
        and rule is not None and feature_heal_key(record.get("name")) == feature_heal_key(rule.get("resource"))
        and isinstance(record.get("delta"), int) and record["delta"] < 0
    ]
    if not spends:
        return
    rows = rows or [{"actorId": proposal.get("actorId"), "ability": feature, "combatantId": None,
                     "hpBefore": None, "max": None, "allowed": 0, "declared": 0}]
    rows = [{k: v for k, v in row.items() if k != "applied"} for row in rows]
    if not clamp:
        resolution["violations"].append(
            "feature heal limit: %s restores nothing here, so %s is not spent"
            % (feature, spends[0].get("name")))
        resolution["featureHealLimits"] = rows
        return
    event["resources"] = [record for record in event["resources"] if record not in spends]
    event.setdefault("normalizations", []).append({
        "kind": "featureHeal", "ability": feature, "combatantId": None,
        "supplied": 0, "allowed": 0, "unspent": [record.get("name") for record in spends]})
    resolution["featureHealUnspent"] = rows


def _feature_heal_refused(event, resolution, encounter, proposal, refusal, targets, clamp):
    """F1: a heal paid with a POOL_HEALS pool that names none of the actor's
    options for it, or a Divine Spark that does not heal exactly one other
    creature, heals nothing. The violation names the options so the
    correction can pick one; on the corrected pass the spend is dropped and
    journaled and the resolution says so (featureHealUnspent), as #669 does
    for a heal that restores nothing."""
    declared = sum(max(0, declared_heal(entry)) for entry in targets)
    row = {"actorId": proposal.get("actorId"), "ability": refusal["ability"], "combatantId": None,
           "hpBefore": None, "max": None, "allowed": 0, "declared": declared,
           "pool": refusal["pool"], "options": list(refusal["options"])}
    if refusal.get("target"):
        row["target"] = refusal["target"]
        text = ("feature heal: %s heals exactly one other creature, never %s; heal one other target, "
                "or spend nothing" % (refusal["ability"], proposal.get("actorId")))
    elif refusal["options"]:
        text = ("feature heal: %s heals only as %s; name one in featureName, or spend nothing"
                % (refusal["pool"], " or ".join(refusal["options"])))
    else:
        text = "feature heal: %s has no heal option for this actor; spend nothing on a heal" % refusal["pool"]
    if not clamp:
        resolution["violations"].append(text)
        resolution.setdefault("featureHealLimits", []).append(row)
        return
    owner = (combatant_by_id(encounter, proposal.get("actorId")) or {}).get("name")
    spends = [
        record for record in event.get("resources") or []
        if record.get("kind") == "featureUse" and record.get("owner") == owner
        and feature_heal_key(record.get("name")) == feature_heal_key(refusal["pool"])
        and isinstance(record.get("delta"), int) and record["delta"] < 0
    ]
    event["resources"] = [record for record in event.get("resources") or [] if record not in spends]
    event.setdefault("normalizations", []).append({
        "kind": "featureHeal", "ability": refusal["ability"], "combatantId": None,
        "supplied": declared, "allowed": 0, "unspent": [record.get("name") for record in spends],
        "options": list(refusal["options"])})
    resolution["featureHealUnspent"] = [row]


def _feature_heal_allowed(hp_now, max_hp, pool_left):
    """The most a FEATURE_HEALS heal may restore to one target: nothing unless
    it is Bloodied (2 x hp <= max), then up to half its maximum, within the
    pool still left."""
    if 2 * hp_now > max_hp:
        return 0
    return max(0, min(max_hp // 2 - hp_now, pool_left))


def _combatant_max_hp(encounter, characters, creature):
    sheet = _effective_combatant_sheet(encounter, characters, creature)
    if isinstance(sheet.get("maxHitPoints"), (int, float)):
        return int(sheet["maxHitPoints"])
    return int((creature or {}).get("maxHitPoints", 0) or 0)


def _stated_conditions(characters, encounter, creature):
    """The conditions a combatant states, casefolded: a party sheet's
    condition_affected / condition and the encounter record's conditions.
    Typed values only; nothing is read from prose."""
    creature = creature or {}
    listed = [c for c in creature.get("conditions") or [] if isinstance(c, str)]
    sheet = (characters or {}).get(creature.get("name"))
    if creature.get("type") in ("player", "npc") and isinstance(sheet, dict):
        listed += [c for c in sheet.get("condition_affected") or [] if isinstance(c, str)]
        single = sheet.get("condition")
        if isinstance(single, str):
            listed.append(single)
    return {c.strip().casefold() for c in listed if c.strip().casefold() not in ("", "none")}


# SRD 5.2.1 conditions that set a known attack's roll mode (#528). The
# attacker's own condition imposes disadvantage; the target's grants advantage.
# Prone depends on the attack: melee has advantage, ranged disadvantage (the
# SRD's 5 feet is the melee entry). Situational modes (cover, unseen, a
# frightened attacker's source in sight) stay with the DM.
_ATTACKER_DISADVANTAGE = frozenset(("blinded", "poisoned", "prone", "restrained"))
_TARGET_ADVANTAGE = frozenset(("blinded", "paralyzed", "petrified", "restrained", "stunned", "unconscious"))


def _attack_mode(attacker_conditions, target_conditions, entry_type, target_dodging=False, declared=None):
    """("normal" | "advantage" | "disadvantage", sources). Any advantage
    with any disadvantage cancels to normal (SRD), the sources still listed."""
    advantage = []
    disadvantage = []
    for name in sorted(attacker_conditions or ()):
        if name in _ATTACKER_DISADVANTAGE:
            disadvantage.append(name)
    for name in sorted(target_conditions or ()):
        if name in _TARGET_ADVANTAGE:
            advantage.append("target " + name)
        elif name == "prone":
            (disadvantage if entry_type == "ranged" else advantage).append("target prone")
    if target_dodging:
        disadvantage.append("target dodging")
    # Item 3: the DM's typed situational ruling on a player's code-scored swing.
    if declared == "advantage":
        advantage.append("DM ruling")
    elif declared == "disadvantage":
        disadvantage.append("DM ruling")
    if advantage and disadvantage:
        return "normal", advantage + disadvantage
    if advantage:
        return "advantage", advantage
    if disadvantage:
        return "disadvantage", disadvantage
    return "normal", []


# SRD Dodge: the dodger loses the benefit while Incapacitated or at Speed 0
# (grappled and restrained set Speed 0). Typed state only.
_DODGE_ENDING_CONDITIONS = frozenset(INCAPACITATING_CONDITIONS + ("grappled", "restrained"))


def _target_dodging(creature, conditions):
    """True when the target's ``dodging`` record stands and it can benefit."""
    creature = creature or {}
    if not isinstance(creature.get("dodging"), dict) or creature.get("effectIncapacitated") is True:
        return False
    return not (set(conditions or ()) & _DODGE_ENDING_CONDITIONS)


# Typed damage traits (#527): the target sheet's lists, compared by exact
# casefolded equality with the attack's damage type. A free-text entry such
# as "poison from Giant Spider" is not a type and never matches.
_DAMAGE_TRAITS = (
    ("damageImmunities", "immunity"),
    ("damageResistances", "resistance"),
    ("damageVulnerabilities", "vulnerability"),
)


def _typed_damage(sheet, damage_type, raw):
    """(applied, traits): immunity -> 0; else resistance halves (rounded
    down) and then vulnerability doubles, each counted once (SRD order)."""
    kind = str(damage_type or "").strip().casefold()
    raw = int(raw or 0)
    if not kind or raw <= 0 or not isinstance(sheet, dict):
        return raw, []
    found = []
    for field, trait in _DAMAGE_TRAITS:
        for entry in sheet.get(field) or []:
            if isinstance(entry, str) and entry.strip().casefold() == kind and trait not in found:
                found.append(trait)
    if "immunity" in found:
        return 0, ["immunity"]
    applied = raw
    if "resistance" in found:
        applied = applied // 2
    if "vulnerability" in found:
        applied = applied * 2
    return applied, found


def _stated_condition_reference(characters, encounter, owner, combatant_id, *references):
    """The condition one of the references names among those the target states, or None.

    A party sheet states conditions in condition_affected / condition; a
    monster record in conditions. Typed values are compared casefolded
    against that list (an effectId of "restrained" written by the model is
    the stated condition, not an effect); nothing is read from prose.
    """
    if owner:
        sheet = (characters or {}).get(owner) or {}
        listed = [c for c in sheet.get("condition_affected") or [] if isinstance(c, str)]
        single = sheet.get("condition")
        if isinstance(single, str) and single.strip().casefold() not in ("", "none"):
            listed.append(single)
    else:
        creature = combatant_by_id(encounter, combatant_id) or {}
        listed = [c for c in creature.get("conditions") or [] if isinstance(c, str)]
    stated = {c.strip().casefold() for c in listed}
    for reference in references:
        if isinstance(reference, str) and reference.strip().casefold() in stated:
            return reference.strip().casefold()
    return None


def _end_stated_condition(encounter, characters, op):
    """A journaled remove op naming a stated condition: the fight's effects stating it go, then the name.

    A function of the op and the target's records, so a replay converges.
    """
    name = str(op.get("condition") or "").casefold()

    def _states(effect):
        return isinstance(effect, dict) and name in [
            str(c).strip().casefold() for c in effect.get("conditions") or [] if isinstance(c, str)
        ]

    if op.get("owner"):
        sheet = (characters or {}).get(op.get("owner"))
        if not isinstance(sheet, dict):
            raise ValueError("Effect owner is not durably addressable")
        remove_ops = [
            {"op": "remove", "effectId": effect.get("effectId"), "name": effect.get("name")}
            for effect in sheet.get("temporaryEffects") or []
            if _states(effect) and effect.get("sourceEncounterId")
        ]
        if remove_ops:
            sheet = apply_effect_ops(sheet, remove_ops)
        sheet["condition_affected"] = [
            c for c in sheet.get("condition_affected") or []
            if not (isinstance(c, str) and c.strip().casefold() == name)
        ]
        current = sheet.get("condition")
        if isinstance(current, str) and current.strip().casefold() == name:
            listed = sheet["condition_affected"]
            sheet["condition"] = listed[0] if listed else "none"
        # The engine's roll-mode labels named the ended state; its next
        # status request writes the current ones back.
        sheet.pop("rollModes", None)
        characters[op["owner"]] = sheet
        return
    creature = combatant_by_id(encounter, op.get("combatantId"))
    if creature is None or creature.get("type") in ("player", "npc"):
        raise ValueError("Effect combatant is not durably addressable")
    for effect in [e for e in creature.get("activeEffects") or [] if _states(e)]:
        _apply_encounter_effect_operation(
            creature, {"op": "remove", "effectId": effect.get("effectId"), "name": effect.get("name")}
        )
    creature["conditions"] = [
        c for c in creature.get("conditions") or []
        if not (isinstance(c, str) and c.strip().casefold() == name)
    ]


def _sheet_backed_target(characters, creature):
    """The character sheet behind a party combatant, or None for monsters."""
    if not isinstance(creature, dict) or creature.get("type") not in ("player", "npc"):
        return None
    sheet = (characters or {}).get(creature.get("name"))
    return sheet if isinstance(sheet, dict) else None


def _engine_hit_points(sheet, signed, event, focus=None, kind=None, treated=None):
    """CH: the rules engine applies one hit-point change to a party sheet.

    One damage instance is one engine request (the SRD concentration rule is
    one save per damage instance). The engine drains temporary hit points
    first, clamps at zero and at the effective maximum, holds Unconscious at
    zero and releases it on healing, and makes the concentration save when
    the sheet carries a record. Returns the engine's sheet copy, or None when
    the engine is unavailable or refuses, in which case the caller keeps the
    arithmetic it did before this change (fail forward, the fight never
    pauses for the engine). Every engine line is journaled on the event.

    K1: ``kind`` types a damage so the engine applies the sheet's traits to
    it first; the engine's record (requested, treated) is copied into the
    ``treated`` dict. On a failure ``treated`` holds only ``reason`` and
    nothing is logged here: the rider logs it and retries without the kind.
    """
    if type(signed) is not int or signed == 0 or type(sheet.get("hitPoints")) is not int:
        return None

    def failed(reason):
        if kind and treated is not None:
            treated["reason"] = reason
        else:
            _warn_engine(sheet, signed, reason)
        return None

    try:
        from core.nql import resources as nql_resources
        effective_max = effective_sheet(sheet).get("maxHitPoints")
        outcome = nql_resources.apply_deltas(
            sheet,
            {"hpDelta": signed},
            max_hp=effective_max if type(effective_max) is int else None,
            location="combat",
            kind=kind,
        )
    except Exception as exc:  # engine wrapper faults never stop a fight
        return failed(str(exc))
    if not outcome.ok or not isinstance(outcome.sheet, dict):
        return failed(outcome.reason)
    if type(outcome.sheet.get("hitPoints")) is not int:
        return failed("engine returned no hit points")
    if kind and treated is not None:
        treated.update(outcome.treated or {})
    for line in outcome.concentration_lines or []:
        event.setdefault("engineChecks", []).append(line)
        if focus is not None:
            focus.setdefault("engineChecks", []).append(line)
        try:
            from utils.enhanced_logger import info as _info
            _info("CH: engine check: %s" % line, category="combat_events")
        except Exception:
            pass
    if outcome.concentration_ended:
        event["concentrationEnded"] = outcome.concentration_ended
        if focus is not None:
            # CC: the target record carries the verdict; apply_resolution ends
            # the spell everywhere from it. The working sheet drops the record
            # now so a later swing or event of this window makes no second
            # save for a spell the engine already ended.
            focus["concentrationEnded"] = outcome.concentration_ended
            record = _concentration_record(outcome.sheet)
            if record:
                focus["concentrationGroup"] = record["group"]
            from core.managers.concentration_runtime import clear_record
            clear_record(outcome.sheet)
    try:
        from utils.enhanced_logger import info as _info
        _info(
            "CH: %s hp %s -> %s (temp %s -> %s) [engine %+d]"
            % (sheet.get("name"), sheet.get("hitPoints"), outcome.sheet.get("hitPoints"),
               sheet.get("temporaryHitPoints"), outcome.sheet.get("temporaryHitPoints"), signed),
            category="combat_events",
        )
    except Exception:
        pass
    return outcome.sheet


def _warn_rider(actor, entry, reason):
    try:
        from utils.enhanced_logger import warning as _warning
        _warning(
            "AS: %s %s damage treated without the engine (%s)"
            % ((actor or {}).get("name"), entry.get("name"), reason),
            category="combat_events",
        )
    except Exception:
        pass


def _warn_hands(actor, entry, error):
    try:
        from utils.enhanced_logger import warning as _warning
        _warning(
            "NUM-B: %s %s swing stands with no hands record (%s: %s)"
            % ((actor or {}).get("name"), entry.get("name"), type(error).__name__, error),
            category="combat_events",
        )
    except Exception:
        pass


def _warn_engine(sheet, signed, reason):
    try:
        from utils.enhanced_logger import warning as _warning
        _warning(
            "CH: %s hit points %+d applied without the engine (%s)"
            % (sheet.get("name"), signed, reason),
            category="combat_events",
        )
    except Exception:
        pass


def _engine_rider(working, trait_sheet, hp_after, kind, amount, event, focus):
    """K1: the engine applies the target's typed traits to a rider's damage.

    A party target's damage goes through CH with the kind (the engine treats,
    then drains temporary hit points, applies hp and makes the concentration
    save from the treated amount); a monster's through a throwaway world, its
    hp staying NEQ's arithmetic. Returns ((damage, traits), applied sheet or
    None, None), or (None, None, reason) when the engine did not answer.
    """
    from core.nql import attacks as nql_attacks
    if working is not None:
        treated = {}
        applied = _engine_hit_points(working, -amount, event, focus, kind=kind, treated=treated)
        record = treated.get("treated")
        if applied is None or not isinstance(record, dict) or type(treated.get("requested")) is not int:
            return None, None, treated.get("reason") or "engine returned no treated damage"
        return (treated["requested"], nql_attacks.journal_traits(record.get("treatments"))), applied, None
    max_hp = trait_sheet.get("maxHitPoints") if isinstance(trait_sheet, dict) else None
    try:
        result = nql_attacks.treat(
            amount=amount, damage_type=kind, target_sheet=trait_sheet, target_hp=hp_after,
            target_max_hp=max_hp if type(max_hp) is int else 0,
        )
    except Exception as exc:  # adapter faults never stop a fight
        return None, None, str(exc)
    if not result.ok or type(result.damage) is not int:
        return None, None, result.reason or "engine returned no treated damage"
    return (result.damage, list(result.traits)), None, None


def _concentration_record(sheet):
    """The caster's typed concentration record on a sheet, or None."""
    from core.nql import stats as nql_stats
    return nql_stats.concentration_of(sheet) if isinstance(sheet, dict) else None


def _end_concentration_group(encounter, characters, group, caster_combatant_id):
    """CC: end every effect of one concentration group on every sheet and creature.

    Matching is by the typed ``concentrationId`` first; a record with no group
    id (staged before groups existed) ends by its ``sourceCombatantId``. Sheet
    removals go through the lifecycle so the engine takes the numbers off the
    sheet. Returns the "<owner>: <name>" labels removed; removing an absent
    effect is a no-op, so a replay converges.
    """
    labels = []

    def _matches(effect):
        if not (isinstance(effect, dict) and effect.get("concentration")):
            return False
        if group and effect.get("concentrationId"):
            return effect.get("concentrationId") == group
        return bool(caster_combatant_id) and effect.get("sourceCombatantId") == caster_combatant_id

    for owner, sheet in list((characters or {}).items()):
        if not isinstance(sheet, dict):
            continue
        remove_ops = [
            {"op": "remove", "effectId": effect.get("effectId"), "name": effect.get("name")}
            for effect in sheet.get("temporaryEffects", []) or []
            if _matches(effect)
        ]
        if remove_ops:
            characters[owner] = apply_effect_ops(sheet, remove_ops)
            labels.extend("%s: %s" % (owner, op["name"]) for op in remove_ops)
    for creature in (encounter or {}).get("creatures", []) or []:
        effects = creature.get("activeEffects") if isinstance(creature, dict) else None
        if not isinstance(effects, list):
            continue
        remove_ops = [
            {"op": "remove", "effectId": effect.get("effectId"), "name": effect.get("name")}
            for effect in effects
            if _matches(effect)
        ]
        for operation in remove_ops:
            _apply_encounter_effect_operation(creature, operation)
            labels.append("%s: %s" % (creature.get("name"), operation["name"]))
    return labels


def _apply_concentration_verdicts(new_encounter, new_characters, event):
    """CC: act on the engine's concentration verdict journaled on each target record.

    Live apply writes ``concentrationGroup`` and ``concentrationEndedEffects``
    into the record before the event is journaled; a replay reads them back
    and re-applies the same removals, never consulting the engine.
    """
    from core.managers.concentration_runtime import clear_record
    for record in (event.get("outcome") or {}).get("targets", []) or []:
        if not isinstance(record, dict) or not record.get("concentrationEnded"):
            continue
        creature = combatant_by_id(new_encounter, record.get("combatantId"))
        sheet = _sheet_backed_target(new_characters, creature)
        if sheet is None:
            continue
        current = _concentration_record(sheet)
        group = record.get("concentrationGroup") or (current or {}).get("group")
        if group and not record.get("concentrationGroup"):
            record["concentrationGroup"] = group
        labels = _end_concentration_group(
            new_encounter, new_characters, group, creature.get("combatantId")
        )
        if clear_record(new_characters[creature["name"]]):
            labels.append("%s: concentration record" % creature["name"])
        if "concentrationEndedEffects" not in record:
            record["concentrationEndedEffects"] = labels
        try:
            from utils.enhanced_logger import info as _info
            _info(
                "CC: %s concentration ended (%s); removed: %s"
                % (creature.get("name"), record.get("concentrationEnded"), ", ".join(labels) or "nothing"),
                category="combat_events",
            )
        except Exception:
            pass


def _record_fight_cast(new_encounter, new_characters, event, op):
    """CC: a concentration effect added by a party caster writes the caster's record.

    The group is the event id the resolver stamped on the effect, so the
    journaled op carries everything a replay needs. Several ops of one event
    (one cast, several targets) extend ``targets``; a different group replaces
    the record (the same-caster drop already removed the old effects).
    """
    effect = op.get("effect") if isinstance(op, dict) else None
    if not (isinstance(effect, dict) and effect.get("concentration") and effect.get("concentrationId")):
        return
    actor = combatant_by_id(new_encounter, event.get("actorId"))
    sheet = _sheet_backed_target(new_characters, actor)
    if sheet is None:
        return
    if op.get("owner"):
        target = op.get("owner")
    else:
        target_creature = combatant_by_id(new_encounter, op.get("combatantId"))
        target = (target_creature or {}).get("name") or op.get("combatantId")
    from core.nql import stats as nql_stats
    group = effect.get("concentrationId")
    current = nql_stats.concentration_of(sheet)
    targets = set((current or {}).get("targets") or []) if current and current.get("group") == group else set()
    targets.add(str(target))
    sheet[nql_stats.CONCENTRATION_FIELD] = {
        "name": effect.get("name"),
        "group": group,
        "targets": sorted(targets),
        "expiration": None,
    }
    try:
        from utils.enhanced_logger import info as _info
        _info(
            "CC: %s concentrates on %s (group %s, targets %s)"
            % (actor.get("name"), effect.get("name"), group, ", ".join(sorted(targets))),
            category="combat_events",
        )
    except Exception:
        pass


def _temp_hp(sheet):
    value = sheet.get("temporaryHitPoints") if isinstance(sheet, dict) else None
    return value if type(value) is int else None


def _sheet_delta(working, hp_after, status_after, creature, had_temp):
    """The absolute sheet write for one party target (replay reads the same)."""
    delta = {"hitPoints": hp_after}
    temp_after = _temp_hp(working)
    if temp_after is not None and (had_temp is not None or temp_after):
        delta["temporaryHitPoints"] = temp_after
    if status_after != normalize_status(creature.get("status")):
        delta["status"] = status_after
    return delta


GREAT_WEAPON_RULE = "Great Weapon Fighting"


def great_weapon_treated(faces):
    """SRD 5.2.1 Great Weapon Fighting: a 1 or 2 on a damage die counts as a 3."""
    return [max(int(face), 3) for face in faces]


def great_weapon_applies(sheet, entry):
    """(applies, note) for one swing (#879): the sheet records exactly
    "Fighting Style: Great Weapon Fighting", the row is melee, and the engine
    option for the row occupies two hands. note is "" when it applies or the
    style is absent, otherwise why it does not. Typed fields only."""
    from core.nql import genesis, hands
    if not genesis.has_great_weapon_style(sheet):
        return False, ""
    if not isinstance(entry, dict) or entry.get("type") != "melee":
        return False, "not a melee row"
    try:
        held = hands.two_handed(sheet, entry.get("name"))
    except Exception as exc:  # fail forward: the swing is scored without the style
        held = None
        _warn_great_weapon(entry, exc)
    if held is None:
        return False, "no engine row"
    return (True, "") if held else (False, "not held in two hands")


def _warn_great_weapon(entry, exc):
    try:
        from utils.enhanced_logger import warning as _warning
        _warning("GWF: %s scored without Great Weapon Fighting (%s: %s)"
                 % ((entry or {}).get("name"), type(exc).__name__, exc), category="combat_events")
    except Exception:
        pass


def _engine_swing(rolls, entry, sheet, to_hit, mode, faces, target_ac, target, target_hp, trait_sheet,
                  log_label="", treat=False):
    """Option 3: one swing scored by the rules engine (NQL X6 + X8), or None.

    The engine keeps the face, decides hit, miss and critical, adds the
    damage bonus once and applies the target's typed damage traits. Both
    damage totals are summed from the faces the roll source will hand out
    next (peeked, not taken), so the caller takes exactly what today's code
    takes. None (engine missing or refusing, dice it cannot take) keeps
    today's arithmetic for the whole swing.
    """
    from core.nql import attacks

    try:
        count, sides, modifier = parse_dice(entry.get("damageDice", "1d4"), flat_ok=True)
    except ValueError:
        return None
    peek = getattr(rolls, "peek", None)
    upcoming = peek("d%d" % sides, 2 * count) if callable(peek) else []
    if treat:
        upcoming = great_weapon_treated(upcoming)
    normal = sum(upcoming[:count]) if len(upcoming) >= count else None
    critical = sum(upcoming) if len(upcoming) >= 2 * count else None
    # With no damage faces ahead (the player's miss) the swing is only scored.
    scored = attacks.score(
        to_hit=to_hit, count=count, sides=sides,
        bonus=modifier + int(entry.get("damageBonus", 0) or 0) + modifier_total(sheet, "damageRolls"),
        damage_type=entry.get("damageType"), mode=mode, faces=list(faces),
        target_ac=target_ac, target_hp=target_hp,
        target_max_hp=int((target or {}).get("maxHitPoints", 0) or 0),
        target_sheet=trait_sheet, damage=normal, critical_damage=critical,
    )
    if scored.ok:
        return scored
    try:
        from utils.enhanced_logger import warning as _warning
        _warning(
            "AS: %s scored without the engine (%s)" % (log_label or entry.get("name"), scored.reason),
            category="combat_events",
        )
    except Exception:
        pass
    return None


def _added_dice(sheet, stats, rolls, purpose):
    """#889: the added dice of the sheet's live effects on ``stats`` (Bless:
    1d4 to attack rolls and saving throws), each face taken from the generic
    pool of ``rolls`` and journaled. Empty when no effect adds a die, so no
    face is taken and the dice stream is today's."""
    journal = []
    for stat in stats:
        for count, sides, effect_id in modifier_dice(sheet, stat):
            for _ in range(count):
                journal.append({"die": "1d%d" % sides, "value": int(rolls.take("d%d" % sides)),
                                "purpose": purpose, "effect": effect_id})
    return journal


def _replay_added_dice(rolls, added):
    """#889: the faces an open roll phase took from a fresh copy of the
    prerolls are taken again from the committing source, so its generic
    pools advance by the same takes (the stored faces are the ones used)."""
    if rolls is None:
        return
    for roll in added or []:
        rolls.take("d%s" % str(roll.get("die", "")).split("d")[-1])


def _save_added_dice(encounter, characters, creature, save_type, rolls):
    """#889: the added dice (Bless) on a saving throw code scores."""
    ability = save_ability(save_type) or ""
    return _added_dice(_raw_combatant_sheet(encounter, characters, creature),
                       ("savingThrows", "savingThrow.%s" % ability), rolls, "saveBonus")


def _opened_faces(encounter, characters, actor, rolls):
    """#889: the faces a swing's roll phase opens with: the actor's added
    attack dice, taken now from a fresh copy of the prerolls (nothing is
    consumed until the window commits), or {}."""
    if rolls is None:
        return {}
    added = _added_dice(_raw_combatant_sheet(encounter, characters, actor), ("attackRolls",), rolls,
                        "attackBonus")
    return {"bonusDice": added} if added else {}


def resolve_intent(encounter, characters, intent, rolls, event_id, mode_override=None, great_weapon=None, bonus_dice=None):
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
            "status": "defeated",
            # The typed manner of leaving, for the location record (P4-c):
            # a closed file tells fled from yielded without reading prose.
            "resolution": "fled" if intent.get("action") == "flee" else "yielded",
        }
        # Leaving the fight is an encounter fact only (#466): the sheet keeps
        # its own status so the character is not treated as down afterwards.
        return resolution

    if intent.get("action") != "attack":
        return resolution

    # K1: validate_intent found this row by abilityRow before any resolve.
    selected_entry = attack_row(sheet, intent.get("abilityRow"), intent.get("actorId")) or {}
    attack_entries = attack_sequence(
        sheet,
        selected=selected_entry,
        num_attacks=actor.get("numAttacks"),
        sequence=actor.get("multiattackSequence"),
    )
    target = combatant_by_id(encounter, intent.get("targetId"))
    target_ac = _combatant_ac(encounter, characters, target)

    hp_before = int((target or {}).get("currentHitPoints", 0) or 0)
    hp_after = hp_before
    swings = []
    total_damage = 0
    ranged_swings = 0
    ranged_entry = None
    # CH: a party target's hit points are applied by the rules engine, one
    # request per hitting swing, on a working copy that starts from the
    # encounter's number (the commit invariant keeps sheet and creature equal).
    target_sheet = _sheet_backed_target(characters, target)
    working = None
    temp_before = None
    engine_used = None
    focus = {}
    if target_sheet is not None:
        working = deepcopy(target_sheet)
        working["hitPoints"] = hp_before
        temp_before = _temp_hp(working)
    # #527/#528: the target's typed damage traits and the stated conditions
    # on both sides are read once; every swing of the sequence uses them.
    trait_sheet = _raw_combatant_sheet(encounter, characters, target) if target is not None else {}
    attacker_conditions = _stated_conditions(characters, encounter, actor)
    target_conditions = _stated_conditions(characters, encounter, target)
    target_dodging = _target_dodging(target, target_conditions)
    for swing_number, entry in enumerate(attack_entries, start=1):
        if target is None or hp_after <= 0:
            break
        if _spends_ammunition(entry) and ranged_swings >= _ammunition_left(sheet, ranged_entry or entry):
            continue
        attack_bonus = int(entry.get("attackBonus", 0) or 0) + modifier_total(
            sheet, "attackRolls"
        )
        # #889: an effect's added die (Bless) joins this to-hit: from the
        # generic pool, or the faces the player's open roll phase holds.
        added = (list(bonus_dice) if bonus_dice is not None
                 else _added_dice(sheet, ("attackRolls",), rolls, "attackBonus"))
        attack_bonus += sum(int(roll["value"]) for roll in added)
        # #528: advantage or disadvantage takes two faces from the same
        # source (both journaled), and keeps the higher or the lower one.
        if mode_override is not None:
            # Item 3: a player's code-scored swing keeps the mode fixed when its
            # roll was asked for, so the faces typed always match it.
            attack_mode, mode_sources = mode_override
        else:
            attack_mode, mode_sources = _attack_mode(
                attacker_conditions, target_conditions, entry.get("type"), target_dodging
            )
        attack_faces = [
            _take_roll(
                rolls,
                "d20",
                "attack",
                actor_id=intent.get("actorId"),
                target_id=intent.get("targetId"),
            )
            for _ in range(2 if attack_mode in ("advantage", "disadvantage") else 1)
        ]
        attack_die = (
            max(attack_faces) if attack_mode == "advantage"
            else min(attack_faces) if attack_mode == "disadvantage"
            else attack_faces[0]
        )
        # #879: Great Weapon Fighting is read once per swing; a player's
        # code-scored swing passes the answer stored when its damage was asked.
        if great_weapon is not None:
            gwf, gwf_note = bool(great_weapon), ""
        else:
            gwf, gwf_note = great_weapon_applies(sheet, entry)
        if gwf or gwf_note:
            event["outcome"]["greatWeaponFighting"] = True if gwf else gwf_note
        # Option 3: the rules engine scores the swing and its damage; today's
        # arithmetic stays the fallback (engine false on the swing).
        scored = _engine_swing(
            rolls, entry, sheet, attack_bonus, attack_mode, attack_faces, target_ac,
            target, hp_after, trait_sheet,
            log_label="%s %s" % (actor.get("name"), entry.get("name")), treat=gwf,
        )
        if scored is not None:
            total, critical, hit = int(scored.total), bool(scored.critical), bool(scored.hit)
        else:
            total = attack_die + attack_bonus
            critical = attack_die == 20
            hit = critical or (attack_die != 1 and total >= target_ac)
        if mode_sources:
            try:
                from utils.enhanced_logger import info as _info
                _info(
                    "CR: %s %s with %s (%s): faces %s, kept %d"
                    % (actor.get("name"), entry.get("name"), attack_mode,
                       ", ".join(mode_sources), attack_faces, attack_die),
                    category="combat_events",
                )
            except Exception:
                pass
        for face in attack_faces:
            roll_record = {"die": "d20", "value": face, "purpose": "attack"}
            if attack_mode != "normal":
                roll_record["mode"] = attack_mode
            event["rolls"].append(roll_record)
        event["rolls"].extend(dict(roll) for roll in added)
        damage = 0
        raw_damage = 0
        damage_traits = []
        if hit:
            count, sides, modifier = parse_dice(entry.get("damageDice", "1d4"), flat_ok=True)
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
            treated = great_weapon_treated(damage_rolls) if gwf else damage_rolls
            for value, used in zip(damage_rolls, treated):
                roll_record = {"die": "d%d" % sides, "value": value, "purpose": "damage"}
                if gwf:
                    roll_record.update(treated=used, rule=GREAT_WEAPON_RULE)
                event["rolls"].append(roll_record)
            if (scored is not None and scored.raw_damage is not None
                    and scored.damage_rolled == sum(treated)):
                # Option 3: the engine's damage, its traits applied.
                raw_damage = scored.raw_damage
                damage, damage_traits = int(scored.damage or 0), list(scored.traits)
            else:
                if scored is not None:
                    try:
                        from utils.enhanced_logger import warning as _warning
                        _warning(
                            "AS: %s %s scored without the engine (damage faces taken %d, engine used %s)"
                            % (actor.get("name"), entry.get("name"), sum(treated), scored.damage_rolled),
                            category="combat_events",
                        )
                    except Exception:
                        pass
                    scored = None
                raw_damage = max(
                    0,
                    sum(treated)
                    + modifier
                    + int(entry.get("damageBonus", 0) or 0)
                    + modifier_total(sheet, "damageRolls"),
                )
                # #527: the target's trait for this damage type applies before
                # the number reaches the engine or the arithmetic; the journal
                # keeps both numbers so a replay applies the same result.
                damage, damage_traits = _typed_damage(trait_sheet, entry.get("damageType"), raw_damage)
            if damage_traits:
                try:
                    from utils.enhanced_logger import info as _info
                    _info(
                        "CR: %s takes %d %s from %s's %s (%s: %d -> %d)"
                        % (target.get("name"), damage, entry.get("damageType"), actor.get("name"),
                           entry.get("name"), ", ".join(damage_traits), raw_damage, damage),
                        category="combat_events",
                    )
                except Exception:
                    pass
            applied = _engine_hit_points(working, -damage, event, focus) if working is not None and damage else None
            if applied is not None:
                working = applied
                hp_after = int(working["hitPoints"])
                engine_used = True
            else:
                hp_after = max(0, hp_after - damage)
                if working is not None:
                    working["hitPoints"] = hp_after
                    if damage:
                        engine_used = False
            total_damage += damage
        rider_result = None
        rider_spec = _stated_save_spec(entry, "rider") if hit else None
        if rider_spec is not None:
            # MS-b: the hit forces the stat block's rider save on the same
            # event (a venomous bite): party target through the engine,
            # monster by arithmetic; rider dice from the persisted prerolls,
            # halved or negated by the verdict; conditions staged from the
            # entry as a failed-save effect. Replay reads the journal.
            rider_dice, rider_conditions, rider_rounds = _stated_on_fail(entry, "rider")
            saved = _target_save(
                encounter, characters, working, target, rider_spec, rolls,
                intent.get("actorId"), event, focus,
            )
            rider_damage = 0
            rider_typed = {}
            rider_engine = False
            if rider_dice is not None:
                r_count, r_sides, r_flat = rider_dice
                r_rolls = [
                    _take_roll(
                        rolls, "d%d" % r_sides, "damage",
                        actor_id=intent.get("actorId"), target_id=intent.get("targetId"),
                    )
                    for _ in range(r_count)
                ]
                for value in r_rolls:
                    event["rolls"].append({
                        "die": "d%d" % r_sides, "value": value, "purpose": "damage",
                        "combatantId": target["combatantId"], "rider": entry.get("name"),
                    })
                rider_damage = max(0, sum(r_rolls) + r_flat)
                if saved:
                    rider_damage = rider_damage // 2 if rider_spec.get("halfOnSave") else 0
                # #527: the rider's own damage type (a venomous bite's poison)
                # meets the target's traits like the swing's damage does.
                # K1: the engine applies them; today's arithmetic is the
                # fallback when it does not answer.
                rider_raw = rider_damage
                rider_type = ((entry.get("rider") or {}).get("onFail") or {}).get("damageType")
                rider_kind = str(rider_type or "").strip().casefold()
                rider_treated, rider_sheet = None, None
                if rider_damage > 0 and rider_kind:
                    rider_treated, rider_sheet, reason = _engine_rider(
                        working, trait_sheet, hp_after, rider_kind, rider_damage, event, focus)
                    if rider_treated is None:
                        _warn_rider(actor, entry, reason)
                if rider_treated is not None:
                    rider_damage, rider_traits = rider_treated
                    rider_engine = True
                else:
                    rider_damage, rider_traits = _typed_damage(trait_sheet, rider_type, rider_damage)
                if rider_traits:
                    rider_typed = {"rawDamage": rider_raw, "damageTraits": rider_traits}
                else:
                    rider_typed = {}
                if rider_sheet is not None:
                    # CH already applied the treated damage (0 changes nothing).
                    working = rider_sheet
                    hp_after = int(working["hitPoints"])
                    engine_used = True
                    total_damage += rider_damage
                elif rider_damage:
                    applied = _engine_hit_points(working, -rider_damage, event, focus) if working is not None else None
                    if applied is not None:
                        working = applied
                        hp_after = int(working["hitPoints"])
                        engine_used = True
                    else:
                        hp_after = max(0, hp_after - rider_damage)
                        if working is not None:
                            working["hitPoints"] = hp_after
                            engine_used = False
                    total_damage += rider_damage
            rider_applied = []
            if not saved and rider_conditions:
                op, problems = _stat_block_condition_op(
                    encounter, event_id, actor, target, entry, rider_conditions, rider_rounds,
                    len(resolution.setdefault("effectOps", [])),
                )
                if op is not None:
                    resolution["effectOps"].append(op)
                    rider_applied = list(rider_conditions)
                else:
                    resolution["violations"].append(
                        "rider effect contract rejected: %s" % "; ".join(problems))
            rider_result = {
                "ability": entry.get("name"), "save": rider_spec["type"], "dc": rider_spec["dc"],
                "saved": saved, "damage": rider_damage, "conditions": rider_applied,
                # K1: the rider's typed damage was treated by the rules engine.
                "engine": rider_engine,
            }
            rider_result.update(rider_typed)
        swing = {
            "number": swing_number,
            "ability": entry.get("name"),
            "attackRoll": attack_die,
            "totalAttack": total,
            "targetAC": target_ac,
            "hit": hit,
            "critical": critical,
            "damage": damage,
            # Option 3: scored by the rules engine, or by today's arithmetic.
            "engine": scored is not None,
            # #851: the swung row's type, read back as the actor's last weapon.
            "rowType": entry.get("type"),
            "thrown": entry.get("thrown") is True,
        }
        if attack_mode != "normal" or mode_sources:
            # #528: the mode, the faces it chose from and the conditions
            # behind it (cancelled ones included) stay on the journal.
            swing["attackMode"] = attack_mode
            swing["attackFaces"] = list(attack_faces)
            swing["attackModeSources"] = list(mode_sources)
        if hit and damage_traits:
            # #527: the raw number and the trait that changed it.
            swing["damageType"] = entry.get("damageType")
            swing["rawDamage"] = raw_damage
            swing["damageTraits"] = list(damage_traits)
        if rider_result is not None:
            swing["rider"] = rider_result
        swings.append(swing)
        if _spends_ammunition(entry):
            ranged_swings += 1
            ranged_entry = ranged_entry or entry

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
            # D-242-1: party members (player and companions) fall unconscious;
            # only hostiles die at 0. Party-ness is the roster value.
            status_after = (
                PLAYER_UNCONSCIOUS
                if is_party_member(target)
                else NONPLAYER_DEAD
            )
        record = {
            "combatantId": target["combatantId"], "hpBefore": hp_before,
            "hpAfter": hp_after, "statusAfter": status_after,
        }
        riders = [swing["rider"] for swing in swings if swing.get("rider")]
        if riders:
            record["riders"] = riders
        if working is not None:
            if temp_before is not None:
                record["tempHpBefore"] = temp_before
            if _temp_hp(working) is not None and (temp_before is not None or _temp_hp(working)):
                record["tempHpAfter"] = _temp_hp(working)
            if engine_used is not None:
                record["engine"] = engine_used
            record.update(focus)
        event["outcome"]["targets"].append(record)
        resolution["creatureDeltas"][target["combatantId"]] = {
            "currentHitPoints": hp_after, "status": status_after,
        }
        # Only players/NPCs have character files; monsters can share a
        # name (Twig Blight x2), so syncing their sheets by name would
        # clobber the wrong record.
        if working is not None:
            resolution["charDeltas"][target["name"]] = _sheet_delta(
                working, hp_after, status_after, target, temp_before)

    if swings and selected_entry:
        _spend_recharge(resolution, event, actor, selected_entry)
    if resolution.get("effectOps"):
        event["effects"] = deepcopy(resolution["effectOps"])
    item = _ammunition_row(sheet, ranged_entry) if ranged_swings else None
    if item is not None:
        before = int(item.get("quantity", 0) or 0)
        spent = min(ranged_swings, before)
        record = {
            "owner": actor.get("name"), "kind": "ammunition",
            "name": item.get("name"), "delta": -spent,
            "before": before, "after": before - spent,
        }
        # AM: a party archer's shots go through the engine (stock and
        # recoverable count); monsters have no sheet row and never
        # reach here. Engine unavailable: today's arithmetic, engine false.
        if actor.get("type") in ("player", "npc"):
            answer = _engine_ammunition(sheet, item.get("name"), -spent, record)
            if answer is not True:
                record["engine"] = False
        event["resources"].append(record)
    # NUM-B (owner BQ1-BQ3): the swing stands. The engine's option for the swung
    # row is recorded on the event, and a carried weapon that fits is drawn
    # (applied by apply_resolution from the record, so a replay matches).
    if (swings and selected_entry and actor.get("type") in ("player", "npc")
            and isinstance((characters or {}).get(actor.get("name")), dict)):
        from core.nql import hands
        try:
            hands_record = hands.after_swing(sheet, selected_entry.get("name"))
        except Exception as exc:
            # Fail forward: the swing is already resolved; it stands with no record.
            hands_record = None
            _warn_hands(actor, selected_entry, exc)
        if hands_record is not None:
            hands_record["owner"] = actor.get("name")
            event["hands"] = hands_record
    _stage_last_weapon_rows(encounter, characters, resolution)
    return resolution


# Item 3: the player's plain melee weapon swing, or (D-HC-1) shot with
# ammunition, is scored by code from the
# player's typed faces, asked for by code ([ROLL]); every other player action
# stays with the model's adjudicated ruling. Typed fields only.
PLAYER_DECLARED_MODES = ("advantage", "disadvantage")


def _declares_one_shot(resources):
    """D-HC-1: an ammunition shot's resources as the model writes them today:
    none, or exactly one record of kind 'ammunition' and delta -1. Only those
    typed fields are read; the record's name and owner never are (the row
    spent is the typed one, ``_ammunition_row``)."""
    if not resources:
        return True
    return (isinstance(resources, list) and len(resources) == 1 and isinstance(resources[0], dict)
            and resources[0].get("kind") == "ammunition" and resources[0].get("delta") == -1)


def _plain_weapon_attack(encounter, characters, intent):
    """(entry, sheet, actor) when the intent is a plain single weapon attack at
    a hostile, targetable creature: a melee swing with no resources, or
    (D-HC-1) a shot from a ranged row that spends ammunition (a thrown row
    does not, #801, and stays adjudicated); None otherwise."""
    if not isinstance(intent, dict) or intent.get("action") != "attack":
        return None
    if intent.get("targets") or intent.get("effects"):
        return None
    attacks = intent.get("attacks")
    if attacks is not None and not (type(attacks) is int and attacks == 1):
        return None
    actor = combatant_by_id(encounter, intent.get("actorId"))
    target = combatant_by_id(encounter, intent.get("targetId"))
    if actor is None or target is None:
        return None
    if (not is_hostile(target) or not is_combatant_targetable(target)
            or target.get("faction") == actor.get("faction")):
        return None
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    # K1: no abilityRow, or one naming no listed row, means no code takeover;
    # the model rules the attack (and P1's outcome check holds).
    entry = attack_row(sheet, intent.get("abilityRow"), actor.get("combatantId"))
    if not isinstance(entry, dict) or not is_executable_attack(entry):
        return None
    if entry.get("type") == "melee":
        if intent.get("resources"):
            return None
    elif not _spends_ammunition(entry) or not _declares_one_shot(intent.get("resources")):
        return None
    # #1350: a flat row (NUM-H3c) is taken over too; its window asks only the
    # d20 and the engine scores the flat damage.
    sequence = attack_sequence(
        sheet,
        selected=entry,
        num_attacks=actor.get("numAttacks"),
        sequence=actor.get("multiattackSequence"),
    )
    if len(sequence) != 1 or sequence[0] is not entry:
        return None
    return entry, sheet, actor


def player_weapon_attack_entry(encounter, characters, intent):
    """The sheet entry when the intent is a plain single melee weapon swing, or
    (D-HC-1) a shot with ammunition left for it, at a hostile, targetable
    creature; None otherwise."""
    plain = _plain_weapon_attack(encounter, characters, intent)
    if plain is None:
        return None
    entry, sheet, _actor = plain
    if _spends_ammunition(entry) and _ammunition_row(sheet, entry) is None:
        return None
    return entry


def player_ammunition_refusal(encounter, characters, intent):
    """D-HC-1: the typed #968 refusal for a plain shot with no ammunition row
    left for it (every stocked row is typed to another id), or None. The name
    is the display name of the row's typed ammunitionType (data; never
    compared), left out when the catalog has no entry for it."""
    plain = _plain_weapon_attack(encounter, characters, intent)
    if plain is None:
        return None
    entry, sheet, actor = plain
    if not _spends_ammunition(entry) or _ammunition_row(sheet, entry) is not None:
        return None
    refusal = {"owner": actor.get("name"), "kind": "ammunition", "before": 0, "max": None,
               "need": 1, "actor": actor.get("name"), "ability": entry.get("name")}
    wanted = entry.get("ammunitionType")
    if isinstance(wanted, str) and wanted:
        refusal["ammunitionType"] = wanted
        from core.nql import item_catalog
        catalog_entry = item_catalog.entry(wanted)
        if isinstance(catalog_entry, dict) and catalog_entry.get("name"):
            refusal["name"] = catalog_entry["name"]
    return refusal


def open_player_weapon_attack(encounter, characters, intent, entry, rolls=None):
    """The roll-phase record for pendingTurn.weaponAttack: the mode is fixed
    here (conditions, Dodge and the DM's typed ruling) so the number of d20
    faces asked for never changes mid-turn."""
    actor = combatant_by_id(encounter, intent.get("actorId"))
    target = combatant_by_id(encounter, intent.get("targetId"))
    attacker_conditions = _stated_conditions(characters, encounter, actor)
    target_conditions = _stated_conditions(characters, encounter, target)
    declared = intent.get("attackMode")
    mode, sources = _attack_mode(
        attacker_conditions, target_conditions, entry.get("type"),
        _target_dodging(target, target_conditions),
        declared if declared in PLAYER_DECLARED_MODES else None,
    )
    record = {
        "actorId": actor.get("combatantId"),
        "ability": entry.get("name"),
        "targetId": target.get("combatantId"),
        "targetName": target.get("name"),
        "mode": mode,
        "modeSources": list(sources),
        "phase": "attack",
        "faces": _opened_faces(encounter, characters, actor, rolls),
        "sources": {},
    }
    if isinstance(intent.get("abilityRow"), dict):
        # K1: the phase keeps the row's position and its value at open.
        record["abilityRow"] = deepcopy(intent["abilityRow"])
        record["rowAtOpen"] = deepcopy(entry)
    return record


def weapon_attack_sheet_entry(encounter, characters, record, check_open=False):
    """The sheet entry the open roll phase was opened for, or None. A spell
    attack's phase (#672) carries its own entry, fixed when it opened. With
    ``check_open`` the row must still equal the row the phase opened on."""
    actor = combatant_by_id(encounter, record.get("actorId"))
    if actor is None:
        return None
    spell = record.get("spell")
    if isinstance(spell, dict):
        return {key: spell.get(key) for key in ("name", "type", "damageDice", "damageType", "attackBonus")}
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    if "abilityRow" in record:
        entry = attack_row(sheet, record.get("abilityRow"), actor.get("combatantId"))
        if check_open and isinstance(entry, dict) and "rowAtOpen" in record and entry != record["rowAtOpen"]:
            # K1 (P-3): the row at the phase's position changed since the phase
            # opened, so it is closed and the turn goes back to T096.
            return None
    else:
        # A phase opened before K1 named its row by the row's own name
        # (code-written at open, not the model's text).
        entry = _find_action(sheet, record.get("ability"))
    return entry if isinstance(entry, dict) else None


def _row_ref_of(encounter, characters, record, entry):
    """The position of ``entry`` (the very row) in the actor's attack list, or None."""
    actor = combatant_by_id(encounter, record.get("actorId"))
    if actor is None:
        return None
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    family = attack_family(sheet)
    for index, row in enumerate(sheet.get(family) or []):
        if row is entry:
            return {"combatantId": actor.get("combatantId"), "family": family, "index": index}
    return None


def player_weapon_attack_dice(record, entry):
    """(count, sides) the open phase asks for: 1d20 (2d20 with a mode), or the
    weapon's damage dice, doubled on a critical hit."""
    if record.get("phase") == "attack":
        return (2 if record.get("mode") in PLAYER_DECLARED_MODES else 1), 20
    count, sides, _modifier = parse_dice(entry.get("damageDice"))
    return count * (2 if record.get("critical") else 1), sides


def player_weapon_attack_score(encounter, characters, record, entry):
    """(hit, critical, kept, total, ac) for the attack faces on the record;
    the same arithmetic resolve_intent applies to the swing."""
    actor = combatant_by_id(encounter, record.get("actorId"))
    target = combatant_by_id(encounter, record.get("targetId"))
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    faces = list((record.get("faces") or {}).get("attack") or [])
    mode = record.get("mode")
    to_hit = int(entry.get("attackBonus", 0) or 0) + modifier_total(sheet, "attackRolls")
    # #889: the added dice the phase took when it opened (none on a record
    # opened before them).
    to_hit += sum(int(roll["value"]) for roll in (record.get("faces") or {}).get("bonusDice") or [])
    ac = _combatant_ac(encounter, characters, target)
    # Option 3: the player's first step is a score-only engine call (no
    # damage total yet); today's arithmetic stays the fallback.
    scored = _engine_score_only(entry, to_hit, mode, faces, ac, target, sheet)
    if scored is not None:
        return bool(scored.hit), bool(scored.critical), int(scored.kept), int(scored.total), ac
    kept = max(faces) if mode == "advantage" else min(faces) if mode == "disadvantage" else faces[0]
    total = kept + to_hit
    critical = kept == 20
    return critical or (kept != 1 and total >= ac), critical, kept, total, ac


def _engine_score_only(entry, to_hit, mode, faces, ac, target, sheet):
    """Option 3: hit, miss and critical for the player's typed faces, with no
    damage applied; None keeps today's arithmetic."""
    from core.nql import attacks

    try:
        count, sides, modifier = parse_dice(entry.get("damageDice", "1d4"), flat_ok=True)
    except ValueError:
        return None
    scored = attacks.score(
        to_hit=to_hit, count=count, sides=sides,
        bonus=modifier + int(entry.get("damageBonus", 0) or 0) + modifier_total(sheet, "damageRolls"),
        damage_type=entry.get("damageType"), mode=mode, faces=faces,
        target_ac=ac, target_hp=int((target or {}).get("currentHitPoints", 0) or 0),
        target_max_hp=int((target or {}).get("maxHitPoints", 0) or 0),
    )
    if scored.ok:
        return scored
    try:
        from utils.enhanced_logger import warning as _warning
        _warning("AS: %s scored without the engine (%s)" % (entry.get("name"), scored.reason),
                 category="combat_events")
    except Exception:
        pass
    return None


def _split_total(total, count, sides):
    """count die values within 1..sides summing to total (the player typed the
    total; the arithmetic only needs the sum)."""
    values = [1] * count
    rest = total - count
    for index in range(count):
        step = min(sides - 1, rest)
        values[index] += step
        rest -= step
    return values


def _damage_faces(faces, count, sides, total):
    """The typed damage faces kept on the roll record (#879), or None when they
    are absent or do not match the dice and the total."""
    if (not isinstance(faces, list) or len(faces) != count
            or any(type(face) is not int or not 1 <= face <= sides for face in faces)
            or sum(faces) != total):
        return None
    return list(faces)


def player_great_weapon(encounter, characters, record, entry):
    """Whether the player's weapon swing on ``record`` has Great Weapon Fighting
    (#879); read once when its damage is asked for and stored on the record."""
    actor = combatant_by_id(encounter, record.get("actorId"))
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    return great_weapon_applies(sheet, entry)[0]


def resolve_player_weapon_attack(encounter, characters, intent, record, event_id, roll_source=None):
    """Score the player's swing from the typed faces on the completed roll
    phase through resolve_intent (crit, natural 1, typed damage traits, the
    event shape); the journal keeps the faces as typed."""
    entry = weapon_attack_sheet_entry(encounter, characters, record)
    faces = record.get("faces") or {}
    pools = {"d20": list(faces.get("attack") or [])}
    damage_total = faces.get("damage")
    damage_faces = None
    if type(damage_total) is int:
        count, sides = player_weapon_attack_dice(dict(record, phase="damage"), entry)
        damage_faces = _damage_faces(faces.get("damageFaces"), count, sides, damage_total)
        pools["d%d" % sides] = damage_faces or _split_total(damage_total, count, sides)
    # #879: Great Weapon Fighting needs each die; a window saved before its faces
    # were kept (a total only) is scored as before, without it.
    great_weapon = record.get("greatWeapon") is True and damage_faces is not None
    scored = {
        "actorId": record.get("actorId"),
        "action": "attack",
        "ability": record.get("ability"),
        # P-1: the swing reaches resolve_intent with its row's position (a
        # phase opened before K1 gets the position of the row found for it).
        "abilityRow": deepcopy(record.get("abilityRow")) or _row_ref_of(encounter, characters, record, entry),
        "targetId": record.get("targetId"),
        "description": (intent or {}).get("description", ""),
    }
    added = [dict(roll) for roll in faces.get("bonusDice") or []]
    _replay_added_dice(roll_source, added)
    resolution = resolve_intent(
        encounter, characters, scored, DeterministicRollSource(pools), event_id,
        mode_override=(record.get("mode"), list(record.get("modeSources") or [])),
        great_weapon=great_weapon,
        bonus_dice=added,
    )
    event = resolution["event"]
    event["intent"] = deepcopy(intent if isinstance(intent, dict) else scored)
    sources = record.get("sources") or {}
    rolls = [dict(r, source=sources.get("attack", "player")) for r in event["rolls"] if r.get("purpose") == "attack"]
    rolls += [dict(r, source="game") for r in event["rolls"] if r.get("purpose") == "attackBonus"]
    if type(damage_total) is int and event["outcome"].get("hit"):
        count, sides = player_weapon_attack_dice(dict(record, phase="damage"), entry)
        row = {"die": "%dd%d" % (count, sides), "value": damage_total, "purpose": "damage",
               "source": sources.get("damage", "player")}
        if damage_faces is not None:
            row["faces"] = list(damage_faces)
            if great_weapon:
                row["facesTreated"] = great_weapon_treated(damage_faces)
                row["value"] = sum(row["facesTreated"])
                row["rule"] = GREAT_WEAPON_RULE
        rolls.append(row)
    event["rolls"] = rolls
    event["outcome"]["scoredBy"] = "code"
    return resolution


# #672: the player's cast of a spell with a typed attack record
# (data/srd_spell_attacks.json) takes the plain swing's code-issued roll
# phase: the d20, then the spell's damage dice on a hit. The stored intent
# keeps the model's resources (the slot) and effects; code scores the
# attack and the damage. Typed fields only.
def player_spell_attack_entry(encounter, characters, intent):
    """The roll phase's spell entry when the intent is a cast of a recorded
    spell attack at exactly one hostile, targetable creature; None otherwise.
    The entry fixes the damage dice (slot or character level) and the spell
    attack bonus when the phase opens."""
    if not isinstance(intent, dict) or intent.get("action") != "cast" or intent.get("save") is not None:
        return None
    attacks = intent.get("attacks")
    if attacks is not None and not (type(attacks) is int and attacks == 1):
        return None
    request = intent.get("requiresPlayerInput")
    if request is not None and not (isinstance(request, dict) and request.get("kind") == "roll"):
        return None
    from core.ai import srd_roll_contracts, srd_spell_attacks

    status, record, phase = srd_spell_attacks.lookup(intent.get("ability"))
    if status != "recorded" or phase is None:
        return None
    target_id = intent.get("targetId")
    targets = intent.get("targets") or []
    if not isinstance(targets, list) or len(targets) > 1:
        return None
    if targets:
        listed = targets[0]
        if not isinstance(listed, dict) or listed.get("hpDelta", 0) != 0 or type(listed.get("hpDelta", 0)) is not int:
            return None
        if target_id is None:
            target_id = listed.get("combatantId")
        elif listed.get("combatantId") != target_id:
            return None
    actor = combatant_by_id(encounter, intent.get("actorId"))
    target = combatant_by_id(encounter, target_id) if isinstance(target_id, str) else None
    if actor is None or target is None:
        return None
    if (not is_hostile(target) or not is_combatant_targetable(target)
            or target.get("faction") == actor.get("faction")):
        return None
    effects = intent.get("effects") or []
    if not isinstance(effects, list) or any(
        not isinstance(op, dict) or op.get("applyOn", "always") not in SPELL_ATTACK_APPLY_ON for op in effects
    ):
        return None
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    casting = sheet.get("spellcasting") if isinstance(sheet, dict) else None
    bonus = casting.get("spellAttackBonus") if isinstance(casting, dict) else None
    if type(bonus) is not int or not _sheet_lists_spell(casting, record["name"]):
        return None
    slot_level = None
    level = None
    if (phase.get("scaling") or {}).get("kind") == "slot_level":
        # #724 (D-724-1 A): a cast that spends no slot (Spiritual Weapon's
        # later attacks) is scored at its typed slotLevel, else the contract's
        # base level, the level the roll audit assumes.
        slot_level = srd_roll_contracts._slot_level(intent, {}, actor.get("name"))
        if slot_level is None:
            slot_level = phase["scaling"].get("baseLevel")
        if type(slot_level) is not int or slot_level < 1:
            return None
    else:
        level = sheet.get("level") if type(sheet.get("level")) is int else None
    dice = srd_spell_attacks.damage_dice(phase, slot_level, level)
    if dice is None:
        return None
    # The record owns all effects of this attack on its target, regardless of name.
    riders = record.get("onHit") or []
    if riders:
        intent["effects"] = [op for op in effects
                             if op.get("combatantId") != target["combatantId"]
                             and op.get("owner") != target["name"]]
        for rider in riders:
            op = {"op": "add", "applyOn": "hit", "hitTargetId": target["combatantId"],
                  "effect": deepcopy(rider["effect"])}
            if target.get("type") in ("player", "npc"):
                op["owner"] = target["name"]
            else:
                op["combatantId"] = target["combatantId"]
            intent["effects"].append(op)
    entry = {
        "name": record["name"],
        "type": record["attack"],
        "damageDice": "%dd%d" % dice,
        "damageType": record["damageKind"],
        "attackBonus": bonus + modifier_total(sheet, "spellAttackBonus"),
        "record": record["source"],
        "slotLevel": slot_level,
        "characterLevel": level,
        "targetId": target["combatantId"],
    }
    if record["abilityModifierToDamage"]:
        # #724: the caster's spellcasting ability modifier, added to the damage once.
        ability = casting.get("ability")
        abilities = sheet.get("abilities") if isinstance(sheet.get("abilities"), dict) else {}
        score = abilities.get(ability) if isinstance(ability, str) else None
        if type(score) is not int:
            return None
        entry["damageBonus"] = (score - 10) // 2
    return entry


SPELL_ATTACK_APPLY_ON = ("always", "hit")


def _sheet_lists_spell(casting, name):
    """True when the caster's spellcasting lists the spell (a spells level
    list or preparedSpells), compared by the roll contracts' canonical key."""
    from core.ai import srd_roll_contracts

    key = srd_roll_contracts._canonical_key(name)
    spells = casting.get("spells") if isinstance(casting.get("spells"), dict) else {}
    lists = [value for value in spells.values() if isinstance(value, list)]
    lists.append(casting.get("preparedSpells") if isinstance(casting.get("preparedSpells"), list) else [])
    return any(
        isinstance(entry, str) and srd_roll_contracts._canonical_key(entry) == key
        for listed in lists for entry in listed
    )


def open_player_spell_attack(encounter, characters, intent, spell, rolls=None):
    """The roll-phase record for a spell attack: the swing's record (mode fixed
    now) plus the spell entry under ``spell``."""
    entry = {"name": spell["name"], "type": spell["type"]}
    record = open_player_weapon_attack(encounter, characters, dict(intent, targetId=spell["targetId"]), entry,
                                       rolls)
    record["spell"] = dict(spell)
    return record


def spell_attack_proposal(intent, target_id, damage):
    """The adjudicated proposal the stored intent resolves as: the model's
    resources and effects, the code-scored damage on the one target."""
    proposal = deepcopy(intent)
    proposal.pop("requiresPlayerInput", None)
    proposal["targets"] = [{"combatantId": target_id, "hpDelta": -int(damage)}]
    return proposal


def spell_attack_violations(encounter, characters, intent, spell):
    """The violations the stored intent would resolve with (a hit for 0
    damage), found before any roll is asked for; on copies, so a check
    never changes the fight."""
    try:
        resolution = resolve_adjudicated(
            deepcopy(encounter), deepcopy(characters), spell_attack_proposal(intent, spell["targetId"], 0),
            DeterministicRollSource({}), "spell-attack-check", attack_hits={spell["targetId"]: True},
        )
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        return [str(exc)]
    return list(resolution["violations"])


def resolve_player_spell_attack(encounter, characters, intent, record, event_id, rolls):
    """Score the player's spell attack from the typed faces on the completed
    roll phase: the engine decides hit, miss and critical and applies the
    target's typed damage traits to the damage dice; today's arithmetic is
    the fallback. The stored intent then resolves through resolve_adjudicated
    (the slot, the effects; applyOn 'hit' effects only on a hit)."""
    from core.nql import attacks

    entry = weapon_attack_sheet_entry(encounter, characters, record)
    spell = record.get("spell") or {}
    actor = combatant_by_id(encounter, record.get("actorId"))
    target = combatant_by_id(encounter, record.get("targetId"))
    if entry is None or target is None:
        raise ValueError("the spell attack's caster or target is gone")
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    trait_sheet = _raw_combatant_sheet(encounter, characters, target)
    faces = record.get("faces") or {}
    attack_faces = list(faces.get("attack") or [])
    mode = record.get("mode")
    critical_phase = bool(record.get("critical"))
    total_rolled = faces.get("damage") if type(faces.get("damage")) is int else None
    to_hit = int(entry["attackBonus"]) + modifier_total(sheet, "attackRolls")
    added = [dict(roll) for roll in faces.get("bonusDice") or []]
    to_hit += sum(int(roll["value"]) for roll in added)
    ac = _combatant_ac(encounter, characters, target)
    count, sides, _flat = parse_dice(entry["damageDice"])
    damage_bonus = int(spell.get("damageBonus") or 0)
    scored = attacks.score(
        to_hit=to_hit, count=count, sides=sides, bonus=damage_bonus, damage_type=entry["damageType"], mode=mode,
        faces=attack_faces, target_ac=ac, target_hp=int(target.get("currentHitPoints", 0) or 0),
        target_max_hp=_combatant_max_hp(encounter, characters, target), target_sheet=trait_sheet,
        damage=None if critical_phase else total_rolled,
        critical_damage=total_rolled if critical_phase else None,
    )
    if scored.ok and (not scored.hit or scored.damage_rolled == total_rolled):
        hit, critical, kept, total = bool(scored.hit), bool(scored.critical), int(scored.kept), int(scored.total)
        raw_damage = scored.raw_damage if hit else 0
        damage, traits = (int(scored.damage or 0), list(scored.traits)) if hit else (0, [])
        engine = True
    else:
        try:
            from utils.enhanced_logger import warning as _warning
            _warning("AS: %s scored without the engine (%s)" % (
                entry["name"], scored.reason or "damage %s, engine used %s" % (total_rolled, scored.damage_rolled)),
                category="combat_events")
        except Exception:
            pass
        kept = (max(attack_faces) if mode == "advantage"
                else min(attack_faces) if mode == "disadvantage" else attack_faces[0])
        total = kept + to_hit
        critical = kept == 20
        hit = critical or (kept != 1 and total >= ac)
        raw_damage = max(0, (total_rolled or 0) + damage_bonus) if hit else 0
        damage, traits = _typed_damage(trait_sheet, entry["damageType"], raw_damage) if hit else (0, [])
        engine = False
    if hit and (total_rolled is None or critical != critical_phase):
        # The faces scored differently from when the damage was asked for:
        # the model rules the window from the exchanges (fail forward).
        raise ValueError("the spell attack's damage roll does not match its hit")
    _replay_added_dice(rolls, added)
    resolution = resolve_adjudicated(
        encounter, characters, spell_attack_proposal(intent, target["combatantId"], damage), rolls, event_id,
        attack_hits={target["combatantId"]: hit},
    )
    event = resolution["event"]
    event["intent"] = deepcopy(intent)
    sources = record.get("sources") or {}
    attack_rolls = []
    for face in attack_faces:
        roll = {"die": "d20", "value": face, "purpose": "attack", "source": sources.get("attack", "player")}
        if mode in PLAYER_DECLARED_MODES:
            roll["mode"] = mode
        attack_rolls.append(roll)
    attack_rolls += [dict(roll, source="game") for roll in added]
    if hit:
        attack_rolls.append({"die": "%dd%d" % (count * (2 if critical else 1), sides), "value": total_rolled,
                             "purpose": "damage", "source": sources.get("damage", "player")})
    event["rolls"] = attack_rolls + list(event.get("rolls") or [])
    spell_record = {
        "spell": spell.get("name"), "record": spell.get("record"), "attack": spell.get("type"),
        "toHit": to_hit, "faces": attack_faces, "kept": kept, "mode": mode, "engine": engine,
        "damageDice": entry["damageDice"], "damageType": entry["damageType"],
    }
    if record.get("modeSources"):
        spell_record["modeSources"] = list(record["modeSources"])
    if spell.get("slotLevel") is not None:
        spell_record["slotLevel"] = spell["slotLevel"]
    if "damageBonus" in spell:
        spell_record["damageBonus"] = damage_bonus
    if hit:
        spell_record.update({"damageRolled": total_rolled, "rawDamage": raw_damage, "damage": damage})
        if traits:
            spell_record["damageTraits"] = traits
    event["outcome"].update({
        "hit": hit, "critical": critical, "attackRoll": kept, "totalAttack": total, "targetAC": ac,
        "damage": damage, "scoredBy": "code", "spellAttack": spell_record,
    })
    return resolution


# #723: the player's cast of a spell with a typed save record
# (data/srd_spell_saves.json, #703) takes the same code-issued roll phase,
# save first: code scores each target's save from the persisted prerolls
# before any damage is asked for, and asks once for the spell's damage dice
# only when a target takes damage. The stored intent keeps the model's
# resources (the slot) and effects. Typed fields only.
SPELL_SAVE_ACTIONS = ("cast", "ability")
SPELL_SAVE_APPLY_ON = ("always", "failedSave", "successfulSave")


def player_spell_save_entry(encounter, characters, intent):
    """The roll phase's spell entry when the intent is a cast of a recorded
    save spell at one or more listed, targetable creatures (each hpDelta 0;
    a typed targetId with no targets listed is that one target) by a caster
    whose sheet lists the spell and states its spell save DC; None
    otherwise. The entry fixes the damage dice (slot or character level) and
    the save when the phase opens."""
    if not isinstance(intent, dict) or intent.get("action") not in SPELL_SAVE_ACTIONS:
        return None
    attacks = intent.get("attacks")
    if attacks is not None and not (type(attacks) is int and attacks == 1):
        return None
    request = intent.get("requiresPlayerInput")
    if request is not None and not (isinstance(request, dict) and request.get("kind") == "roll"):
        return None
    save = intent.get("save")
    targets = intent.get("targets")
    if targets in (None, []) and isinstance(intent.get("targetId"), str):
        targets = [{"combatantId": intent["targetId"], "hpDelta": 0}]
    if (save is not None and not isinstance(save, dict)) or not isinstance(targets, list) or not targets:
        return None
    target_ids = []
    for listed in targets:
        if not isinstance(listed, dict) or type(listed.get("hpDelta", 0)) is not int or listed.get("hpDelta", 0) != 0:
            return None
        listed_id = listed.get("combatantId")
        target = combatant_by_id(encounter, listed_id) if isinstance(listed_id, str) else None
        if target is None or not is_combatant_targetable(target):
            return None
        target_ids.append(target["combatantId"])
    if len(set(target_ids)) != len(target_ids):
        return None
    if intent.get("targetId") is not None and intent.get("targetId") not in target_ids:
        return None
    effects = intent.get("effects") or []
    if not isinstance(effects, list) or any(
        not isinstance(op, dict) or op.get("applyOn", "always") not in SPELL_SAVE_APPLY_ON for op in effects
    ):
        return None
    actor = combatant_by_id(encounter, intent.get("actorId"))
    if actor is None:
        return None
    sheet = _raw_combatant_sheet(encounter, characters, actor)
    casting = sheet.get("spellcasting") if isinstance(sheet, dict) else None
    if not isinstance(casting, dict) or type(casting.get("spellSaveDC")) is not int or casting["spellSaveDC"] <= 0:
        return None
    from core.ai import srd_roll_contracts, srd_spell_saves

    status, record, phase = srd_spell_saves.lookup(intent.get("ability"))
    if status != "recorded" or phase is None or not _sheet_lists_spell(casting, record["name"]):
        return None
    if save_row(sheet, intent.get("abilityRow"), actor.get("combatantId")) is not None:
        # K1: the cast names a listed save ability by its abilityRow; it stays adjudicated.
        return None
    if (srd_roll_contracts.slot_level_mismatch(intent, actor.get("name"))
            or srd_roll_contracts.slot_below_spell_level(intent, actor.get("name"))):
        # F4-Q3 A: never opened at the claimed level; the adjudicated
        # path returns the mismatch to the model as a violation (#942:
        # also a slot below the spell's level).
        return None
    slot_level = None
    level = None
    if (phase.get("scaling") or {}).get("kind") == "slot_level":
        slot_level = srd_roll_contracts._slot_level(intent, {}, actor.get("name"))
        if slot_level is None:
            return None
    else:
        level = sheet.get("level") if type(sheet.get("level")) is int else None
    rule = _spell_save_rule(encounter, characters, intent, save, targets, {})
    if rule is None or rule["dice"] is None:
        return None
    return {
        "name": record["name"],
        "type": "save",
        "damageDice": "%dd%d" % rule["dice"],
        "damageType": rule["kind"],
        "record": record["source"],
        "slotLevel": slot_level,
        "characterLevel": level,
        "targetId": target_ids[0],
        "targetIds": target_ids,
        "save": {"type": rule["spec"]["type"], "dc": rule["spec"]["dc"], "success": rule["success"]},
    }


def spell_save_proposal(intent, target_ids, damage):
    """The adjudicated proposal the stored intent resolves as: the model's
    resources and effects, and the rolled total on every target of the entry
    (the #703 save applies the record's effect to it per target)."""
    proposal = deepcopy(intent)
    proposal.pop("requiresPlayerInput", None)
    listed = {entry.get("combatantId"): entry for entry in intent.get("targets") or [] if isinstance(entry, dict)}
    proposal["targets"] = [dict(listed.get(target_id) or {"combatantId": target_id}, hpDelta=-int(damage))
                           for target_id in target_ids]
    return proposal


def open_player_spell_save(encounter, characters, intent, spell, rolls):
    """The roll-phase record for a save-first cast, or None (today's path).

    The stored intent is resolved on copies with no damage, from ``rolls`` (a
    fresh copy of the persisted preroll pool; nothing is consumed): the same
    #703 path scores each target's save alone, and any violation (an
    overspent slot, a bad effect) keeps today's path. The faces and verdicts
    are persisted on the record; ``ready`` when no target takes damage."""
    try:
        preview = resolve_adjudicated(
            deepcopy(encounter), deepcopy(characters), spell_save_proposal(intent, spell["targetIds"], 0), rolls,
            "spell-save-check",
        )
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    if preview["violations"]:
        return None
    scored = {
        roll.get("combatantId"): roll for roll in preview["event"].get("rolls") or []
        if roll.get("purpose") == "save" and roll.get("spell") == spell["name"]
    }
    save = spell["save"]
    results = []
    for target_id in spell["targetIds"]:
        roll = scored.get(target_id)
        if roll is None:
            return None
        target = combatant_by_id(encounter, target_id)
        success = bool(roll.get("success"))
        kept = roll.get("kept", roll.get("value"))
        result = {
            "combatantId": target_id,
            "name": target.get("name") or target_id,
            "faces": list(roll.get("faces") or []),
            "kept": kept,
            "bonus": roll.get("bonus"),
            "total": roll.get("total") if roll.get("engine") else (kept or 0) + int(roll.get("bonus") or 0),
            "success": success,
            "effect": roll.get("effect") or (save["success"] if success else "full"),
            "engine": bool(roll.get("engine")),
        }
        if roll.get("mode") not in (None, "normal"):
            result["mode"] = roll["mode"]
        results.append(result)
    names = [result["name"] for result in results]
    record = {
        "actorId": intent.get("actorId"),
        "ability": spell["name"],
        "targetId": spell["targetId"],
        "targetName": ", ".join(names),
        "mode": None,
        "modeSources": [],
        "phase": "damage",
        "faces": {},
        "sources": {},
        "spell": dict(spell, save=dict(save, results=results)),
    }
    if all(result["effect"] == "none" for result in results):
        # Every target saved against a spell that does nothing on a save:
        # no roll is asked (Q3); the window resolves with no damage.
        record["ready"] = True
    return record


class _ReplayedSaveRolls(object):
    """#723: the roll source for a save-first cast. Each target's save faces
    are the ones persisted when the phase opened (the player saw them); the
    persisted pool underneath still advances by the same takes, so the
    consumption cursors are today's."""

    def __init__(self, rolls, faces):
        self._rolls = rolls
        self._faces = {target_id: list(values) for target_id, values in faces.items()}

    def take(self, die):
        return self._rolls.take(die)

    def take_for(self, die, purpose, actor_id=None, target_id=None, ability=None):
        value = _take_roll(self._rolls, die, purpose, actor_id=actor_id, target_id=target_id, ability=ability)
        if purpose == "save" and self._faces.get(target_id):
            return self._faces[target_id].pop(0)
        return value

    def unreplayed(self):
        return any(self._faces.values())

    def __getattr__(self, name):
        return getattr(self._rolls, name)


def resolve_player_spell_save(encounter, characters, intent, record, event_id, rolls):
    """Resolve a save-first cast from the completed roll phase: the stored
    intent goes through resolve_adjudicated with the rolled total (0 when no
    target takes damage) on every target, and the persisted save faces are
    replayed, so the saves are scored once, as the player saw them."""
    spell = record.get("spell") or {}
    save = spell.get("save") or {}
    results = save.get("results") or []
    rolled = (record.get("faces") or {}).get("damage")
    needs_damage = any(result.get("effect") != "none" for result in results)
    if not results or (needs_damage and type(rolled) is not int):
        raise ValueError("the save-first cast has no damage roll to apply")
    replay = _ReplayedSaveRolls(rolls, {result["combatantId"]: result["faces"] for result in results})
    resolution = resolve_adjudicated(
        encounter, characters, spell_save_proposal(intent, spell.get("targetIds") or [], rolled if needs_damage else 0),
        replay, event_id,
    )
    event = resolution["event"]
    scored = {
        roll.get("combatantId"): roll for roll in event.get("rolls") or []
        if roll.get("purpose") == "save" and roll.get("spell") == spell.get("name")
    }
    for result in results:
        roll = scored.get(result["combatantId"])
        if roll is None or bool(roll.get("success")) != bool(result["success"]):
            # Fail forward: the model rules the window from the exchanges.
            raise ValueError("a save scored differently from when its phase opened")
    if replay.unreplayed():
        raise ValueError("a persisted save face was not taken")
    event["intent"] = deepcopy(intent)
    if needs_damage:
        event["rolls"] = [{"die": spell.get("damageDice"), "value": rolled, "purpose": "damage",
                           "source": (record.get("sources") or {}).get("damage", "player")}] + list(event["rolls"])
    spell_record = {
        "spell": spell.get("name"), "record": spell.get("record"), "save": save.get("type"), "dc": save.get("dc"),
        "success": save.get("success"), "damageDice": spell.get("damageDice"), "damageType": spell.get("damageType"),
        "targets": [{key: result[key] for key in ("combatantId", "faces", "success", "effect")} for result in results],
    }
    if needs_damage:
        spell_record["damageRolled"] = rolled
    else:
        spell_record["noDamageRoll"] = True
    if spell.get("slotLevel") is not None:
        spell_record["slotLevel"] = spell["slotLevel"]
    event["outcome"].update({"scoredBy": "code", "spellSave": spell_record})
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
        # #891: a feat's use (feats[].usage) after the class features.
        for feature in list((sheet or {}).get("classFeatures", []) or []) + list((sheet or {}).get("feats", []) or []):
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
    if kind == "charges":
        # H3: a charged equipment row. The engine decides the spend; this
        # snapshot only makes the record resolvable. A catalog row still
        # waiting for its engine-minted state reads 0 of its type's max.
        row = _charged_row(sheet, name)
        if row is None:
            return None
        charges = row.get("charges") if isinstance(row.get("charges"), dict) else {}
        current = charges.get("current") if type(charges.get("current")) is int else 0
        cap = charges.get("max") if type(charges.get("max")) is int else None
        return current, cap
    return None


def _charged_row(sheet, name):
    """The equipment row named ``name`` when it carries charges: a ``charges``
    object (H1) or a charged SRD catalog type (H2b). None otherwise."""
    for item in (sheet or {}).get("equipment", []):
        if isinstance(item, dict) and item.get("item_name") == name:
            if isinstance(item.get("charges"), dict):
                return item
            try:
                from core.nql import genesis
                return item if genesis.charge_rule(item) is not None else None
            except Exception:
                return None
    return None


def _engine_charges(encounter, sheet, owner, name, delta, event_id, record):
    """H3: the rules engine spends ``-delta`` charges of the holder's item on
    the in-memory sheet and the engine's normalized state is journaled on the
    resource record (chargesAfter, exhausted, engine true), so apply and any
    replay write the same values without the engine. The clock is the fight's
    frozen effect clock. Returns (True, None), or (the violation text, the
    refusal's plain fact; None for a model mistake): a short count is
    an overspend (T096 corrects); every other refusal, the engine unavailable
    included, leaves the item unspent (the count is engine-owned, there is no
    arithmetic to fall back on)."""
    if type(delta) is not int or delta >= 0:
        return "charges are never added in combat: %s %s" % (owner, name), None
    state = encounter.get("combatState") or {}
    clock = state.get("effectsClockScalar") if type(state.get("effectsClockScalar")) is int else None
    try:
        from core.managers.item_charges import combat_request_id, combat_spend
        outcome = combat_spend(sheet, name, -delta, clock, "combat", combat_request_id(event_id, owner, name))
    except Exception as exc:  # engine wrapper faults never stop a fight
        return "%s could not be spent (%s)" % (name, exc), "unusable"
    if not outcome.get("ok"):
        fact = outcome.get("fact") or "unusable"
        if outcome.get("overspend"):
            return "overspend rejected: %s charges %s (%s)" % (owner, name, outcome.get("reason")), fact
        return "%s could not be spent (%s)" % (name, outcome.get("reason")), fact
    record["before"] = outcome["before"]
    record["after"] = outcome["after"]
    record["chargesAfter"] = outcome["chargesAfter"]
    record["request"] = combat_request_id(event_id, owner, name)
    record["nqlId"] = outcome.get("nqlId")
    record["message"] = outcome.get("message")
    if isinstance(outcome.get("exhausted"), dict):
        record["exhausted"] = outcome["exhausted"]
    record["engine"] = True
    return True, None


def _save_bonus(encounter, characters, creature, save_type):
    raw_sheet = _raw_combatant_sheet(encounter, characters, creature)
    sheet = effective_sheet(raw_sheet)
    saves = sheet.get("savingThrows") or []
    ability = save_ability(save_type) or ""
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
    if ability and isinstance(saves, list) and any(
        save_ability(item) == ability for item in saves
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


_ABILITY_ALIASES = {"str": "strength", "dex": "dexterity", "con": "constitution",
                    "int": "intelligence", "wis": "wisdom", "cha": "charisma"}


def save_ability(save_type):
    """The ability a save type names: one of the six ability names or its
    three-letter code, whole and casefolded; None for any other value."""
    if not isinstance(save_type, str):
        return None
    text = save_type.strip().casefold()
    text = _ABILITY_ALIASES.get(text, text)
    return text if text in _ABILITY_ALIASES.values() else None


def _engine_added_dice(dice, rolls):
    """#889: faces for the added dice the engine holds on a party save
    (``net_mode``'s dice), taken from the fight's pool and journaled as the
    sheet's saveBonus rolls are; sent as the engine's ``added`` faces, so the
    journal stays the replay authority. Returns (journal, [(type, faces)])."""
    journal = []
    groups = []
    for die in dice or []:
        faces = [int(rolls.take("d%d" % die["sides"])) for _ in range(die["count"])]
        condition_type = die["type"]
        effect = condition_type[len("effect:"):] if condition_type.startswith("effect:") else condition_type
        journal.extend({"die": "1d%d" % die["sides"], "value": face, "purpose": "saveBonus", "effect": effect}
                       for face in faces)
        groups.append((condition_type, faces))
    return journal, groups


def _engine_save(sheet, save_type, dc, rolls, actor_id, target_id, player_faces=None):
    """CS: the rules engine rolls one party member's saving throw.

    The engine knows the sheet's save total and the roll mode its conditions
    impose (Restrained: disadvantage on Dexterity saves; Paralyzed: Strength
    and Dexterity saves fail). Code reads that mode first, takes that many
    persisted d20 faces (none for an automatic failure, two for advantage or
    disadvantage, else one) so the journal stays the replay authority, and
    hands them to the engine, with the faces of any added die (Bless, #889).
    3b: ``player_faces`` are the checked d20 faces the player rolled for
    this save; they are used first, and only a face the roll mode needs
    beyond them comes from the persisted pool.
    Returns (result, faces, added) or None when the engine
    is unavailable or refuses, in which case the caller keeps today's
    arithmetic (fail forward, the fight never pauses for the engine).
    """
    try:
        from core.nql import checks as nql_checks
        ability = save_ability(save_type)
        if ability is None:
            return None
        stat = "save:" + ability
        mode = nql_checks.net_mode(sheet, stat)
        if mode.reason:
            return None
        needed = nql_checks.faces_needed(mode.mode)
        faces = list(player_faces or [])[:needed]
        faces += [
            _take_roll(rolls, "d20", "save", actor_id=actor_id, target_id=target_id, ability=ability)
            for _ in range(needed - len(faces))
        ]
        added, groups = ([], []) if mode.mode == "fail" else _engine_added_dice(mode.dice, rolls)
        result = nql_checks.resolve(sheet, stat, dc=int(dc), faces=faces or None, added=groups or None)
    except Exception as exc:  # engine wrapper faults never stop a fight
        _warn_save(sheet, save_type, str(exc))
        return None
    if not result.ok or result.success is None:
        _warn_save(sheet, save_type, result.reason or "engine returned no verdict")
        return None
    try:
        from utils.enhanced_logger import info as _info
        _info("CS: engine save: %s" % nql_checks.describe(result), category="combat_events")
    except Exception:
        pass
    return result, faces, added


def _player_save_faces(proposal, target):
    """3b: the d20 faces the player rolled for their own save, as checked
    against the typed request by the orchestrator, or None."""
    roll = proposal.get("playerRoll")
    if not isinstance(roll, dict) or roll.get("phase") != "save":
        return None
    if roll.get("requestedRoll") not in ("1d20", "2d20", "d20"):
        return None
    if target.get("combatantId") != proposal.get("actorId"):
        return None
    faces = roll.get("faces")
    group = faces[0] if isinstance(faces, list) and faces and isinstance(faces[0], list) else []
    group = [face for face in group if type(face) is int and 1 <= face <= 20]
    return group or None


def _player_save_dc(proposal, target, save_spec, player_faces, event):
    """Item 10 (r2): the DC of the player's own save. When the player
    answered a save request asked at a DC (playerRoll.requestedDc, typed
    when the request was made), that DC; a different supplied dc is
    journaled. Otherwise the supplied dc, 10 when none."""
    roll = proposal.get("playerRoll")
    asked = roll.get("requestedDc") if player_faces and isinstance(roll, dict) else None
    if type(asked) is not int:
        return save_spec.get("dc", 10) or 10
    if save_spec.get("dc") != asked:
        event.setdefault("normalizations", []).append({
            "kind": "askedSaveDc", "combatantId": target.get("combatantId"),
            "supplied": save_spec.get("dc"), "applied": asked})
    return asked


def _spell_save_rule(encounter, characters, proposal, save_spec, targets, event):
    """#703: the typed save of a spell with a record, or None (today's path).

    The intent's ``ability`` is looked up by the roll contracts' canonical key
    (a typed key, never the description). The record gives the ability and
    the effect of a success; the DC is the party caster's sheet spellSaveDC
    (with its effect modifiers), else the supplied DC. A ``spellSave``
    normalization journals every difference from the model's save object.
    """
    name = proposal.get("ability")
    if not isinstance(name, str) or not name.strip():
        return None
    if save_spec is None and not targets:
        return None
    from core.ai import srd_roll_contracts, srd_spell_saves

    status, record, phase = srd_spell_saves.lookup(name)
    if status != "recorded":
        if save_spec is not None:
            _log_spell_save("spell_save_unchecked: %s (%s); the model's save applies" % (name, status))
        return None
    caster = _sheet_backed_target(characters, combatant_by_id(encounter, proposal.get("actorId")))
    dc = None
    casting = caster.get("spellcasting") if caster is not None else None
    stored = casting.get("spellSaveDC") if isinstance(casting, dict) else None
    if type(stored) is int and stored > 0:
        dc = stored + modifier_total(caster, "spellSaveDC")
    else:
        supplied_dc = (save_spec or {}).get("dc")
        if type(supplied_dc) is int and supplied_dc > 0:
            dc = supplied_dc
    if dc is None:
        _log_spell_save("spell_save_unchecked: %s has no DC (no caster spellSaveDC, none supplied)" % name)
        return None
    spec = {"type": record["save"], "dc": dc, "halfOnSave": record["success"] == "half"}
    supplied = {
        "type": str((save_spec or {}).get("type") or "").strip().lower(),
        "dc": (save_spec or {}).get("dc"),
        "halfOnSave": bool((save_spec or {}).get("halfOnSave")),
    }
    if save_spec is None or supplied != spec:
        event.setdefault("normalizations", []).append({
            "kind": "spellSave",
            "spell": record["name"],
            "record": record["source"],
            "supplied": deepcopy(save_spec),
            "applied": dict(spec),
        })
    level = caster.get("level") if caster is not None else None
    dice = srd_spell_saves.damage_dice(
        phase,
        srd_roll_contracts._slot_level(
            proposal, {}, (combatant_by_id(encounter, proposal.get("actorId")) or {}).get("name")),
        level if type(level) is int else None,
    ) if phase else None
    return {"name": record["name"], "spec": spec, "success": record["success"],
            "kind": record["damageKind"], "dice": dice}


def _spell_save_target(encounter, characters, proposal, target, spell_save, hp_delta, rolls, event):
    """#703: one target's save against a recorded spell: (saved, hp_delta, save_line).

    Code takes the d20 faces the target's roll mode needs from the persisted
    prerolls (as the CS party save does; one for a monster). The engine
    scores the save and applies the record's effect, then the target's damage
    traits, to the rolled total: |hpDelta|, which it range-checks against the
    spell's dice. A refused total is applied by the record's effect without
    the engine (the save is still the engine's); an unavailable engine keeps
    the arithmetic with the same faces. The HP change itself stays CH's.
    """
    from core.nql import checks as nql_checks
    from core.nql import saves as nql_saves

    spec = spell_save["spec"]
    ability, dc = spec["type"], spec["dc"]
    stat = nql_saves.stat_id(ability)
    party = _sheet_backed_target(characters, target)
    mode = "normal"
    dice = None
    if party is not None:
        try:
            net = nql_checks.net_mode(party, stat)
            if not net.reason:
                mode = net.mode
                dice = net.dice
        except Exception:  # engine wrapper faults never stop a fight
            pass
    faces = [
        _take_roll(rolls, "d20", "save", actor_id=proposal.get("actorId"),
                   target_id=target.get("combatantId"), ability=ability)
        for _ in range(nql_checks.faces_needed(mode))
    ]
    total = -hp_delta if hp_delta < 0 else None
    name = target.get("name") or target["combatantId"]
    record = {"die": "d20", "purpose": "save", "combatantId": target["combatantId"],
              "spell": spell_save["name"], "faces": faces}
    scored = None
    unchecked = None
    # #889: the target's added save dice, taken once for both paths: for a
    # party target the dice the engine holds (sent as its added faces), else
    # the sheet's; an automatic failure rolls none.
    groups = []
    if party is not None and mode == "fail":
        added = []
    elif party is not None and dice is not None:
        added, groups = _engine_added_dice(dice, rolls)
    else:
        added = _save_added_dice(encounter, characters, target, ability, rolls)
    if added:
        record["added"] = added
    if spell_save["dice"] is not None:
        count, sides = spell_save["dice"]
        arguments = dict(
            ability=ability, dc=dc, count=count, sides=sides, damage_type=spell_save["kind"],
            success=spell_save["success"], faces=faces, party_sheet=party, added_faces=groups or None,
            save_bonus=(None if party is not None
                        else _save_bonus(encounter, characters, target, ability)
                        + sum(roll["value"] for roll in added)),
            target_hp=int(target.get("currentHitPoints", 0) or 0),
            target_max_hp=_combatant_max_hp(encounter, characters, target),
            target_sheet=_raw_combatant_sheet(encounter, characters, target),
        )
        scored = nql_saves.score(damage=total, **arguments)
        if not scored.ok and total is not None:
            # The total is off the spell's dice (a bonus the record does not
            # type, or a wrong roll): the engine still scores the save alone.
            unchecked = scored.reason
            scored = nql_saves.score(damage=None, **arguments)
    else:
        unchecked = "no damage dice for %s at this level" % spell_save["name"]
    if scored is not None and scored.ok:
        saved = bool(scored.success)
        record.update({"value": scored.kept if scored.kept is not None else 0, "bonus": scored.bonus,
                       "success": saved, "engine": True, "kept": scored.kept, "mode": scored.mode,
                       "sources": scored.sources, "total": scored.total, "margin": scored.margin,
                       "effect": scored.effect})
        if scored.unused_faces:
            record["unusedFaces"] = scored.unused_faces
        save_line = nql_saves.describe(scored, name, dc)
        event.setdefault("engineChecks", []).append(save_line)
        if total is not None and unchecked is None:
            record["damageRolled"] = total
            record["damage"] = int(scored.damage or 0)
            if scored.traits:
                record["traits"] = scored.traits
            event["rolls"].append(record)
            return saved, -int(scored.damage or 0), save_line
    else:
        reason = scored.reason if scored is not None else unchecked
        _log_spell_save("CS: %s %s save scored without the engine (%s)" % (name, ability, reason))
        bonus = _save_bonus(encounter, characters, target, ability)
        kept = (None if not faces else max(faces) if mode == "advantage"
                else min(faces) if mode == "disadvantage" else faces[0])
        saved = kept is not None and kept + bonus + sum(roll["value"] for roll in added) >= dc
        record.update({"value": kept or 0, "bonus": bonus, "success": saved, "engine": False})
        save_line = None
    if total is not None:
        record["damageRolled"] = total
        if unchecked is not None:
            record["damageUnchecked"] = unchecked
            _log_spell_save("CS: %s damage applied without the engine (%s)" % (spell_save["name"], unchecked))
    event["rolls"].append(record)
    if saved and hp_delta < 0:
        hp_delta = -((-hp_delta) // 2) if spec["halfOnSave"] else 0
    return saved, hp_delta, save_line


def _log_spell_save(message):
    try:
        from utils.enhanced_logger import warning as _warning
        _warning(message, category="combat_events")
    except Exception:
        pass


def _warn_save(sheet, save_type, reason):
    try:
        from utils.enhanced_logger import warning as _warning
        _warning(
            "CS: %s %s save rolled without the engine (%s)"
            % (sheet.get("name"), save_type, reason),
            category="combat_events",
        )
    except Exception:
        pass


PERSONAL_RESOURCE_KINDS = ("spellSlot", "featureUse")
# #968: the spends whose refusal for the player asks the player (#671), items and ammunition included.
PLAYER_ASK_KINDS = PERSONAL_RESOURCE_KINDS + ("item", "ammunition")


def _sheet_can_cast(sheet):
    """True when the sheet lists any spell or any spell slot."""
    spellcasting = sheet.get("spellcasting") if isinstance(sheet, dict) else None
    if not isinstance(spellcasting, dict):
        return False
    spells = spellcasting.get("spells")
    if isinstance(spells, dict) and any(spells.values()):
        return True
    if isinstance(spells, list) and spells:
        return True
    slots = spellcasting.get("spellSlots")
    for level in (slots.values() if isinstance(slots, dict) else []):
        if isinstance(level, dict) and int(level.get("max", 0) or 0) > 0:
            return True
    return False


def _removal_reference(op):
    """#725: the reference a remove op supplies (effectId, name or condition),
    read from its typed fields as the removal match reads them."""
    nested = op.get("effect") if isinstance(op.get("effect"), dict) else {}
    return (op.get("effectId") or nested.get("effectId") or op.get("name") or nested.get("name")
            or op.get("condition"))


def _refuse_removal(resolution, event, refusal, violation, drop):
    """#725 (D-725-1 A): a remove op that cannot be matched. On the actor's
    re-rule (drop) it is dropped as the ruling and recorded on the event;
    otherwise the violation stands and the typed refusal goes to the
    correction."""
    if drop:
        event.setdefault("normalizations", []).append(dict(refusal, kind="effectRemovalDropped"))
        return
    resolution["violations"].append(violation)
    resolution.setdefault("removalRefusals", []).append(refusal)


def resolve_adjudicated(encounter, characters, proposal, rolls, event_id, clamp_feature_heals=False,
                        attack_hits=None, drop_refused_removals=False):
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

    #669: a heal from a FEATURE_HEALS class feature above its typed limit is a
    violation carrying ``featureHealLimits`` (the correction's numbers); with
    ``clamp_feature_heals`` (the corrected batch broke it again) it is
    clamped to the limit and journaled as a ``featureHeal`` normalization.

    #672: ``attack_hits`` maps the target of a spell attack code scored to
    whether it hit; an effect op with applyOn 'hit' is staged only on a hit,
    and is a violation on any other intent.
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
    # Targets may be normalized below when a weak model supplies one exact,
    # provably redundant HP representation. Never mutate the provider payload
    # retained in event.intent.
    targets = deepcopy(proposal.get("targets", []) or [])
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
    if any(
        not isinstance(target_id, str) or not target_id
        for target_id in target_ids
    ):
        resolution["violations"].append(
            "every adjudicated target requires a string combatantId"
        )
        targets = []
    elif len(target_ids) != len(set(target_ids)):
        resolution["violations"].append("duplicate adjudicated targets are not allowed")
        targets = []

    # MS-a: a listed save ability (Web, a breath weapon) is declared by the
    # model with abilityRow = its listed rowRef (K1; ability is display text);
    # the stat block's typed save object is then the authority for the save,
    # the on-fail damage dice and the on-fail conditions. Code reconciles: the
    # save spec is taken from the entry, the damage is rolled from the
    # persisted prerolls, and a missing failed-save condition effect is staged
    # from the entry. Each correction is journaled as a normalization; replay
    # reads the journal. F5: with no abilityRow there is no stat-block lookup
    # and the model's ruling stands; one that names no listed row is corrected.
    stated_entry = None
    stated_save = None
    stated_dice = None
    stated_conditions = []
    stated_rounds = None
    actor_creature = combatant_by_id(encounter, proposal.get("actorId"))
    if actor_creature is not None and proposal.get("abilityRow") is not None:
        actor_sheet = _raw_combatant_sheet(encounter, characters, actor_creature)
        listed = row_at(actor_sheet, proposal.get("abilityRow"), ROW_FAMILIES, actor_creature.get("combatantId"))
        if listed is None:
            resolution["violations"].append(
                "abilityRow %s names no listed row of %s; give one listed rowRef as abilityRow: %s"
                % (json_ref(proposal.get("abilityRow")), actor_creature.get("name"),
                   json_ref_list(row_refs(actor_sheet, actor_creature.get("combatantId"), ROW_FAMILIES))))
            return resolution
        stated_entry = listed if is_save_row(listed) else None
    if stated_entry is not None and _recharge_spent(actor_creature, stated_entry.get("name")):
        resolution["violations"].append(
            "%s is recharging for %s (it returns on a d6 at the start of its turn); choose another action"
            % (stated_entry.get("name"), actor_creature.get("name")))
        return resolution
    if stated_entry is not None:
        stated_save = _stated_save_spec(stated_entry)
        stated_dice, stated_conditions, stated_rounds = _stated_on_fail(stated_entry)
    if stated_entry is not None and stated_save is not None and stated_conditions:
        effects = list(effects)
        for entry in targets:
            target_id = entry.get("combatantId") if isinstance(entry, dict) else None
            target = combatant_by_id(encounter, target_id) if target_id else None
            if target is None:
                continue
            sheet_backed = target.get("type") in ("player", "npc")
            covered = False
            for op in effects:
                if not isinstance(op, dict) or op.get("op") != "add":
                    continue
                same_target = (
                    op.get("combatantId") == target_id
                    or (sheet_backed and op.get("owner") == target.get("name"))
                )
                listed = [
                    str(name).strip().lower()
                    for name in ((op.get("effect") or {}).get("conditions") or [])
                    if isinstance(name, str)
                ]
                if same_target and all(name in listed for name in stated_conditions):
                    covered = True
                    break
            if covered:
                continue
            effect = {
                "name": str(stated_entry.get("name") or "").strip(),
                "description": str(
                    stated_entry.get("description") or stated_entry.get("name") or ""
                ).strip(),
                "modifiers": [],
                "conditions": list(stated_conditions),
                "incapacitates": False,
            }
            if stated_rounds:
                effect["roundsRemaining"] = stated_rounds
                effect["tickTrigger"] = "end_of_round"
            else:
                effect["durationKind"] = "encounter"
            op = {"op": "add", "applyOn": "failedSave", "effect": effect}
            if sheet_backed:
                op["owner"] = target.get("name")
            else:
                op["combatantId"] = target_id
            effects.append(op)
            event.setdefault("normalizations", []).append({
                "kind": "statBlockConditions",
                "ability": stated_entry.get("name"),
                "combatantId": target_id,
                "conditions": list(stated_conditions),
            })

    # Playtest round 2: a companion "cast" Cure Wounds it does not know and
    # paid with the player's slot. Slots and feature uses belong to the actor
    # that spends them, and a sheet with no spellcasting cannot cast unless an
    # item or feature of its own pays for it.
    actor = combatant_by_id(encounter, proposal.get("actorId")) or {}
    actor_name = actor.get("name")
    actor_sheet = (characters or {}).get(actor_name) if actor_name else None
    for record in resources:
        if (isinstance(record, dict) and record.get("kind") in PERSONAL_RESOURCE_KINDS
                and isinstance(record.get("owner"), str) and record.get("owner") != actor_name
                and record.get("owner") in (characters or {})):
            try:
                spends = int(record.get("delta")) < 0
            except (TypeError, ValueError):
                spends = False
            if spends:
                resolution["violations"].append(
                    "%s cannot spend %s's %s %s: an actor spends only its own slots "
                    "and feature uses" % (actor_name, record.get("owner"), record.get("kind"), record.get("name")))
    if (proposal.get("action") == "cast" and actor.get("type") in ("player", "npc")
            and isinstance(actor_sheet, dict) and not _sheet_can_cast(actor_sheet)
            and not any(isinstance(record, dict) and record.get("owner") == actor_name
                        and record.get("kind") in ("item", "charges", "featureUse")
                        for record in resources)):
        resolution["violations"].append(
            "%s has no spells or spell slots on their sheet and cannot cast; choose an "
            "action from their own attacks, features or items" % actor_name)
    if isinstance(actor_sheet, dict):
        # #855 F4-Q3 A: the own slot spent sets the spell's level.
        from core.ai import srd_roll_contracts as _contracts
        mismatch = (_contracts.slot_level_mismatch(proposal, actor_name, actor_sheet)
                    or _contracts.slot_below_spell_level(proposal, actor_name))
        if mismatch:
            resolution["violations"].append(mismatch)

    # Resources: validate owner/kind/name, reject overspend, and record
    # absolute before/after so a crash-replay of this event is idempotent.
    resource_identities = set()
    for record in resources:
        if not isinstance(record, dict):
            resolution["violations"].append("non-object resource record dropped")
            continue
        owner, kind, name = record.get("owner"), record.get("kind"), record.get("name")
        if not all(
            isinstance(value, str) and bool(value)
            for value in (owner, kind, name)
        ):
            resolution["violations"].append(
                "resource owner, kind, and name must be nonempty strings"
            )
            continue
        identity = (owner, kind, name)
        if identity in resource_identities:
            resolution["violations"].append(
                "duplicate resource record rejected: %r/%r/%r"
                % (owner, kind, name)
            )
            continue
        resource_identities.add(identity)
        sheet = (characters or {}).get(owner)
        try:
            delta = int(record.get("delta"))
        except (TypeError, ValueError):
            resolution["violations"].append(
                "non-integer resource delta for %r dropped" % owner)
            continue
        if kind == "item" and isinstance(sheet, dict) and _charged_row(sheet, name) is not None:
            # H3: a wand, staff or rod is one unit whose charges are spent;
            # lowering its quantity would destroy it.
            resolution["violations"].append(
                "%s is a charged item: declare kind 'charges' with the count its use costs, never kind 'item'" % name)
            continue
        snapshot = _resource_snapshot(sheet, kind, name) if isinstance(sheet, dict) else None
        if snapshot is None:
            resolution["violations"].append(
                "unresolvable resource %r/%r/%r dropped" % (owner, kind, name))
            continue
        before, cap = snapshot
        if kind == "charges":
            # H3: no arithmetic check here; the sheet's stored count can be
            # below the real one (a dawn since its last write) and only the
            # engine knows. Its answer is the record.
            record = {"owner": owner, "kind": kind, "name": name, "delta": delta,
                      "before": before, "after": before}
            answer, fact = _engine_charges(encounter, sheet, owner, name, delta, event_id, record)
            if answer is not True:
                resolution["violations"].append(answer)
                if fact is not None:
                    # H3b: every refusal of a use the item could not pay for
                    # (by exclusion: only a positive or zero delta is a
                    # model mistake here; an unknown item or owner never
                    # reaches this branch). For the player's own actor this
                    # pauses for the player's choice (core/combat/pipeline.py).
                    resolution.setdefault("chargeRefusals", []).append(
                        {"owner": owner, "name": name, "reason": answer, "fact": fact})
                continue
            event["resources"].append(record)
            continue
        after = before + delta
        if after < 0:
            resolution["violations"].append(
                "overspend rejected: %s %s %s (%d%+d)" % (owner, kind, name, before, delta))
            if kind in PLAYER_ASK_KINDS:
                # #671, #968: typed, so a player's refused spend can ask the player.
                resolution.setdefault("resourceRefusals", []).append(
                    {"owner": owner, "kind": kind, "name": name, "before": before, "max": cap,
                     "need": -delta, "actor": actor_name})
            continue
        if cap is not None:
            after = min(after, cap)
        record = {"owner": owner, "kind": kind, "name": name,
                  "delta": delta, "before": before, "after": after}
        if kind == "ammunition":
            # AM: the engine spends or adds the declared amount; a short stock
            # is the same violation as the arithmetic check above, so T096
            # corrects itself; engine unavailable keeps the arithmetic.
            answer = _engine_ammunition(sheet, name, delta, record)
            if isinstance(answer, str):
                resolution["violations"].append(
                    "overspend rejected: %s %s %s (%s)" % (owner, kind, name, answer))
                # #968: the engine holds less than the sheet shows; typed as above.
                resolution.setdefault("resourceRefusals", []).append(
                    {"owner": owner, "kind": kind, "name": name, "before": before, "max": cap,
                     "need": -delta, "actor": actor_name, "engine": answer})
                continue
            if answer is not True:
                record["engine"] = False
        event["resources"].append(record)

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
        if owner is not None and not isinstance(owner, str):
            resolution["violations"].append("effect owner must be a string")
            continue
        if combatant_id is not None and not isinstance(combatant_id, str):
            resolution["violations"].append(
                "effect combatantId must be a string"
            )
            continue
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
                violation = "sheet-backed effect target %r must use owner" % combatant_id
                if op["op"] == "remove":
                    # #725: a remove refused for its destination, typed for
                    # the correction (an add keeps today's violation).
                    _refuse_removal(resolution, event, {
                        "reason": "mustUseOwner", "reference": _removal_reference(op),
                        "combatantId": combatant_id, "owner": target.get("name"),
                    }, violation, drop_refused_removals)
                else:
                    resolution["violations"].append(violation)
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
            if effect_incapacitates(op["effect"]):
                # Paralyzed, stunned, petrified and unconscious include
                # Incapacitated (SRD): the journal records the derived flag so
                # a replay and the turn order agree whatever the model wrote.
                op["effect"]["incapacitates"] = True
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
            effect_target = (
                combatant_by_id(encounter, combatant_id)
                if combatant_id
                else next(
                    (
                        creature
                        for creature in encounter.get("creatures", [])
                        if creature.get("name") == owner
                        and creature.get("type") in ("player", "npc")
                    ),
                    None,
                )
            )
            grants_current_hp = any(
                operation.get("stat") == "hitPoints"
                and operation.get("delta", 0) > 0
                for operation in op["effect"].get("onApply", [])
            )
            if (
                grants_current_hp
                and effect_target
                and normalize_status(effect_target.get("status")) == NONPLAYER_DEAD
            ):
                resolution["violations"].append(
                    "ordinary healing effect cannot restore dead target %s"
                    % effect_target["combatantId"]
                )
                continue
            effect_problems = validate_effect(
                op["effect"],
                require_managed=True,
            )
            effect_problems.extend(
                problem
                for problem in (
                    _combat_modifier_problem(modifier)
                    for modifier in op["effect"].get("modifiers", [])
                )
                if problem
            )
            if effect_problems:
                resolution["violations"].append(
                    "effect contract rejected: %s" % "; ".join(effect_problems)
                )
                continue
        else:
            nested_effect = op.get("effect") if isinstance(op.get("effect"), dict) else {}
            supplied_effect_id = op.get("effectId") or nested_effect.get("effectId")
            supplied_name = op.get("name") or nested_effect.get("name")
            supplied_condition = op.get("condition")
            if not supplied_effect_id and not supplied_name and not supplied_condition:
                resolution["violations"].append(
                    "effect remove requires a name, effectId or condition"
                )
                continue

            if owner:
                current_effects = (
                    ((characters or {}).get(owner) or {}).get("temporaryEffects", [])
                    or []
                )
            else:
                current_effects = (
                    (combatant_by_id(encounter, combatant_id) or {}).get(
                        "activeEffects", []
                    )
                    or []
                )
            if not isinstance(current_effects, list):
                current_effects = []

            id_matches = [
                effect
                for effect in current_effects
                if isinstance(effect, dict)
                and supplied_effect_id
                and effect.get("effectId") == supplied_effect_id
            ]
            matched_by_id_in_name = False
            if supplied_effect_id:
                matches = id_matches
            else:
                matches = [
                    effect
                    for effect in current_effects
                    if isinstance(effect, dict)
                    and effect.get("name") == supplied_name
                ]
                if not matches:
                    matches = [
                        effect
                        for effect in current_effects
                        if isinstance(effect, dict)
                        and effect.get("effectId") == supplied_name
                    ]
                    matched_by_id_in_name = bool(matches)

            # CSb: a remove that names a condition the target states (the
            # sheet's list, or a monster's conditions) and no effect ends
            # that condition, as removeEffect does outside a fight. Typed
            # values compared against the stated list, never prose.
            stated_condition = None
            if not matches:
                stated_condition = _stated_condition_reference(
                    characters, encounter, owner, combatant_id,
                    supplied_condition, supplied_effect_id, supplied_name,
                )
            if stated_condition == "unconscious":
                resolution["violations"].append(
                    "unconscious is the rules engine's verdict at 0 hit points; it ends with healing, not a remove"
                )
                continue
            if stated_condition:
                op.pop("effect", None)
                op.pop("effectId", None)
                op.pop("name", None)
                op["condition"] = stated_condition
                if supplied_condition != stated_condition:
                    normalization = {
                        "kind": "canonicalizeConditionRemovalReference",
                        "suppliedValue": supplied_effect_id or supplied_name or supplied_condition,
                        "condition": stated_condition,
                    }
                    normalization["owner" if owner else "combatantId"] = owner or combatant_id
                    event.setdefault("normalizations", []).append(normalization)
            elif len(matches) != 1:
                label = supplied_effect_id or supplied_name or supplied_condition
                reason = "ambiguous" if len(matches) > 1 else "unknown"
                violation = "%s effect removal reference %r" % (reason, label)
                if reason == "unknown":
                    # #725: nothing by that reference to remove; the target's
                    # current effects are named for the correction.
                    refusal = {"reason": "unknown", "reference": label, "currentEffects": [
                        effect.get("name") or effect.get("effectId")
                        for effect in current_effects if isinstance(effect, dict)]}
                    refusal["owner" if owner else "combatantId"] = owner or combatant_id
                    _refuse_removal(resolution, event, refusal, violation, drop_refused_removals)
                else:
                    resolution["violations"].append(violation)
                continue

            matched_effect = matches[0] if matches else {}
            matched_effect_id = matched_effect.get("effectId")
            matched_name = matched_effect.get("name")
            if not stated_condition:
                op.pop("effect", None)
                if matched_effect_id:
                    op["effectId"] = matched_effect_id
                else:
                    op.pop("effectId", None)
                if matched_name:
                    op["name"] = matched_name
                else:
                    op.pop("name", None)
            if matched_by_id_in_name:
                normalization = {
                    "kind": "canonicalizeEffectRemovalReference",
                    "suppliedField": "name",
                    "suppliedValue": supplied_name,
                    "effectId": matched_effect_id,
                    "name": matched_name,
                }
                normalization["owner" if owner else "combatantId"] = (
                    owner or combatant_id
                )
                event.setdefault("normalizations", []).append(normalization)
        apply_on = op.get("applyOn", "always")
        if apply_on == "hit" and attack_hits is None:
            resolution["violations"].append(
                "effect applyOn 'hit' is only for a spell attack code scores; use always, failedSave, or successfulSave"
            )
            continue
        if apply_on not in ("always", "failedSave", "successfulSave", "hit"):
            resolution["violations"].append(
                "effect applyOn must be always, failedSave, or successfulSave"
            )
            continue
        op["_applyOnExplicit"] = "applyOn" in op
        op["applyOn"] = apply_on
        normalized_effects.append(op)

    # One-time effect resource changes and target HP deltas are alternative
    # representations of the same mechanic. An exact Aid-like duplicate can
    # be canonicalized without another provider call: the effect operation is
    # retained because it runs after the maximum-HP modifier, while target
    # hpDelta becomes zero. Every ambiguous/mismatched shape still rejects.
    save_spec = (
        proposal.get("save")
        if isinstance(proposal.get("save"), dict)
        else None
    )
    if stated_save is not None:
        supplied = {
            "type": str((save_spec or {}).get("type") or "").strip().lower(),
            "dc": (save_spec or {}).get("dc"),
            "halfOnSave": bool((save_spec or {}).get("halfOnSave")),
        }
        if save_spec is None or supplied != stated_save:
            event.setdefault("normalizations", []).append({
                "kind": "statBlockSave",
                "ability": stated_entry.get("name"),
                "supplied": deepcopy(save_spec),
                "applied": dict(stated_save),
            })
        save_spec = dict(stated_save)
    # #703: a spell with a typed save record (data/srd_spell_saves.json) takes
    # the save ability and the effect of a success from the record, never from
    # the model's save object, and a party caster's DC from its sheet. The
    # record requires the save even when the intent omits it. The rules engine
    # scores each target's save below. A spell without a record keeps the
    # model-declared save.
    spell_save = None
    if stated_save is None:
        spell_save = _spell_save_rule(encounter, characters, proposal, save_spec, targets, event)
        if spell_save is not None:
            save_spec = dict(spell_save["spec"])
    # Plan r2 item 9: a save the model declares (no stat-block or spell
    # record) names one of the six abilities; any other type is corrected,
    # never scored against a default score.
    if save_spec and stated_save is None and spell_save is None and save_ability(save_spec.get("type")) is None:
        resolution["violations"].append(
            "save type %r is not a saving throw; use one of Strength, Dexterity, Constitution, "
            "Intelligence, Wisdom or Charisma" % (save_spec.get("type"),))
    target_entries = {
        entry.get("combatantId"): entry
        for entry in targets
        if isinstance(entry, dict) and entry.get("combatantId")
    }
    overlapping_effects = {}
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
        target_entry = target_entries.get(target_id)
        if not isinstance(target_entry, dict):
            continue
        if type(target_entry.get("hpDelta")) is int and target_entry["hpDelta"] != 0:
            overlapping_effects.setdefault(target_id, []).append(op)

    canonical_records = []
    can_canonicalize = bool(overlapping_effects) and save_spec is None
    for target_id, target_entry in target_entries.items():
        effect_ops = overlapping_effects.get(target_id)
        if not effect_ops:
            continue
        if len(effect_ops) != 1:
            can_canonicalize = False
            continue
        op = effect_ops[0]
        effect = op.get("effect") or {}
        on_apply = effect.get("onApply", []) or []
        on_remove = effect.get("onRemove", []) or []
        modifiers = effect.get("modifiers", []) or []
        maximum_modifiers = [
            modifier
            for modifier in modifiers
            if isinstance(modifier, dict)
            and modifier.get("stat") == "maxHitPoints"
        ]
        target_delta = target_entry.get("hpDelta")
        exact = (
            op.get("applyOn") == "always"
            and len(on_apply) == 1
            and on_apply[0].get("stat") == "hitPoints"
            and type(on_apply[0].get("delta")) is int
            and on_apply[0]["delta"] > 0
            and type(target_delta) is int
            and target_delta == on_apply[0]["delta"]
            and len(modifiers) == 1
            and len(maximum_modifiers) == 1
            and maximum_modifiers[0].get("value") == target_delta
            and not on_remove
        )
        if not exact:
            can_canonicalize = False
            continue
        canonical_records.append((target_id, target_entry, target_delta))

    canonical_wake_targets = set()
    if overlapping_effects and can_canonicalize:
        for target_id, target_entry, delta in canonical_records:
            target_entry["hpDelta"] = 0
            target = combatant_by_id(encounter, target_id)
            if (
                target is not None
                and normalize_status(target.get("status")) == PLAYER_UNCONSCIOUS
            ):
                canonical_wake_targets.add(target_id)
            event.setdefault("normalizations", []).append(
                {
                    "kind": "deduplicateEffectHitPoints",
                    "combatantId": target_id,
                    "delta": delta,
                    "kept": "effect.onApply",
                    "removed": "target.hpDelta",
                }
            )
    else:
        for target_id in overlapping_effects:
            resolution["violations"].append(
                "effect onApply and target hpDelta duplicate one HP change"
            )

    if save_spec and not targets:
        resolution["violations"].append(
            "a declared save requires at least one target (use hpDelta 0 for control)"
        )

    heal_feature, heal_pool, heal_formula, heal_refusal = _feature_heal_selection(
        encounter, characters, proposal, targets)
    if heal_formula is not None and heal_formula["target"] == "other":
        # F1: Divine Spark heals exactly one creature, never its caster.
        healed_ids = [entry.get("combatantId") for entry in targets if declared_heal(entry) > 0]
        if healed_ids and (len(healed_ids) != 1 or healed_ids[0] == proposal.get("actorId")):
            heal_refusal = {"pool": spent_heal_pool(encounter, proposal)[1][0].get("name"),
                            "options": [], "ability": heal_formula["feature"], "target": "other"}
            heal_formula = None
    formula_heal_declared = False
    heal_rows = []
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
        if hp_delta > 0 and normalize_status(target.get("status")) == NONPLAYER_DEAD:
            resolution["violations"].append(
                "ordinary healing cannot restore dead target %s"
                % target["combatantId"]
            )
            continue
        if heal_refusal is not None and hp_delta > 0:
            # F1: the spent pool pays for no heal named here; nothing is healed.
            continue
        feature_heal = None
        if (heal_formula is not None and hp_delta > 0
                and (target["combatantId"] == proposal.get("actorId")) == (heal_formula["target"] == "self")):
            formula_heal_declared = True
            # #881: code does the arithmetic, the typed die face (rolled) plus
            # the class level; with no rolled the declared heal is held to the
            # formula's range (D-881-1 a). No violation, no extra pass.
            low, high = heal_formula["count"], heal_formula["count"] * heal_formula["sides"]
            bonus = heal_formula["bonus"]
            face = entry.get("rolled") if type(entry.get("rolled")) is int else None
            applied = (min(max(face, low), high) + bonus if face is not None
                       else min(max(hp_delta, low + bonus), high + bonus))
            if applied != hp_delta:
                event.setdefault("normalizations", []).append({
                    "kind": "featureHealFormula", "ability": heal_formula["feature"],
                    "combatantId": target["combatantId"], "rolled": face, "bonus": bonus,
                    "supplied": hp_delta, "allowed": applied})
                feature_heal = {"supplied": hp_delta, "allowed": applied, "formula": "%dd%d (%s) + %s" % (
                    heal_formula["count"], heal_formula["sides"], "?" if face is None else face,
                    heal_formula["label"])}
                hp_delta = applied
        if heal_pool is not None and hp_delta >= 0:
            hp_now = int(target.get("currentHitPoints", 0) or 0)
            max_now = _combatant_max_hp(encounter, characters, target)
            # An unreadable maximum keeps only the pool limit (fail forward).
            allowed = (_feature_heal_allowed(hp_now, max_now, heal_pool) if max_now > 0
                       else max(0, min(hp_delta, heal_pool)))
            heal_row = {
                "actorId": proposal.get("actorId"), "ability": heal_feature,
                "combatantId": target["combatantId"], "hpBefore": hp_now, "max": max_now, "allowed": allowed, "declared": hp_delta}
            heal_rows.append(heal_row)
            if hp_delta > allowed:
                if not clamp_feature_heals:
                    resolution["violations"].append(
                        "feature heal limit: %s restores at most %d to %s (%d/%d, half %d)"
                        % (heal_feature, allowed, target["combatantId"], hp_now, max_now, max_now // 2))
                    resolution.setdefault("featureHealLimits", []).append(heal_row)
                    continue
                feature_heal = {"supplied": hp_delta, "allowed": allowed}
                event.setdefault("normalizations", []).append({
                    "kind": "featureHeal", "ability": heal_feature,
                    "combatantId": target["combatantId"], "supplied": hp_delta, "allowed": allowed})
                hp_delta = allowed
            heal_pool -= hp_delta
            heal_row["applied"] = hp_delta
        saved = None
        save_line = None
        if stated_dice is not None and hp_delta <= 0:
            # MS-a: the stat block's on-fail dice are rolled from the
            # persisted prerolls (the full failed-save amount; the save
            # verdict below halves or negates it), never by the model.
            count, sides, flat = stated_dice
            rolled = [
                _take_roll(
                    rolls,
                    "d%d" % sides,
                    "damage",
                    actor_id=proposal.get("actorId"),
                    target_id=target.get("combatantId"),
                )
                for _ in range(count)
            ]
            for value in rolled:
                event["rolls"].append({
                    "die": "d%d" % sides, "value": value, "purpose": "damage",
                    "combatantId": target["combatantId"],
                })
            stated_damage = max(0, sum(rolled) + flat)
            if hp_delta != -stated_damage:
                event.setdefault("normalizations", []).append({
                    "kind": "statBlockDamage",
                    "ability": stated_entry.get("name"),
                    "combatantId": target["combatantId"],
                    "supplied": hp_delta,
                    "rolled": -stated_damage,
                })
            hp_delta = -stated_damage
        spell_scored = None
        if spell_save is not None and save_spec and hp_delta <= 0:
            spell_scored = _spell_save_target(encounter, characters, proposal, target, spell_save,
                                              hp_delta, rolls, event)
        if spell_scored is not None:
            saved, hp_delta, save_line = spell_scored
        elif save_spec and hp_delta <= 0:
            # CS: a party target's save is the rules engine's (conditions'
            # roll modes, the sheet's total, the verdict); monsters and an
            # unavailable engine keep the arithmetic below.
            save_sheet = _sheet_backed_target(characters, target)
            player_faces = _player_save_faces(proposal, target)
            save_dc = _player_save_dc(proposal, target, save_spec, player_faces, event)
            engine_save = (
                _engine_save(save_sheet, save_spec.get("type"), save_dc,
                             rolls, proposal.get("actorId"), target.get("combatantId"),
                             player_faces=player_faces)
                if save_sheet is not None else None
            )
            if engine_save is not None:
                from core.nql import checks as nql_checks
                result, faces, added = engine_save
                saved = bool(result.success)
                save_line = nql_checks.describe(result)
                event["rolls"].append({
                    "die": "d20", "value": result.kept if result.kept is not None else 0,
                    "purpose": "save", "combatantId": target["combatantId"],
                    "bonus": result.bonus, "success": saved, "engine": True,
                    "faces": faces, "kept": result.kept, "mode": result.mode,
                    "sources": result.sources, "total": result.total, "margin": result.margin,
                    **({"added": added} if added else {}),
                    **({"rolledBy": "player"} if player_faces else {}),
                })
                event.setdefault("engineChecks", []).append(save_line)
            else:
                die = player_faces[0] if player_faces else _take_roll(
                    rolls,
                    "d20",
                    "save",
                    actor_id=proposal.get("actorId"),
                    target_id=target.get("combatantId"),
                    ability=save_spec.get("type"),
                )
                bonus = _save_bonus(encounter, characters, target, save_spec.get("type"))
                added = _save_added_dice(encounter, characters, target, save_spec.get("type"), rolls)
                saved = die + bonus + sum(roll["value"] for roll in added) >= int(save_dc)
                record = {"die": "d20", "value": die, "purpose": "save",
                          "combatantId": target["combatantId"],
                          "bonus": bonus, "success": saved}
                if added:
                    record["added"] = added
                if player_faces:
                    record["rolledBy"] = "player"
                if save_sheet is not None:
                    record["engine"] = False
                event["rolls"].append(record)
            if saved and hp_delta < 0:
                # SRD division rounds damage down. The stored delta is
                # negative, so Python's ``//`` would round away from zero
                # (-7 // 2 == -4) and accidentally deal one extra damage.
                hp_delta = (
                    -((-hp_delta) // 2)
                    if save_spec.get("halfOnSave")
                    else 0
                )
        hp_before = int(target.get("currentHitPoints", 0) or 0)
        ceiling = _combatant_max_hp(encounter, characters, target) or hp_before
        # CH: the rules engine applies a party target's change (temporary hit
        # points first, clamps, the concentration save); the arithmetic below
        # stays for monsters and as the fallback when the engine is unavailable.
        target_sheet = _sheet_backed_target(characters, target)
        working = None
        temp_before = None
        engine_used = None
        focus = {}
        if save_line:
            # The save line rides with the target record like the concentration
            # lines (CC), so the narrator and the log state the engine's verdict.
            focus["engineChecks"] = [save_line]
        if target_sheet is not None:
            working = deepcopy(target_sheet)
            working["hitPoints"] = hp_before
            temp_before = _temp_hp(working)
            applied = _engine_hit_points(working, hp_delta, event, focus) if hp_delta else None
            if applied is not None:
                working = applied
                engine_used = True
            elif hp_delta:
                engine_used = False
        if engine_used:
            hp_after = int(working["hitPoints"])
        else:
            hp_after = max(0, min(hp_before + hp_delta, ceiling))
            if working is not None:
                working["hitPoints"] = hp_after
        status_after = normalize_status(target.get("status"))
        if hp_after == 0 and hp_delta < 0:
            # D-242-1: same rule as the attack path above.
            status_after = (PLAYER_UNCONSCIOUS if is_party_member(target)
                            else NONPLAYER_DEAD)
        elif target["combatantId"] in canonical_wake_targets:
            status_after = "alive"
        elif hp_after > 0 and status_after == PLAYER_UNCONSCIOUS and hp_delta > 0:
            status_after = "alive"
        record = {"combatantId": target["combatantId"], "hpBefore": hp_before,
                  "hpAfter": hp_after, "statusAfter": status_after}
        if feature_heal is not None:
            # #669: the narrator states the clamped heal, never the supplied one.
            record["featureHeal"] = feature_heal
        if saved is not None:
            record["saved"] = saved
        if working is not None:
            if temp_before is not None:
                record["tempHpBefore"] = temp_before
            if _temp_hp(working) is not None and (temp_before is not None or _temp_hp(working)):
                record["tempHpAfter"] = _temp_hp(working)
            if engine_used is not None:
                record["engine"] = engine_used
            record.update(focus)
        elif focus:
            record.update(focus)
        event["outcome"]["targets"].append(record)
        resolution["creatureDeltas"][target["combatantId"]] = {
            "currentHitPoints": hp_after, "status": status_after}
        if working is not None:
            resolution["charDeltas"][target["name"]] = _sheet_delta(
                working, hp_after, status_after, target, temp_before)

    if heal_formula is not None and heal_formula["target"] == "self" and not formula_heal_declared:
        # #939 (#352 shape): the actor spends a formula heal but declares no
        # heal on itself, so the use would be spent and nothing restored.
        resolution["violations"].append(
            "feature heal: %s spends a use but declares no heal on %s; declare it as a target on %s with "
            "hpDelta and the d%d face in rolled, or spend nothing"
            % (heal_formula["feature"], proposal.get("actorId"), proposal.get("actorId"), heal_formula["sides"]))
    if heal_refusal is not None:
        _feature_heal_refused(event, resolution, encounter, proposal, heal_refusal, targets,
                              clamp_feature_heals)
    if heal_pool is not None and not resolution.get("featureHealLimits"):
        _feature_heal_unspent(event, resolution, encounter, proposal, heal_feature, heal_rows,
                              clamp_feature_heals)

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
        if apply_on == "hit":
            # #672: the one target of the code-scored spell attack.
            hit_target_id = next(iter(attack_hits))
            if not attack_hits[hit_target_id]:
                continue
            op["hitTargetId"] = hit_target_id
        elif apply_on != "always":
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
    if stated_entry is not None and not resolution["violations"]:
        _spend_recharge(resolution, event, actor_creature, stated_entry)
    _stage_last_weapon_rows(encounter, characters, resolution)
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
    bonus = event.get("bonusAction") if isinstance(event.get("bonusAction"), dict) else {}
    # R2: the bonus action's targets first; the Action's own records (taken
    # after it) replace them for the same combatant. R3: an Off-hand Attack
    # (order "afterAction") came after the Action, so its records come last.
    bonus_records = [(record, False) for record in (bonus.get("outcome") or {}).get("targets") or []]
    action_records = [(record, True) for record in (event.get("outcome") or {}).get("targets", []) or []]
    ordered = (action_records + bonus_records if bonus.get("order") == "afterAction"
               else bonus_records + action_records)
    for record, from_action in ordered:
        combatant_id = record.get("combatantId")
        resolution["creatureDeltas"][combatant_id] = {
            "currentHitPoints": int(record["hpAfter"]),
            "status": record["statusAfter"],
        }
        creature = combatant_by_id(encounter, combatant_id)
        if (creature is not None and creature.get("type") in ("player", "npc")
                and creature.get("name") in (characters or {})):
            if from_action and (event.get("outcome") or {}).get("kind") in ("flee", "yield"):
                # Same as the live path (#466): no sheet delta for leaving.
                continue
            delta = {"hitPoints": int(record["hpAfter"])}
            if type(record.get("tempHpAfter")) is int:
                delta["temporaryHitPoints"] = record["tempHpAfter"]
            if record["statusAfter"] != normalize_status(creature.get("status")):
                delta["status"] = record["statusAfter"]
            resolution["charDeltas"][creature["name"]] = delta
    for spent in event.get("recharge") or []:
        actor = combatant_by_id(encounter, spent.get("actorId"))
        if actor is None or not spent.get("name"):
            continue
        current = deepcopy(actor.get("recharge")) if isinstance(actor.get("recharge"), dict) else {}
        current[spent["name"]] = {
            key: spent[key] for key in ("state", "min", "max", "rechargesOn") if key in spent
        }
        resolution["creatureDeltas"].setdefault(actor["combatantId"], {})["recharge"] = current
    ended = event.get("dodgeEnded")
    if isinstance(ended, dict) and combatant_by_id(encounter, ended.get("actorId")) is not None:
        resolution["creatureDeltas"].setdefault(ended["actorId"], {})["dodging"] = None
    dodge = event.get("dodge")
    if isinstance(dodge, dict) and combatant_by_id(encounter, dodge.get("actorId")) is not None:
        resolution["creatureDeltas"].setdefault(dodge["actorId"], {})["dodging"] = {
            "sinceEventId": event["eventId"]
        }
    _stage_last_weapon_rows(encounter, characters, resolution)
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
    # An encounter creature record is not a character sheet: no engine world.
    updated = apply_effect_ops(raw, [operation], engine=False)
    # The effect's SRD conditions ride on the creature record the same way
    # a sheet's condition_affected does (CSb); T096 reads them from there.
    creature["conditions"] = sync_condition_states(
        creature.get("conditions"), effects, updated.get("temporaryEffects", [])
    )
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
            effect_incapacitates(effect) for effect in effects
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


def _apply_charges_after(sheet, item, resource, after_state):
    """Write one journaled charge state onto the row and keep the sheet's
    chargeUses receipt in step with the out-of-combat path (H1): the same
    request is never recorded twice (a crash between the sheet write and
    the applied-event ledger replays this apply)."""
    charges = item.get("charges") if isinstance(item.get("charges"), dict) else {}
    charges.pop("gap", None)
    charges["current"] = int(after_state["current"])
    if type(after_state.get("max")) is int:
        charges["max"] = after_state["max"]
    for key in ("asOf", "seed", "nextRecharge"):
        if key in after_state:
            charges[key] = deepcopy(after_state[key])
        else:
            charges.pop(key, None)
    item["charges"] = charges
    exhausted = resource.get("exhausted") if isinstance(resource.get("exhausted"), dict) else None
    if after_state.get("quantity") == 0 or (exhausted and exhausted.get("outcome") == "destroyed"):
        # The unit is gone: unworn, quantity 0, no boundary; the row and its
        # count stay (H2b-3).
        item["quantity"] = 0
        item["equipped"] = False
        charges.pop("nextRecharge", None)
    request = resource.get("request")
    receipts = [r for r in sheet.get("chargeUses") or [] if isinstance(r, dict)]
    if request and not any(r.get("request") == request for r in receipts):
        receipt = {"request": request, "nqlId": resource.get("nqlId"), "item": item.get("item_name"),
                   "requested": -int(resource.get("delta") or 0), "before": resource.get("before"),
                   "after": charges["current"], "message": resource.get("message")}
        if exhausted:
            receipt["exhausted"] = deepcopy(exhausted)
        receipts.append(receipt)
        sheet["chargeUses"] = receipts[-20:]  # item_charges.RECEIPTS_KEPT


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
        if "resolution" in delta:
            creature["resolution"] = delta["resolution"]
        if "recharge" in delta:
            # MS-b: the full record replaces the creature's (journal authority)
            if delta["recharge"]:
                creature["recharge"] = deepcopy(delta["recharge"])
            else:
                creature.pop("recharge", None)
        if "dodging" in delta:
            # Item 2: a record marks a Dodge; None ends it (the journal is the authority)
            if isinstance(delta["dodging"], dict):
                creature["dodging"] = deepcopy(delta["dodging"])
            else:
                creature.pop("dodging", None)
        if isinstance(delta.get("lastWeaponRows"), dict):
            # #851: the actor's last swung weapon row per kind (journal authority)
            creature["lastWeaponRows"] = deepcopy(delta["lastWeaponRows"])

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
        if type(delta.get("temporaryHitPoints")) is int:
            sheet["temporaryHitPoints"] = max(0, delta["temporaryHitPoints"])
        if "status" in delta:
            sheet["status"] = delta["status"]

    # NUM-B: a weapon drawn after a swing (BQ1); the record holds the absolute value.
    hands = event.get("hands")
    draw = hands.get("draw") if isinstance(hands, dict) else None
    if isinstance(draw, dict):
        sheet = new_characters.get(hands.get("owner"))
        rows = sheet.get("equipment") if isinstance(sheet, dict) else None
        index = draw.get("index")
        if (isinstance(rows, list) and type(index) is int and 0 <= index < len(rows)
                and isinstance(rows[index], dict) and rows[index].get("item_name") == draw.get("item_name")):
            rows[index]["equipped"] = draw.get("equippedAfter") is True

    bonus = event.get("bonusAction") if isinstance(event.get("bonusAction"), dict) else {}
    for resource in list(bonus.get("resources") or []) + list(event.get("resources", []) or []):
        # R2: the bonus action's spends come first (its absolute 'after' values
        # are already on the sheet when the live path applied it).
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
                    # AM: the engine's pending count rides on the journal; an
                    # older record without it leaves the row's count alone.
                    if type(resource.get("recoverableAfter")) is int:
                        if resource["recoverableAfter"] > 0:
                            item["recoverable"] = resource["recoverableAfter"]
                        else:
                            item.pop("recoverable", None)
                    break
        elif resource["kind"] == "spellSlot":
            level = ((sheet.get("spellcasting") or {}).get("spellSlots") or {}).get(
                resource.get("name"))
            if isinstance(level, dict):
                cap = int(level.get("max", 0) or 0)
                level["current"] = min(cap, setter(int(level.get("current", 0) or 0)))
        elif resource["kind"] == "featureUse":
            for feature in list(sheet.get("classFeatures", []) or []) + list(sheet.get("feats", []) or []):
                if isinstance(feature, dict) and feature.get("name") == resource.get("name"):
                    usage = feature.get("usage")
                    if isinstance(usage, dict):
                        cap = int(usage.get("max", 0) or 0)
                        usage["current"] = min(cap, setter(int(usage.get("current", 0) or 0)))
                    break
        elif resource["kind"] == "item":
            if isinstance(resource.get("item"), dict):
                from core.nql.item_use import resolve_row
                found = resolve_row(sheet, resource["item"])
                if found is not None:
                    index, item = found
                    # Keep zero-stock rows, as the existing item path does (#1121/#1197).
                    item["quantity"] = setter(item["quantity"])
                continue
            for item in sheet.get("equipment", []):
                if isinstance(item, dict) and item.get("item_name") == resource.get("name"):
                    item["quantity"] = setter(int(item.get("quantity", 0) or 0))
                    break
        elif resource["kind"] == "charges":
            # H3: the journaled engine state is written whole (a field the
            # record omits is removed, the H2 store_view rule); a record
            # without it applies nothing, there is no delta fallback.
            after_state = resource.get("chargesAfter")
            if isinstance(after_state, dict) and type(after_state.get("current")) is int:
                for item in sheet.get("equipment", []):
                    if isinstance(item, dict) and item.get("item_name") == resource.get("name"):
                        _apply_charges_after(sheet, item, resource, after_state)
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
            _record_fight_cast(new_encounter, new_characters, event, op)
        if op.get("op") == "remove" and op.get("condition"):
            _end_stated_condition(new_encounter, new_characters, op)
            continue
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
        downed = _sheet_backed_target(new_characters, combatant_by_id(new_encounter, source_id))
        if downed is not None:
            from core.managers.concentration_runtime import clear_record
            clear_record(downed)
    # CSb: a caster held, stunned or petrified by a fight's effect cannot
    # concentrate (SRD); the spell ends everywhere the way it does at 0 hit
    # points. A function of the sheets' conditions, so a replay agrees.
    for creature in new_encounter.get("creatures", []) or []:
        if not isinstance(creature, dict) or not creature.get("combatantId"):
            continue
        caster = _sheet_backed_target(new_characters, creature)
        if caster is None or _concentration_record(caster) is None:
            continue
        from core.nql import stats as nql_stats
        if nql_stats.concentration_blocked(caster):
            _drop_concentration(new_encounter, new_characters, creature["combatantId"])
            from core.managers.concentration_runtime import clear_record
            clear_record(_sheet_backed_target(new_characters, creature))
    # CC: a failed engine save (journaled on the target record) ends the spell
    # everywhere and clears the caster's record; replay reads the same record.
    _apply_concentration_verdicts(new_encounter, new_characters, event)

    # Character files are written before the encounter journal receipt. A
    # replay can therefore begin with an already-applied effect/resource file.
    # These absolute post-event values make one-time effect HP operations
    # converge instead of being lost or applied twice after that partial write.
    for name, snapshot in (event.get("characterStateAfter") or {}).items():
        sheet = new_characters.get(name)
        if not isinstance(sheet, dict) or not isinstance(snapshot, dict):
            raise ValueError("Character replay snapshot is not durably addressable")
        if "hitPoints" in snapshot:
            ceiling = int(
                effective_sheet(sheet).get(
                    "maxHitPoints",
                    snapshot["hitPoints"],
                )
                or 0
            )
            sheet["hitPoints"] = max(
                0,
                min(int(snapshot["hitPoints"]), ceiling),
            )
        if type(snapshot.get("temporaryHitPoints")) is int:
            sheet["temporaryHitPoints"] = max(0, snapshot["temporaryHitPoints"])
        if "status" in snapshot:
            sheet["status"] = snapshot["status"]
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
        if (
            isinstance(hp, int)
            and hp > 0
            and normalize_status(creature.get("status")) == NONPLAYER_DEAD
        ):
            violations.append("%s has positive HP but status dead" % cid)
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
