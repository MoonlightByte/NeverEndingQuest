# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Hit points, spell slots and class feature uses as engine resources (E8).

Every character carries ``hp``, one ``slot:N`` per spell slot level and one
``use:<feature>`` per class feature usage pool (genesis, typed fields only). A
change is a signed whole number per pool:

- hit points: a negative amount is ``damage`` (clamped at zero, the character
  drops), a positive amount is ``heal`` (clamped at the maximum);
- slots and feature uses: a negative amount is ``spend`` (refused when the pool
  cannot cover it), a positive amount is ``heal`` (an exact refill, clamped at
  the maximum).

All lines of one request commit together or not at all. The values written back
to the sheet are the engine's, never a number computed here or by a model.
Maximums are never written by this module: level-up and the effects layer own
``maxHitPoints`` and ``max``. Nothing here reads prose or writes files.
"""
import copy
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import apply, genesis, stats

HP_DELTA = "hpDelta"
SLOT_DELTA = "spellSlotDelta"
USE_DELTA = "featureUseDelta"
# Temporary hit points are granted, never healed or spent: a positive whole
# number sets the buffer to max(current, amount); damage drains it first
# (engine buffer). Loss is only through damage, so a negative value is refused.
TEMP_HP_GRANT = "tempHpGrant"
DELTA_KEYS = (HP_DELTA, SLOT_DELTA, USE_DELTA, TEMP_HP_GRANT)
TEMP_HP = genesis.TEMP_HP_RESOURCE


@dataclass
class ResourceOutcome:
    ok: bool
    sheet: Optional[Dict[str, Any]] = None       # new copy with engine values
    applied: Dict[str, int] = field(default_factory=dict)  # resource id -> signed change requested
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    fault: Optional[Dict[str, Any]] = None
    gaps: List[str] = field(default_factory=list)
    concentration_lines: List[str] = field(default_factory=list)  # CN: the saves the engine made for this damage
    concentration_ended: Optional[str] = None                  # CN: why the engine ended the caster's concentration
    treated: Optional[Dict[str, Any]] = None  # K1: DamageApplied.resource for a kinded hp damage (requested, treated)


SPELL_REPOSITORY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                     "data", "spell_repository.json")


def _spell_levels(path: str) -> Dict[str, int]:
    """#1329: each spell_repository key with its typed integer level."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            spells = json.load(handle)
    except (OSError, ValueError):
        spells = {}
    return {key: entry["level"] for key, entry in (spells if isinstance(spells, dict) else {}).items()
            if isinstance(entry, dict) and type(entry.get("level")) is int}


SPELL_LEVELS = _spell_levels(SPELL_REPOSITORY_PATH)
if not SPELL_LEVELS:
    # Fail forward: without levels the spell-key and slot-level checks are skipped,
    # never every paid cast refused (the feat binding is still checked from the sheet).
    from utils.enhanced_logger import warning
    warning("SPELL_LEVELS is empty (%s unreadable): castingResource level checks skipped"
            % SPELL_REPOSITORY_PATH, category="character_updates")


def casting_resource_problem(choice: Any, sheet: Any) -> Optional[Tuple[str, str]]:
    """#1329 (D-1329-1): (code, reason) when a typed castingResource cannot pay
    for its typed ``spell``, else None. Only the choice's kind, featureName,
    level and spell key are read, against the sheet's feats[].grantedSpells
    binding and the spell_repository level; availability stays with the pool."""
    if not isinstance(choice, dict):
        return None
    spell = choice.get("spell")
    if not isinstance(spell, str) or not spell:
        return ("missing_spell", "castingResource needs spell, the spell's repository key "
                "(the key feats[].grantedSpells stores)")
    level = SPELL_LEVELS.get(spell)
    if level is None and SPELL_LEVELS:
        return ("unknown_spell", "castingResource spell %r is not a spell repository key" % spell)
    if level == 0:
        return ("cantrip_no_payment", "%s is a cantrip; a cantrip takes no castingResource" % spell)
    if choice.get("kind") == "feature":
        name = choice.get("featureName")
        feats = sheet.get("feats") if isinstance(sheet, dict) else None
        for feat in feats if isinstance(feats, list) else []:
            if not isinstance(feat, dict) or feat.get("name") != name:
                continue
            for grant in feat.get("grantedSpells") or []:
                if isinstance(grant, dict) and grant.get("spell") == spell and grant.get("resource") == name:
                    return None
        return ("feature_not_bound", "%s does not grant %s (feats[].grantedSpells)" % (name, spell))
    if (choice.get("kind") == "slot" and level is not None
            and type(choice.get("level")) is int and choice["level"] < level):
        return ("slot_below_spell_level", "a level %d slot cannot cast %s (level %d)"
                % (choice["level"], spell, level))
    return None


