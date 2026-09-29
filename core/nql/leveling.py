# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Level-up growth through the engine (L1).

The tables settle what grows; the engine applies it in one request: ``expand`` the
hit point maximum by the gain and ``heal`` the same amount (max and current rise
together), ``expand`` each spell slot level whose maximum grew. Feature pools take
their new maximum from the tables on the sheet (genesis reads ``usage.max``), and
the engine owns the current value from then on. All lines commit together or
nothing does; the values written back are the engine's.
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.nql import apply, genesis, resources


@dataclass
class GrowthOutcome:
    ok: bool
    sheet: Optional[Dict[str, Any]] = None
    operations: List[str] = field(default_factory=list)
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return genesis._q(value)


def grow(sheet: Dict[str, Any], hp_gain: int, slot_targets: Dict[str, int], *, location: str = "sheet",
         request_id: Optional[str] = None, binary: Optional[str] = None) -> GrowthOutcome:
    """Raise hit points (max and current) and slot maxima to the table's targets.

    ``slot_targets`` is {levelN: new maximum}; a level whose maximum already
    matches is untouched, a level whose stored maximum is above the table is
    reported as a gap and left alone (never lowered by a level-up).
    """
    sheet = copy.deepcopy(sheet)
    if type(hp_gain) is not int or hp_gain < 0:
        return GrowthOutcome(False, reason="hit point gain must be a non-negative whole number")
    cid = genesis.character_id(sheet)
    world = genesis.build_world([sheet], location)
    gaps = list(world.gaps)
    lines: List[str] = []
    if hp_gain:
        lines.append(f'expand {_q(cid)} resource "hp" by {hp_gain};')
        lines.append(f'heal {_q(cid)} resource "hp" by {hp_gain};')
    slots = (sheet.get("spellcasting") or {}).get("spellSlots") if isinstance(sheet.get("spellcasting"), dict) else None
    if isinstance(slots, dict):
        for key, target in sorted(slot_targets.items()):
            pool = slots.get(key)
            if not isinstance(pool, dict):
                continue
            current_max = pool.get("max") if type(pool.get("max")) is int else 0
            if target > current_max:
                lines.append(f'expand {_q(cid)} resource {_q(genesis.slot_resource_id(key))} by {target - current_max};')
            elif target < current_max:
                gaps.append(f"{key} max {current_max} is above the table's {target}; left as is")
    if not lines:
        return GrowthOutcome(True, sheet=sheet, gaps=gaps)
    try:
        response = apply.call({"world": world.source, "world_name": "levelup-genesis.nql",
                               "actions": "\n".join(lines), "actions_name": "levelup.nql",
                               "actor": {"kind": "character", "id": cid},
                               "request": request_id or f"levelup:{uuid.uuid4().hex}",
                               "status": [cid]}, binary=binary)
    except apply.EngineUnavailable as error:
        return GrowthOutcome(False, operations=lines, reason=str(error), gaps=gaps)
    if not response.get("ok"):
        fault = response.get("fault") or {}
        return GrowthOutcome(False, operations=lines, gaps=gaps,
                             reason=f"engine refused at {response.get('phase')}: {response.get('diagnostics') or fault or response.get('error')}")
    statuses = [s for s in response.get("status") or [] if isinstance(s.get("character"), dict) and s["character"]["id"] == cid]
    if not statuses:
        return GrowthOutcome(False, operations=lines, reason="engine returned no status", gaps=gaps)
    res = statuses[0].get("resources") or {}
    hp = res.get("hp") or {}
    if "current" in hp and "maximum" in hp:
        sheet["hitPoints"] = int(hp["current"])
        sheet["maxHitPoints"] = int(hp["maximum"])
    if isinstance(slots, dict):
        for key, pool in slots.items():
            r = res.get(genesis.slot_resource_id(key))
            if isinstance(pool, dict) and isinstance(r, dict):
                pool["max"] = int(r.get("maximum", pool.get("max", 0)))
                pool["current"] = int(r.get("current", pool.get("current", 0)))
    return GrowthOutcome(True, sheet=sheet, operations=lines, receipt=response.get("receipt"), gaps=gaps)
