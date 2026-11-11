"""A fight against a sleeping enemy opens with it asleep but seated (#1900).

A hostile npc whose sheet is unconscious above 0 HP (a sleeper) is seated
alive at build with the typed marker ``sleeperWake``. After activation the
marker becomes a one-round "Asleep" effect on the sheet that states
unconscious and incapacitates. The sleeper wakes when it takes damage or
when round 1 ends; a fight that ends first leaves it awake.

#1894 (D-1894-5, B): a party-side combatant (the player, a companion, a
friendly npc) whose sheet states unconscious above 0 HP with no effect
behind it is seated the same way (``party_sleeper_rows``).

Typed keys and value compares only (AP-7). The wake effect has no
``modifiers`` key, so the rules engine never holds it (core/nql/effects
``pending_effects``) and adding or removing it makes no engine request.
"""

from copy import deepcopy

# Its own name and id namespace, apart from #834's "Surprised" / "surprise-":
# the narrator reads the name of the effect a hit removes.
WAKE_PREFIX = "asleep-"
WAKE_NAME = "Asleep"
WAKE_MARKER = "sleeperWake"
UNCONSCIOUS = "unconscious"


def _names(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def states_unconscious(sheet):
    """Whether the sheet's own condition or condition_affected names unconscious."""
    if not isinstance(sheet, dict):
        return False
    listed = _names(sheet.get("condition")) + _names(sheet.get("condition_affected"))
    return any(name.strip().casefold() == UNCONSCIOUS for name in listed)


def is_sleeper_sheet(sheet):
    """Unconscious above 0 HP: status unconscious, or unconscious stated."""
    from core.managers.combat_state import normalize_status

    if not isinstance(sheet, dict):
        return False
    hp = sheet.get("hitPoints")
    if isinstance(hp, bool) or not isinstance(hp, int) or hp <= 0:
        return False
    return normalize_status(sheet.get("status")) == UNCONSCIOUS or states_unconscious(sheet)


def wake_effect_id(combatant_id):
    return WAKE_PREFIX + str(combatant_id)


def wake_effect(combatant_id, encounter_id):
    """The sheet effect that holds a sleeper until struck or round 1 ends.
    No ``modifiers`` key: the engine never holds it."""
    return {
        "effectId": wake_effect_id(combatant_id),
        "name": WAKE_NAME,
        "description": "Asleep when the fight began: unconscious until it takes damage or round 1 ends.",
        "conditions": [UNCONSCIOUS],
        "incapacitates": True,
        "roundsRemaining": 1,
        "durationKind": "rounds",
        "tickTrigger": "end_of_round",
        "sourceEncounterId": str(encounter_id),
        "authoredBy": "engine",
    }


def is_wake_effect(effect):
    """A wake effect this change wrote: its id prefix, encounter and author,
    and its own shape (name, the one unconscious condition, incapacitating).
    The prefix alone is not enough: a combat add keeps a model-supplied
    effectId and stamps sourceEncounterId, and authoredBy defaults to engine."""
    return (
        isinstance(effect, dict)
        and isinstance(effect.get("effectId"), str)
        and effect["effectId"].startswith(WAKE_PREFIX)
        and isinstance(effect.get("sourceEncounterId"), str)
        and bool(effect["sourceEncounterId"])
        and effect.get("authoredBy") == "engine"
        and effect.get("name") == WAKE_NAME
        and effect.get("conditions") == [UNCONSCIOUS]
        and effect.get("incapacitates") is True
    )


def wake_effect_ids(sheet):
    if not isinstance(sheet, dict):
        return set()
    return {
        effect["effectId"]
        for effect in sheet.get("temporaryEffects") or []
        if is_wake_effect(effect)
    }


def wake_holds(sheet, creature, encounter):
    """C5: the row's wake effect from this encounter holds on a sheet above 0 HP.
    While it does, a sheet status "unconscious" is not copied to the row."""
    if not isinstance(sheet, dict) or not isinstance(creature, dict) or not isinstance(encounter, dict):
        return False
    hp = sheet.get("hitPoints")
    if isinstance(hp, bool) or not isinstance(hp, (int, float)) or hp <= 0:
        return False
    combatant_id = creature.get("combatantId")
    encounter_id = encounter.get("encounterId")
    if not combatant_id or not encounter_id:
        return False
    wanted = wake_effect_id(combatant_id)
    return any(
        isinstance(effect, dict)
        and effect.get("effectId") == wanted
        and effect.get("sourceEncounterId") == encounter_id
        for effect in sheet.get("temporaryEffects") or []
    )


def keep_row_status(sheet, creature, encounter):
    """C5 at a sheet-to-row status copy: True when the copy is skipped."""
    from core.managers.combat_state import normalize_status

    if not isinstance(sheet, dict):
        return False
    return normalize_status(sheet.get("status")) == UNCONSCIOUS and wake_holds(sheet, creature, encounter)


def restore_woken(sheet):
    """C6 (K1): status alive when it reads unconscious above 0 HP and nothing
    states unconscious (no live effect, no condition entry). The write-back's
    own rule (stats._write_back_states) as a value rule. True when changed."""
    from core.managers.combat_state import normalize_status

    if not isinstance(sheet, dict) or normalize_status(sheet.get("status")) != UNCONSCIOUS:
        return False
    hp = sheet.get("hitPoints")
    if isinstance(hp, bool) or not isinstance(hp, int) or hp <= 0:
        return False
    if states_unconscious(sheet):
        return False
    for effect in sheet.get("temporaryEffects") or []:
        if isinstance(effect, dict) and any(
            name.strip().casefold() == UNCONSCIOUS for name in _names(effect.get("conditions"))
        ):
            return False
    sheet["status"] = "alive"
    return True


def restore_woken_after(before, after):
    """C6 on every sheet whose wake effect is gone between ``before`` and
    ``after`` ({name: sheet}). A function of the two states, so a replay of the
    same event agrees. Returns the names restored."""
    restored = []
    for name, sheet in (after or {}).items():
        old = (before or {}).get(name)
        gone = wake_effect_ids(old) - wake_effect_ids(sheet)
        if gone and restore_woken(sheet):
            restored.append(name)
    return restored


def wake_removals(event, encounter, characters):
    """C4: one remove op per sheet-backed target this event damaged and left
    above 0 HP (HP or temporary HP lowered) whose sheet holds its wake effect."""
    from core.managers.combat_state import combatant_by_id

    records = []
    for part in (event, (event or {}).get("bonusAction")):
        outcome = part.get("outcome") if isinstance(part, dict) else None
        if isinstance(outcome, dict) and isinstance(outcome.get("targets"), list):
            records.extend(outcome["targets"])
    ops, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            continue
        hp_before, hp_after = record.get("hpBefore"), record.get("hpAfter")
        if not isinstance(hp_after, int) or isinstance(hp_after, bool) or hp_after <= 0:
            continue
        hurt = isinstance(hp_before, int) and hp_after < hp_before
        temp_before, temp_after = record.get("tempHpBefore"), record.get("tempHpAfter")
        if isinstance(temp_before, int) and isinstance(temp_after, int) and temp_after < temp_before:
            hurt = True
        if not hurt:
            continue
        combatant_id = record.get("combatantId")
        creature = combatant_by_id(encounter, combatant_id)
        if not isinstance(creature, dict) or creature.get("type") not in ("npc", "player") or combatant_id in seen:
            continue
        name = creature.get("name")
        effect_id = wake_effect_id(combatant_id)
        if effect_id not in wake_effect_ids((characters or {}).get(name)):
            continue
        seen.add(combatant_id)
        ops.append({"op": "remove", "effectId": effect_id, "name": WAKE_NAME, "owner": name})
    return ops


def sweep_wake_effects(sheet):
    """C2b: the sheet without any wake effect, then C6. Returns (sheet, removed)."""
    from core.effects.lifecycle import apply_effect_ops

    removed = sorted(wake_effect_ids(sheet))
    if not removed:
        return sheet, []
    swept = apply_effect_ops(sheet, [{"op": "remove", "effectId": effect_id} for effect_id in removed])
    restore_woken(swept)
    return swept, removed


# Builder (C1) --------------------------------------------------------------

def _present_person(place_occupants, occupant_id):
    occupant = (place_occupants or {}).get(occupant_id) if occupant_id else None
    if not isinstance(occupant, dict) or occupant.get("kind") != "person":
        return False
    count = occupant.get("count", 1)
    return isinstance(count, int) and not isinstance(count, bool) and count >= 1


def sleeper_rows(encounter, participants, npc_sheets, place_occupants):
    """The (row, sheet) pairs C1 seats asleep: a hostile npc, active and
    initiative-eligible, a sleeper sheet, and a present person occupant id.
    ``npc_sheets`` is [(row, sheet)] from the build."""
    from core.managers.combat_state import combat_provenance

    if combat_provenance(encounter) != "typed":
        return []
    eligible = {
        item.get("combatantId")
        for item in participants or []
        if isinstance(item, dict) and item.get("participation") == "active" and item.get("initiativeEligible") is True
    }
    found = []
    for row, sheet in npc_sheets or []:
        if not isinstance(row, dict) or row.get("type") != "npc" or row.get("faction") != "hostile":
            continue
        if row.get("combatantId") not in eligible:
            continue
        if not is_sleeper_sheet(sheet) or not _present_person(place_occupants, row.get("occupantId")):
            continue
        found.append((row, sheet))
    return found


def _effect_states_unconscious(sheet):
    """Whether a live effect on the sheet states unconscious (it holds the
    sheet itself; no stated-only sleep to seat)."""
    for effect in (sheet or {}).get("temporaryEffects") or []:
        if isinstance(effect, dict) and any(
            name.strip().casefold() == UNCONSCIOUS for name in _names(effect.get("conditions"))
        ):
            return True
    return False


def party_side(row):
    """#1894 D-1894-5: the player, a party companion or a friendly npc."""
    return isinstance(row, dict) and (row.get("type") == "player" or row.get("faction") == "party")


def party_sleeper_rows(encounter, participants, sheets):
    """#1894 D-1894-5 (B): the (row, sheet) pairs seated asleep on the party's
    side: a party-side row, active and initiative-eligible, whose sheet states
    unconscious above 0 HP with no effect behind it. Seated as #1907's hostile
    sleeper is, so damage or round 1's end wakes them. ``sheets`` is
    [(row, sheet)] from the build (the player and the npcs)."""
    from core.managers.combat_state import combat_provenance

    if combat_provenance(encounter) != "typed":
        return []
    eligible = {
        item.get("combatantId")
        for item in participants or []
        if isinstance(item, dict) and item.get("participation") == "active" and item.get("initiativeEligible") is True
    }
    found = []
    for row, sheet in sheets or []:
        if not party_side(row) or row.get("type") not in ("player", "npc"):
            continue
        if row.get("combatantId") not in eligible or row.get("effectIncapacitated") is True:
            continue
        if not is_sleeper_sheet(sheet) or not states_unconscious(sheet) or _effect_states_unconscious(sheet):
            continue
        found.append((row, sheet))
    return found


def seat_sleeper(row):
    """C1 on one row: alive, conditions [unconscious], the marker, and
    effectIncapacitated as a surprised creature is seated."""
    row["status"] = "alive"
    row["conditions"] = [UNCONSCIOUS]
    row[WAKE_MARKER] = {"effectId": wake_effect_id(row.get("combatantId"))}
    row["effectIncapacitated"] = True


def opening_names(encounter, characters=None):
    """C3: the rows asleep at the opening (marker, or the sheet effect)."""
    names = []
    for creature in (encounter or {}).get("creatures") or []:
        if not isinstance(creature, dict):
            continue
        asleep = isinstance(creature.get(WAKE_MARKER), dict)
        if not asleep and characters is not None:
            asleep = wake_effect_id(creature.get("combatantId")) in wake_effect_ids(characters.get(creature.get("name")))
        if asleep:
            names.append(creature)
    return names


# The wake (C2) -------------------------------------------------------------

def marked_rows(encounter):
    return [
        creature for creature in (encounter or {}).get("creatures") or []
        if isinstance(creature, dict) and creature.get("type") in ("npc", "player")
        and isinstance(creature.get(WAKE_MARKER), dict)
    ]


def wake_marked(encounter_path, character_paths, timeout_seconds=5.0):
    """C2: under the combat leases, sheet first (status alive if unconscious,
    the wake effect upserted with engine=False), then the encounter write that
    clears every marker. Idempotent. Returns (encounter, {name: sheet})."""
    from core.effects.lifecycle import apply_effect_ops
    from core.managers.combat_state import normalize_status
    from core.managers.combat_transaction import _combat_leases, _load_object, _write_object

    with _combat_leases(encounter_path, character_paths, timeout_seconds):
        encounter = _load_object(encounter_path, "encounter")
        rows = marked_rows(encounter)
        if not rows:
            return encounter, {}
        encounter_id = encounter.get("encounterId")
        woken = {}
        for row in rows:
            name = row.get("name")
            path = (character_paths or {}).get(name)
            if not path:
                continue
            sheet = _load_object(path, "character %s" % name)
            if normalize_status(sheet.get("status")) == UNCONSCIOUS:
                sheet["status"] = "alive"
            sheet = apply_effect_ops(
                sheet,
                [{"op": "add", "effect": wake_effect(row.get("combatantId"), encounter_id)}],
                engine=False,
            )
            _write_object(path, sheet, "sleeper wake for %s" % name)
            woken[name] = deepcopy(sheet)
        for row in rows:
            row.pop(WAKE_MARKER, None)
        _write_object(encounter_path, encounter, "sleeper wake receipt")
        return encounter, woken


def sweep_encounter_sheets(encounter_path, character_paths, timeout_seconds=5.0):
    """C2b at a stale clear: every wake effect off the listed sheets, then C6,
    under the leases. Returns the names swept."""
    from core.managers.combat_transaction import _combat_leases, _load_object, _write_object

    swept_names = []
    with _combat_leases(encounter_path, character_paths, timeout_seconds):
        for name, path in (character_paths or {}).items():
            sheet = _load_object(path, "character %s" % name)
            swept, removed = sweep_wake_effects(sheet)
            if removed:
                _write_object(path, swept, "sleeper sweep for %s" % name)
                swept_names.append(name)
    return swept_names