def casting_resource_delta(choice: Any, sheet: Any = None) -> Dict[str, Any]:
    """Resolve a typed casting payment, once, before the existing engine transaction.
    With ``sheet``, a choice that names its spell must also be able to pay for it
    (#1329); one without spell keeps the shape-only check (D-1329-1 last attempt)."""
    delta = _casting_resource_shape(choice)
    if sheet is not None and choice.get("spell") is not None:
        problem = casting_resource_problem(choice, sheet)
        if problem is not None:
            raise ValueError(problem[1])
    return delta


def _casting_resource_shape(choice: Any) -> Dict[str, Any]:
    if not isinstance(choice, dict):
        raise ValueError("castingResource must be an object")
    if choice.get("kind") == "feature":
        name = choice.get("featureName")
        if isinstance(name, str) and name.strip():
            return {USE_DELTA: {name: -1}}
        raise ValueError("feature castingResource requires featureName")
    if choice.get("kind") == "slot":
        level = choice.get("level")
        if type(level) is int and 1 <= level <= 9:
            return {SLOT_DELTA: {f"level{level}": -1}}
        raise ValueError("slot castingResource requires integer level 1..9")
    raise ValueError("castingResource kind must be feature or slot")


def _q(value: str) -> str:
    return genesis._q(value)


def _signed(label: str, amount: Any) -> Tuple[Optional[int], str]:
    if type(amount) is bool or type(amount) is not int:
        return None, f"{label} delta {amount!r} is not a whole number"
    return amount, ""


# #891: feats with their own use pool. SRD 5.2.1 Magic Initiate: the level 1
# spell is cast once without a spell slot, regained on a Long Rest. "namedBy"
# is the choice (its typed name in data/srd/choices.json) whose option a sheet
# writes after the feat name: the repeatable feat takes a different list each time.
FEAT_RULES = {"Magic Initiate": {"max": 1, "refreshOn": "longRest", "namedBy": "Spell List"}}
CHOICES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "data", "srd", "choices.json")


