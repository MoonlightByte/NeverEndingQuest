# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Concentration through the engine (CN): reading the save and the end.

The caster's sheet carries a code-written ``concentration`` record
({"name", "group", "targets", "expiration"}); genesis declares one
``state:concentration`` instance for it. When damage reaches the engine
(core/nql/resources) the world carries a dice seed, the engine makes the
Constitution save by itself (DC max(10, min(30, damage / 2)), the caster's
roll modes applied) and reports it under ``checks`` with the instance and the
damage; a failed save, or an incapacitating state, lists the instance under
``ended_conditions``. Nothing here decides or computes; this module only
turns those records into the one line the DM reads and the reason the host
ends the spell everywhere (core/managers/concentration_runtime).
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.nql import stats


@dataclass
class ConcentrationOutcome:
    lines: List[str] = field(default_factory=list)   # one per save the engine made, DM wording
    ended_reason: Optional[str] = None               # set when the engine ended the concentration


def _signed(value: Any) -> str:
    return f"{value:+d}" if type(value) is int else str(value)


def save_line(sheet: Dict[str, Any], record: Dict[str, Any]) -> str:
    """'Eirik Stonehand Constitution save to keep concentrating on Bless (12 damage, DC 10): rolled 14 +2 = 16, success by 6; Bless holds'."""
    name = str(sheet.get("name", "?"))
    spell = (stats.concentration_of(sheet) or {}).get("name") or "the spell"
    intent = record.get("intent") or {}
    dc = intent.get("dc")
    damage = record.get("damage")
    head = f"{name} Constitution save to keep concentrating on {spell} ({damage} damage, DC {dc})"
    faces = record.get("faces") or []
    if faces == [] and record.get("kept") is None:
        return f"{head}: automatic failure (no dice); concentration broken, {spell} ends for everyone it affected"
    mode = record.get("roll")
    dice = ", ".join(str(f) for f in faces) if faces else "?"
    shown = f"rolled {dice}" + (f" ({mode}, kept {record.get('kept')})" if mode in ("advantage", "disadvantage") else "")
    total = record.get("total")
    arith = f"{shown} {_signed(record.get('bonus'))} = {total}"
    margin = record.get("margin")
    if record.get("success"):
        return f"{head}: {arith}, success by {margin}; {spell} holds"
    return f"{head}: {arith}, failure by {abs(margin) if type(margin) is int else '?'}; concentration broken, {spell} ends for everyone it affected"


def read(sheet: Dict[str, Any], response: Dict[str, Any]) -> ConcentrationOutcome:
    """The saves and the end the engine reported for this sheet's concentration instance."""
    out = ConcentrationOutcome()
    instance = stats.concentration_instance(sheet)
    if not instance:
        return out
    for record in response.get("checks") or []:
        if isinstance(record, dict) and record.get("condition") == instance:
            out.lines.append(save_line(sheet, record))
    for record in response.get("ended_conditions") or []:
        if isinstance(record, dict) and record.get("instance") == instance:
            reason = str(record.get("reason") or "ended")
            out.ended_reason = {"check": "failed the Constitution save"}.get(reason, reason)
    return out
