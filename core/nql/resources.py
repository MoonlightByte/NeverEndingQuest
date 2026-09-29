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

from core.nql import apply, genesis

HP_DELTA = "hpDelta"
SLOT_DELTA = "spellSlotDelta"
USE_DELTA = "featureUseDelta"
DELTA_KEYS = (HP_DELTA, SLOT_DELTA, USE_DELTA)


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