def _feat_uses(rules: Dict[str, Dict[str, Any]], path: str) -> Dict[str, Dict[str, Any]]:
    """Every whole feat name a sheet can carry for a feat in ``rules``, casefolded:
    the SRD name, and "<name> (<option>)" for each option of the rule's
    ``namedBy`` choice in data/srd/choices.json (the form the origins data
    writes, e.g. "Magic Initiate (Cleric)"). No name is cut or parsed (#855)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            feats = json.load(handle).get("feats") or []
    except (OSError, ValueError, AttributeError):
        feats = []
    uses = {name.casefold(): rule for name, rule in rules.items()}
    for feat in feats:
        rule = rules.get(feat.get("name")) if isinstance(feat, dict) else None
        if rule is None:
            continue
        for choice in feat.get("choices") or []:
            if not isinstance(choice, dict) or choice.get("name") != rule.get("namedBy"):
                continue
            options = choice.get("option_source")
            for option in options if isinstance(options, list) else []:
                uses[f"{feat['name']} ({option})".casefold()] = rule
    return uses


FEAT_USES = _feat_uses(FEAT_RULES, CHOICES_PATH)


def feat_usage(feat: Any) -> Optional[Dict[str, Any]]:
    """A full ``usage`` for a feat entry whose typed name is a FEAT_USES name (whole value), else None."""
    name = feat.get("name") if isinstance(feat, dict) else None
    rule = FEAT_USES.get(name.strip().casefold()) if isinstance(name, str) else None
    return None if rule is None else {"current": rule["max"], "max": rule["max"], "refreshOn": rule["refreshOn"]}


def add_feat_usage(sheet: Any) -> List[str]:
    """#891: a full ``usage`` on each feat that has a rule and no ``usage`` key
    yet (an explicit null is left as written). Returns the feat names set."""
    feats = sheet.get("feats") if isinstance(sheet, dict) else None
    added = []
    for feat in feats if isinstance(feats, list) else []:
        if isinstance(feat, dict) and "usage" not in feat:
            usage = feat_usage(feat)
            if usage is not None:
                feat["usage"] = usage
                added.append(str(feat.get("name")))
    return added


def _feature_pools(sheet: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """(name, feature) for every class feature, then every feat (#891), that
    carries a usage pool."""
    return [(f["name"], f) for f in list(sheet.get("classFeatures") or []) + list(sheet.get("feats") or [])
            if isinstance(f, dict) and isinstance(f.get("usage"), dict) and f.get("name")]


def resolve_feature(sheet: Dict[str, Any], name: Any) -> Tuple[Optional[str], str]:
    """The stored feature name for a delta key: exact, then unique case-insensitive."""
    pools = _feature_pools(sheet)
    names = [n for n, _ in pools]
    if name in names:
        return name, ""
    folded = [n for n in names if str(n).strip().lower() == str(name).strip().lower()]
    if len(folded) == 1:
        return folded[0], ""
    if folded:
        return None, f"feature {name!r} matches several use pools; name it exactly"
    return None, f"feature {name!r} has no use pool on the sheet (usage current/max)"


def normalize(sheet: Dict[str, Any], updates: Dict[str, Any]) -> Tuple[Optional[Dict[str, int]], str]:
    """The engine resource changes named by the three delta keys, or a reason.

    Returns {resource id: signed amount} with zero amounts dropped; an empty
    mapping means nothing to do.
    """
    out: Dict[str, int] = {}
    if HP_DELTA in updates:
        amount, reason = _signed("hit point", updates[HP_DELTA])
        if amount is None:
            return None, reason
        if "hitPoints" not in sheet:
            return None, "the sheet has no hitPoints to change"
        if amount:
            out["hp"] = amount
    if TEMP_HP_GRANT in updates:
        amount, reason = _signed("temporary hit point", updates[TEMP_HP_GRANT])
        if amount is None:
            return None, reason
        if "hitPoints" not in sheet:
            return None, "the sheet has no hitPoints; temporary hit points need a character with hit points"
        if amount < 0:
            return None, "temporary hit points are lost only through damage; a grant must be a positive whole number"
        if amount:
            out[TEMP_HP] = amount
    slots = updates.get(SLOT_DELTA)
    if slots is not None:
        if not isinstance(slots, dict):
            return None, "spellSlotDelta must be an object {levelN: signed whole number}"
        known = (sheet.get("spellcasting") or {}).get("spellSlots") if isinstance(sheet.get("spellcasting"), dict) else {}
        for key, amount in slots.items():
            if not (isinstance(known, dict) and isinstance(known.get(key), dict)):
                return None, f"spell slot level {key!r} is not on the sheet"
            value, reason = _signed(f"spell slot {key}", amount)
            if value is None:
                return None, reason
            if value:
                out[genesis.slot_resource_id(key)] = value
    uses = updates.get(USE_DELTA)
    if uses is not None:
        if not isinstance(uses, dict):
            return None, "featureUseDelta must be an object {feature name: signed whole number}"
        for name, amount in uses.items():
            stored, reason = resolve_feature(sheet, name)
            if stored is None:
                return None, reason
            value, reason = _signed(f"feature {stored}", amount)
            if value is None:
                return None, reason
            if value:
                out[genesis.feature_resource_id(stored)] = value
    return out, ""


def _label(sheet: Dict[str, Any], rid: str) -> str:
    """A sheet-facing name for a resource id (used only in refusal reasons)."""
    if rid == "hp":
        return "hit points"
    if rid == TEMP_HP:
        return "temporary hit points"
    if rid.startswith("slot:"):
        return f"level {rid[5:]} spell slots"
    for name, _ in _feature_pools(sheet):
        if genesis.feature_resource_id(name) == rid:
            return f"{name} uses"
    return rid


def lines(cid: str, deltas: Dict[str, int], kind: Optional[str] = None) -> List[str]:
    """One action per pool; ``kind`` (K1) types the hp damage so the engine treats it."""
    out = []
    for rid, amount in deltas.items():
        if amount < 0:
            verb = "damage" if rid == "hp" else "spend"
        elif rid == TEMP_HP:
            verb = "grant"
        else:
            verb = "heal"
        typed = f' kind {_q(kind)}' if kind and rid == "hp" and amount < 0 else ""
        out.append(f'{verb} {_q(cid)} resource {_q(rid)} by {abs(amount)}{typed};')
    return out


def _write_back(sheet: Dict[str, Any], status: Dict[str, Any]) -> Optional[str]:
    """Copy the engine's current values for every declared pool onto the sheet."""
    resources = status.get("resources") or {}

    def current(rid: str) -> Optional[int]:
        pool = resources.get(rid)
        return int(pool["current"]) if isinstance(pool, dict) and "current" in pool else None

    if "hitPoints" in sheet:
        value = current("hp")
        if value is None:
            return "engine returned no hit points"
        sheet["hitPoints"] = value
        temp = current(TEMP_HP)
        if temp is not None and (temp or "temporaryHitPoints" in sheet):
            sheet["temporaryHitPoints"] = temp
    slots = (sheet.get("spellcasting") or {}).get("spellSlots") if isinstance(sheet.get("spellcasting"), dict) else None
    if isinstance(slots, dict):
        for key, pool in slots.items():
            if isinstance(pool, dict) and str(key).startswith("level"):
                value = current(genesis.slot_resource_id(key))
                if value is not None:
                    pool["current"] = value
    for name, feature in _feature_pools(sheet):
        value = current(genesis.feature_resource_id(name))
        if value is not None:
            feature["usage"]["current"] = value
    die = genesis.hit_die(sheet)
    value = current(genesis.hit_dice_resource_id(die)) if die else None
    if value is not None:
        pools = sheet.get(genesis.HIT_DICE_FIELD)
        sheet[genesis.HIT_DICE_FIELD] = {**(pools if isinstance(pools, dict) else {}), f"d{die}": value}
    stats.store(sheet, status)
    return None


def run(sheet: Dict[str, Any], deltas: Dict[str, int], *, location: str = "sheet", max_hp: Optional[int] = None,
        request_id: Optional[str] = None, binary: Optional[str] = None,
        kind: Optional[str] = None) -> ResourceOutcome:
    """Submit {resource id: signed amount} for one sheet; write the engine's values back.

    ``max_hp`` is the effective maximum when a max-HP effect is live; the world
    is built with it so healing clamps at the value the table plays with, while
    the stored ``maxHitPoints`` is never touched.
    ``kind`` (K1) is a typed damage kind for the hp damage: the world then
    carries the attacks law and the sheet's traits for this request only, the
    engine treats the amount, and ``treated`` holds its record. Without a kind
    the request is byte-identical to before.
    """
    if not kind or deltas.get("hp", 0) >= 0:
        kind = None
    sheet = copy.deepcopy(sheet)
    world_sheet = copy.deepcopy(sheet)
    if max_hp is not None and type(max_hp) is int and max_hp >= 0:
        world_sheet["maxHitPoints"] = max_hp
    # CN: damage to a concentrating caster makes the engine roll the Constitution
    # save (no player prompt is possible inside a character update), so the world
    # carries dice; every other request is byte-identical to before.
    seed = None
    if deltas.get("hp", 0) < 0 and stats.concentration_instance(world_sheet):
        from core.nql import checks
        seed = checks.fresh_seed()
    world = genesis.build_world([world_sheet], location, dice_seed=seed, damage_traits=bool(kind))
    cid = genesis.character_id(sheet)
    if not deltas:
        return ResourceOutcome(True, sheet=sheet, gaps=world.gaps)
    try:
        response = apply.call({"world": world.source, "world_name": "resources-genesis.nql",
                               "actions": "\n".join(lines(cid, deltas, kind)), "actions_name": "resources.nql",
                               "actor": {"kind": "character", "id": cid},
                               "request": request_id or f"resources:{uuid.uuid4().hex}",
                               "status": [cid]}, binary=binary)
    except apply.EngineUnavailable as error:
        return ResourceOutcome(False, reason=str(error), gaps=world.gaps)
    if not response.get("ok"):
        fault = response.get("fault") or {}
        if fault.get("code") == "E_INSUFFICIENT_RESOURCE":
            rid = str(fault.get("field"))
            wanted = -deltas.get(rid, 0)
            left = dict((r, c) for r, c, _ in genesis.pool_resources(world_sheet, [])).get(rid)
            reason = (f"{sheet.get('name', cid)} cannot spend {wanted} of {_label(sheet, rid)}: "
                      f"{left} left (the pool would go below zero)")
        else:
            reason = f"engine refused at {response.get('phase')}: {response.get('diagnostics') or fault or response.get('error')}"
        return ResourceOutcome(False, reason=reason, fault=fault or None, gaps=world.gaps)
    statuses = [s for s in response.get("status") or []
                if isinstance(s.get("character"), dict) and s["character"].get("id") == cid]
    if not statuses:
        return ResourceOutcome(False, reason="engine returned no status for the character", gaps=world.gaps)
    treated = None
    if kind:
        from core.nql import attacks
        treated = attacks.treated_record(response)
        if treated is None:
            return ResourceOutcome(False, reason="engine returned no treated damage", gaps=world.gaps)
    problem = _write_back(sheet, statuses[0])
    if problem:
        return ResourceOutcome(False, reason=problem, gaps=world.gaps)
    from core.nql import concentration
    focus = concentration.read(world_sheet, response)
    return ResourceOutcome(True, sheet=sheet, applied=dict(deltas), receipt=response.get("receipt"), gaps=world.gaps,
                           concentration_lines=focus.lines, concentration_ended=focus.ended_reason,
                           treated=treated)


def apply_deltas(sheet: Dict[str, Any], updates: Dict[str, Any], **kwargs: Any) -> ResourceOutcome:
    """The three T079 delta keys of ``updates`` through the engine for one sheet."""
    deltas, reason = normalize(sheet, updates)
    if deltas is None:
        return ResourceOutcome(False, reason=reason)
    return run(sheet, deltas, **kwargs)


# ---------------------------------------------------------------------------
# Rests (E9): the engine restores pools to their maximum, or for a pool a Short
# Rest only partly refills (usage.shortRestRegain), heals it by that many uses,
# capped at the maximum by the engine; nothing is computed.
# ---------------------------------------------------------------------------
REST_KINDS = ("short", "long")
# usage.refreshOn values that a rest of each kind refills. A long rest refills
# every pool the sheet carries (all features recharge); a short rest refills the
# pools tagged for it. Slots refill on a long rest, or on a short rest for the
# classes whose typed ``class`` field names a pact caster.
SHORT_REST_REFRESH = ("shortRest",)
SHORT_REST_SLOT_CLASSES = ("warlock",)


@dataclass
class RestOutcome:
    ok: bool
    sheets: List[Dict[str, Any]] = field(default_factory=list)   # new copies, same order as given
    restored: Dict[str, List[str]] = field(default_factory=dict)  # sheet name -> what refilled
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    gaps: List[str] = field(default_factory=list)
    rolls: List[Dict[str, Any]] = field(default_factory=list)     # one engine roll record per hit die spent
    refused: Dict[str, str] = field(default_factory=dict)         # companion name -> why their hit dice were not spent


def _class_names(sheet: Dict[str, Any]) -> List[str]:
    names = [sheet.get("class")]
    for entry in sheet.get("classes") or []:
        if isinstance(entry, dict):
            names.append(entry.get("name") or entry.get("class"))
        else:
            names.append(entry)
    return [str(n).strip().lower() for n in names if isinstance(n, str) and n.strip()]


def rest_lines(sheet: Dict[str, Any], kind: str, gaps: List[str]) -> List[Tuple[str, str, Optional[int]]]:
    """(resource id, sheet-facing label, uses regained) the rest refills for this sheet.
    Uses regained is None for a full restore; a Short Rest regains only
    ``usage.shortRestRegain`` uses of a pool that carries it (#704, HQ6)."""
    cid = genesis.character_id(sheet)
    declared = {rid for rid, _, _ in genesis.pool_resources(sheet, gaps)}
    out: List[Tuple[str, str]] = []
    if kind == "long" and "hp" in declared:
        out.append(("hp", "hit points", None))
    if kind == "long" and TEMP_HP in declared:
        out.append((TEMP_HP, "temporary hit points (cleared)", None))
    slots_refill = kind == "long" or any(c in SHORT_REST_SLOT_CLASSES for c in _class_names(sheet))
    if slots_refill:
        for rid in sorted(r for r in declared if r.startswith("slot:")):
            out.append((rid, f"level {rid[5:]} spell slots", None))
    if kind == "long":
        # D-KWA-7b (SRD 5.2): a Long Rest restores all spent hit dice.
        for rid in sorted(r for r in declared if r.startswith("hitdice:")):
            out.append((rid, "hit dice", None))
    for name, feature in _feature_pools(sheet):
        rid = genesis.feature_resource_id(name)
        if rid not in declared:
            continue
        refresh = feature["usage"].get("refreshOn")
        if kind == "long" or refresh in SHORT_REST_REFRESH:
            regain = feature["usage"].get("shortRestRegain")
            partial = kind == "short" and type(regain) is int and regain > 0
            out.append((rid, f"{name} uses", regain if partial else None))
    return out


def _hit_dice_refusal(response: Dict[str, Any], sheets: List[Dict[str, Any]], ids: List[str],
                      hit_dice: Dict[str, int]) -> str:
    """The player-facing reason the engine refused a hit-die request."""
    fault = response.get("fault") or {}
    if fault.get("code") == "E_INSUFFICIENT_RESOURCE" and str(fault.get("field", "")).startswith("hitdice:"):
        sheet = next((s for s, c in zip(sheets, ids) if c == fault.get("subject")), None)
        if sheet is not None:
            left = {r: (c, m) for r, c, m in genesis.pool_resources(sheet, [])}.get(fault["field"], (0, 0))
            return (f"{sheet.get('name')} has {left[0]} of {left[1]} {fault['field'].split(':', 1)[1]} hit dice left and "
                    f"cannot spend {hit_dice.get(str(sheet.get('name')))}; spent hit dice return on a long rest")
    problem = fault or next(iter(response.get("diagnostics") or []), None) or {}
    if problem.get("code") == "E_ROLL":
        return f"the engine refused the hit die face (E_ROLL): it must be {problem.get('expected')}, not {problem.get('actual')}"
    return f"engine refused the hit dice at {response.get('phase')}: {problem or response.get('error')}"


def _spend_hit_dice(sheets: List[Dict[str, Any]], ids: List[str], spenders: List[int], actor: int,
                    rolls_by_die: Dict[int, List[str]], hit_dice: Dict[str, int], location: str, clock_tick: int,
                    root: str, binary: Optional[str]) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """One hit-die request: ``actor`` (a sheet index) invokes one hit-die Ability per die for each sheet in
    ``spenders``. The request actor is the dice controller: the party root rolls with the player's faces
    (``roll 1 { face n; }``) or declines them (``roll 1 engine;``); any other actor is the engine's.
    A fresh Battle seed per request. On success the hit points and hit dice are written onto ``sheets``
    and the engine's roll records are returned; nothing changes on a refusal."""
    from core.nql import checks

    world = genesis.hit_die_world(sheets, root, location, clock_tick, checks.fresh_seed())
    actions: List[str] = []
    for index in spenders:
        die = genesis.hit_die(sheets[index])
        for roll in rolls_by_die[index]:
            actions.append(f'invoke {_q(genesis.hit_die_ability_id(die))} {{ "actor" = character {_q(ids[actor])}; '
                           f'"target" = character {_q(ids[index])};{roll} }};')
    try:
        response = apply.call({"world": world.source, "world_name": "rest-hitdice.nql", "actions": "\n".join(actions),
                               "actions_name": "rest-hitdice-actions.nql",
                               "actor": {"kind": "character", "id": ids[actor]},
                               "request": f"rest:hitdice:{uuid.uuid4().hex}",
                               "status": [ids[index] for index in spenders]}, binary=binary)
    except apply.EngineUnavailable as error:
        return None, str(error)
    if not response.get("ok"):
        return None, _hit_dice_refusal(response, sheets, ids, hit_dice)
    statuses = {s["character"]["id"]: s.get("resources") or {} for s in response.get("status") or []
                if isinstance(s.get("character"), dict)}
    for index in spenders:
        values = statuses.get(ids[index]) or {}
        die = genesis.hit_die(sheets[index])
        pool = genesis.hit_dice_resource_id(die)
        if not (isinstance(values.get("hp"), dict) and isinstance(values.get(pool), dict)):
            return None, "engine returned no hit points or hit dice for a resting character"
        sheets[index]["hitPoints"] = int(values["hp"]["current"])
        stored = sheets[index].get(genesis.HIT_DICE_FIELD)
        sheets[index][genesis.HIT_DICE_FIELD] = {**(stored if isinstance(stored, dict) else {}),
                                                 f"d{die}": int(values[pool]["current"])}
    names = {c: str(s.get("name")) for s, c in zip(sheets, ids)}
    rolls = []
    for event in (response.get("receipt") or {}).get("events") or []:
        record = event.get("resource_roll") if isinstance(event, dict) else None
        if isinstance(record, dict) and record.get("target") in names:
            rolls.append({"name": names[record["target"]], "sides": record.get("sides"), "faces": record.get("faces"),
                          "source": record.get("source"), "engine_drawn": bool(record.get("engine_drawn")),
                          "bonus": record.get("bonus"), "actual": int(record.get("actual") or 0)})
    return rolls, ""


def rest(sheets: List[Dict[str, Any]], kind: str, *, location: str = "party", request_id: Optional[str] = None,
         binary: Optional[str] = None, hit_dice: Optional[Dict[str, int]] = None,
         faces: Optional[List[Any]] = None, root: Optional[str] = None, clock_tick: int = 0) -> RestOutcome:
    """Refill every pool the rest recovers on every sheet, one engine request.

    The engine's ``restore`` sets a pool to its maximum; a pool already full is
    a no-op. A Short Rest's partial regain is ``heal ... by n``, which the engine
    caps at the maximum and never refuses. ``hit_dice`` (sheet name -> dice spent,
    a Short Rest only) are rolled first by the engine in the hit-die world: the
    player's own dice (``root``, the player's sheet name) in one request with
    ``faces`` (one per die: a whole number the player typed, or "engine" to let
    the engine roll), then every other character's in one request whose actor is
    the first of them, so the engine rolls theirs. The player's request refused
    refuses the rest; a refused second request leaves those characters'
    hit points and hit dice as they were and names them in ``refused`` (D-KWA-7e).
    All sheets are rebuilt from the engine's values together.
    """
    if kind not in REST_KINDS:
        return RestOutcome(False, reason=f"unknown rest kind {kind!r}; use short or long")
    hit_dice = {str(name): count for name, count in (hit_dice or {}).items()}
    if hit_dice and kind != "short":
        return RestOutcome(False, reason="hit dice are spent on a short rest; a long rest restores every hit point")
    if any(type(count) is not int or count < 1 for count in hit_dice.values()):
        return RestOutcome(False, reason="hit dice spent must be a positive whole number")
    unknown = sorted(set(hit_dice) - {str(s.get("name")) for s in sheets})
    if unknown:
        return RestOutcome(False, reason=f"no resting character is named {', '.join(unknown)}")
    sheets = [copy.deepcopy(s) for s in sheets]
    if not sheets:
        return RestOutcome(False, reason="no one is resting")
    if kind == "long":
        # #891 (owner D-891-2 A): a sheet that has a feat with its own use
        # but no pool yet gets it, full, on its first Long Rest.
        for sheet in sheets:
            add_feat_usage(sheet)
    ids = [genesis.character_id(s) for s in sheets]
    if len(set(ids)) != len(ids):
        return RestOutcome(False, reason="two of the characters resolve to the same engine id")
    rolls: List[Dict[str, Any]] = []
    refused: Dict[str, str] = {}
    if hit_dice:
        names = [str(s.get("name")) for s in sheets]
        root_index = names.index(root) if root in names else 0
        for name in hit_dice:
            sheet = sheets[names.index(name)]
            die = genesis.hit_die(sheet)
            if not die or genesis.hit_dice_resource_id(die) not in {r for r, _, _ in genesis.pool_resources(sheet, [])}:
                return RestOutcome(False, reason=f"{name} has no hit dice pool (no known class and level)")
        player = names[root_index] if names[root_index] in hit_dice else None
        answers = list(faces) if faces is not None else ["engine"] * hit_dice.get(player or "", 0)
        if player and len(answers) != hit_dice[player]:
            return RestOutcome(False, reason=f"{player} spends {hit_dice[player]} hit dice but {len(answers)} were rolled")
        if any(not (answer == "engine" or (type(answer) is int)) for answer in answers):
            return RestOutcome(False, reason="a hit die is a whole number the player rolled, or the engine's roll")
        # The player's dice carry their answers; every other character's carry no roll input.
        rolls_by_die = {names.index(name): ([" roll 1 engine;" if answer == "engine" else f" roll 1 {{ face {answer}; }};"
                                             for answer in answers] if name == player else [""] * count)
                        for name, count in hit_dice.items()}
        if player:
            got, why = _spend_hit_dice(sheets, ids, [root_index], root_index, rolls_by_die, hit_dice, location,
                                       clock_tick, ids[root_index], binary)
            if got is None:
                return RestOutcome(False, reason=why)
            rolls.extend(got)
        others = [index for index in rolls_by_die if index != root_index]
        if others:
            got, why = _spend_hit_dice(sheets, ids, others, others[0], rolls_by_die, hit_dice, location, clock_tick,
                                       ids[root_index], binary)
            if got is None:
                refused.update({names[index]: why for index in others})
            else:
                rolls.extend(got)
    world = genesis.build_world(sheets, location)
    gaps = list(world.gaps)
    actions: List[str] = []
    labels: Dict[str, List[Tuple[str, str]]] = {}
    for sheet, cid in zip(sheets, ids):
        labels[cid] = rest_lines(sheet, kind, gaps)
        actions.extend(f'heal {_q(cid)} resource {_q(rid)} by {regain};' if regain else
                       f'restore {_q(cid)} resource {_q(rid)};' for rid, _, regain in labels[cid])
        level = stats.exhaustion_level(sheet, gaps)
        if kind == "long" and level > 0:
            # SRD: a Long Rest removes one level of exhaustion (the highest instance).
            iid = stats.exhaustion_instance(level) + ":" + cid.split(":", 1)[1]
            actions.append(f'remove condition {_q(iid)} from {_q(cid)};')
    healed = {roll["name"] for roll in rolls}
    restored: Dict[str, List[str]] = {str(s.get("name")): (["hit points (hit dice)"] if str(s.get("name")) in healed else [])
                                      for s in sheets}
    if not actions:
        return RestOutcome(True, sheets=sheets, restored=restored, gaps=gaps, rolls=rolls, refused=refused)
    try:
        response = apply.call({"world": world.source, "world_name": "rest-genesis.nql",
                               "actions": "\n".join(actions), "actions_name": "rest.nql",
                               "actor": {"kind": "character", "id": ids[0]},
                               "request": request_id or f"rest:{uuid.uuid4().hex}",
                               "status": ids}, binary=binary)
    except apply.EngineUnavailable as error:
        return RestOutcome(False, reason=str(error), gaps=gaps)
    if not response.get("ok"):
        fault = response.get("fault") or {}
        return RestOutcome(False, reason=f"engine refused at {response.get('phase')}: "
                                         f"{response.get('diagnostics') or fault or response.get('error')}", gaps=gaps)
    statuses = {s["character"]["id"]: s for s in response.get("status") or [] if isinstance(s.get("character"), dict)}
    for sheet, cid in zip(sheets, ids):
        before = {rid: cur for rid, cur, _ in genesis.pool_resources(sheet, [])}
        level_before = stats.exhaustion_level(sheet, [])
        if cid not in statuses:
            return RestOutcome(False, reason="engine returned no status for a resting character", gaps=gaps)
        problem = _write_back(sheet, statuses[cid])
        if problem:
            return RestOutcome(False, reason=problem, gaps=gaps)
        after = {rid: cur for rid, cur, _ in genesis.pool_resources(sheet, [])}
        restored[str(sheet.get("name"))] += [label for rid, label, _ in labels[cid] if after.get(rid) != before.get(rid)]
        level_after = stats.exhaustion_level(sheet, [])
        if level_after != level_before:
            restored[str(sheet.get("name"))].append(f"exhaustion level {level_before} -> {level_after}")
    return RestOutcome(True, sheets=sheets, restored=restored, receipt=response.get("receipt"), gaps=gaps,
                       rolls=rolls, refused=refused)
