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


def _q(value: str) -> str:
    return genesis._q(value)


def _signed(label: str, amount: Any) -> Tuple[Optional[int], str]:
    if type(amount) is bool or type(amount) is not int:
        return None, f"{label} delta {amount!r} is not a whole number"
    return amount, ""


def _feature_pools(sheet: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """(name, feature) for every class feature that carries a usage pool."""
    return [(f["name"], f) for f in sheet.get("classFeatures") or []
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


def lines(cid: str, deltas: Dict[str, int]) -> List[str]:
    out = []
    for rid, amount in deltas.items():
        if amount < 0:
            verb = "damage" if rid == "hp" else "spend"
        elif rid == TEMP_HP:
            verb = "grant"
        else:
            verb = "heal"
        out.append(f'{verb} {_q(cid)} resource {_q(rid)} by {abs(amount)};')
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
    stats.store(sheet, status)
    return None


def run(sheet: Dict[str, Any], deltas: Dict[str, int], *, location: str = "sheet", max_hp: Optional[int] = None,
        request_id: Optional[str] = None, binary: Optional[str] = None) -> ResourceOutcome:
    """Submit {resource id: signed amount} for one sheet; write the engine's values back.

    ``max_hp`` is the effective maximum when a max-HP effect is live; the world
    is built with it so healing clamps at the value the table plays with, while
    the stored ``maxHitPoints`` is never touched.
    """
    sheet = copy.deepcopy(sheet)
    world_sheet = copy.deepcopy(sheet)
    if max_hp is not None and type(max_hp) is int and max_hp >= 0:
        world_sheet["maxHitPoints"] = max_hp
    world = genesis.build_world([world_sheet], location)
    cid = genesis.character_id(sheet)
    if not deltas:
        return ResourceOutcome(True, sheet=sheet, gaps=world.gaps)
    try:
        response = apply.call({"world": world.source, "world_name": "resources-genesis.nql",
                               "actions": "\n".join(lines(cid, deltas)), "actions_name": "resources.nql",
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
    problem = _write_back(sheet, statuses[0])
    if problem:
        return ResourceOutcome(False, reason=problem, gaps=world.gaps)
    return ResourceOutcome(True, sheet=sheet, applied=dict(deltas), receipt=response.get("receipt"), gaps=world.gaps)


def apply_deltas(sheet: Dict[str, Any], updates: Dict[str, Any], **kwargs: Any) -> ResourceOutcome:
    """The three T079 delta keys of ``updates`` through the engine for one sheet."""
    deltas, reason = normalize(sheet, updates)
    if deltas is None:
        return ResourceOutcome(False, reason=reason)
    return run(sheet, deltas, **kwargs)


# ---------------------------------------------------------------------------
# Rests (E9): the engine restores pools to their maximum; nothing is computed.
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


def _class_names(sheet: Dict[str, Any]) -> List[str]:
    names = [sheet.get("class")]
    for entry in sheet.get("classes") or []:
        if isinstance(entry, dict):
            names.append(entry.get("name") or entry.get("class"))
        else:
            names.append(entry)
    return [str(n).strip().lower() for n in names if isinstance(n, str) and n.strip()]


def rest_lines(sheet: Dict[str, Any], kind: str, gaps: List[str]) -> List[Tuple[str, str]]:
    """(resource id, sheet-facing label) the rest restores for this sheet."""
    cid = genesis.character_id(sheet)
    declared = {rid for rid, _, _ in genesis.pool_resources(sheet, gaps)}
    out: List[Tuple[str, str]] = []
    if kind == "long" and "hp" in declared:
        out.append(("hp", "hit points"))
    if kind == "long" and TEMP_HP in declared:
        out.append((TEMP_HP, "temporary hit points (cleared)"))
    slots_refill = kind == "long" or any(c in SHORT_REST_SLOT_CLASSES for c in _class_names(sheet))
    if slots_refill:
        for rid in sorted(r for r in declared if r.startswith("slot:")):
            out.append((rid, f"level {rid[5:]} spell slots"))
    for name, feature in _feature_pools(sheet):
        rid = genesis.feature_resource_id(name)
        if rid not in declared:
            continue
        refresh = feature["usage"].get("refreshOn")
        if kind == "long" or refresh in SHORT_REST_REFRESH:
            out.append((rid, f"{name} uses"))
    return out


def rest(sheets: List[Dict[str, Any]], kind: str, *, location: str = "party", request_id: Optional[str] = None,
         binary: Optional[str] = None) -> RestOutcome:
    """Refill every pool the rest recovers on every sheet, one engine request.

    The engine's ``restore`` sets a pool to its maximum; a pool already full is
    a no-op. All sheets are rebuilt from the engine's values together.
    """
    if kind not in REST_KINDS:
        return RestOutcome(False, reason=f"unknown rest kind {kind!r}; use short or long")
    sheets = [copy.deepcopy(s) for s in sheets]
    if not sheets:
        return RestOutcome(False, reason="no one is resting")
    world = genesis.build_world(sheets, location)
    ids = [genesis.character_id(s) for s in sheets]
    if len(set(ids)) != len(ids):
        return RestOutcome(False, reason="two of the characters resolve to the same engine id", gaps=world.gaps)
    gaps = list(world.gaps)
    actions: List[str] = []
    labels: Dict[str, List[Tuple[str, str]]] = {}
    for sheet, cid in zip(sheets, ids):
        labels[cid] = rest_lines(sheet, kind, gaps)
        actions.extend(f'restore {_q(cid)} resource {_q(rid)};' for rid, _ in labels[cid])
        level = stats.exhaustion_level(sheet, gaps)
        if kind == "long" and level > 0:
            # SRD: a Long Rest removes one level of exhaustion (the highest instance).
            iid = stats.exhaustion_instance(level) + ":" + cid.split(":", 1)[1]
            actions.append(f'remove condition {_q(iid)} from {_q(cid)};')
    if not actions:
        return RestOutcome(True, sheets=sheets, gaps=gaps)
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
    restored: Dict[str, List[str]] = {}
    for sheet, cid in zip(sheets, ids):
        before = {rid: cur for rid, cur, _ in genesis.pool_resources(sheet, [])}
        level_before = stats.exhaustion_level(sheet, [])
        if cid not in statuses:
            return RestOutcome(False, reason="engine returned no status for a resting character", gaps=gaps)
        problem = _write_back(sheet, statuses[cid])
        if problem:
            return RestOutcome(False, reason=problem, gaps=gaps)
        after = {rid: cur for rid, cur, _ in genesis.pool_resources(sheet, [])}
        restored[str(sheet.get("name"))] = [label for rid, label in labels[cid] if after.get(rid) != before.get(rid)]
        level_after = stats.exhaustion_level(sheet, [])
        if level_after != level_before:
            restored[str(sheet.get("name"))].append(f"exhaustion level {level_before} -> {level_after}")
    return RestOutcome(True, sheets=sheets, restored=restored, receipt=response.get("receipt"), gaps=gaps)
