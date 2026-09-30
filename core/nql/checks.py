"""Checks and saves through the rules engine (C2a).

The DM names the check (a skill, an ability save or check, initiative), the
difficulty and any situational advantage or disadvantage. The engine adds the
character's total, combines the situation with the conditions' roll modes
(Poisoned: disadvantage on checks; Paralyzed: Strength and Dexterity saves
fail), keeps the right die, and reports total, success and margin. Dice are
the player's faces (typed at the roll prompt) or the world's seeded dice.
No model and no Python arithmetic scores a roll.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import srd_stats, stats

MODES = ("advantage", "disadvantage")
DIE = 20


def _q(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def stat_id(check: Any) -> Optional[str]:
    """The engine stat for a check name the DM wrote: 'athletics', 'Sleight of Hand',
    'wisdom save', 'strength check', 'initiative'. None when it is not one."""
    if not isinstance(check, str):
        return None
    text = " ".join(check.strip().casefold().replace("_", " ").split())
    if text in ("initiative", "initiative check", "initiative roll"):
        return "initiative"
    for suffix, prefix in (("saving throw", "save"), ("save", "save"), ("skill check", "check"), ("check", "check"), ("roll", "check")):
        if text.endswith(" " + suffix):
            head = text[: -len(suffix) - 1]
            skill = stats.skill_id(head)
            if skill and prefix == "check":
                return "skill:" + skill
            ability = stats.ability_id(head)
            return f"{prefix}:{ability}" if ability else None
    skill = stats.skill_id(text)
    if skill:
        return "skill:" + skill
    ability = stats.ability_id(text)
    return f"check:{ability}" if ability else None


def label(stat: str) -> str:
    """'skill:sleight-of-hand' -> 'Sleight of Hand check'; 'save:wisdom' -> 'Wisdom saving throw'."""
    kind, _, name = stat.partition(":")
    if kind == "skill":
        return stats._display(name) + " check"
    if kind == "save":
        return name.capitalize() + " saving throw"
    if kind == "check":
        return name.capitalize() + " check"
    return "Initiative"


def fresh_seed() -> Tuple[int, int]:
    return int.from_bytes(os.urandom(4), "big") % 1000000 + 1, int.from_bytes(os.urandom(4), "big") % 1000000 + 1


@dataclass
class RollMode:
    """The net roll mode of one stat from the character's conditions, before any dice."""
    mode: str                      # "normal" | "advantage" | "disadvantage" | "fail"
    sources: List[str] = field(default_factory=list)   # condition names, e.g. ["poisoned"]
    reason: Optional[str] = None   # engine unavailable / refused


def combine(requested: Optional[str], conditions: str) -> str:
    """The engine's rule: fail wins; advantage and disadvantage cancel; neither stacks."""
    if conditions == "fail":
        return "fail"
    modes = {m for m in (requested, conditions) if m in MODES}
    if len(modes) == 2:
        return "normal"
    return modes.pop() if modes else "normal"


def faces_needed(mode: str) -> int:
    return 0 if mode == "fail" else 2 if mode in MODES else 1


def net_mode(sheet: Dict[str, Any], stat: str, requested: Optional[str] = None, *,
             binary: Optional[str] = None) -> RollMode:
    """Read the stat's roll mode from a status view (genesis + status, no action) and combine it with the DM's."""
    from core.nql import apply, genesis

    world = genesis.build_world([sheet], "check")
    cid = genesis.character_id(sheet)
    try:
        response = apply.genesis(world.source, status=[cid], binary=binary)
    except apply.EngineUnavailable as error:
        return RollMode(combine(requested, "normal"), reason=str(error))
    if not response.get("ok"):
        return RollMode(combine(requested, "normal"), reason=f"engine refused the world at {response.get('phase')}")
    conditions = "normal"
    sources: List[str] = []
    for status in response.get("status") or []:
        for record in status.get("stats") or []:
            if isinstance(record, dict) and record.get("stat") == stat:
                conditions = record.get("roll") or "normal"
                sources = sorted({str(src.get("type", "")).replace(stats.STATE_PREFIX, "")
                                  for src in record.get("roll_sources") or [] if isinstance(src, dict)})
    return RollMode(combine(requested, conditions), sources)


@dataclass
class CheckResult:
    ok: bool
    stat: str
    character: str
    dc: Optional[int] = None
    requested: Optional[str] = None
    mode: str = "normal"
    sources: List[str] = field(default_factory=list)
    faces: List[int] = field(default_factory=list)
    drawn: bool = False            # the world's dice rolled (no player faces)
    kept: Optional[int] = None
    bonus: Optional[int] = None
    total: Optional[int] = None
    success: Optional[bool] = None
    margin: Optional[int] = None
    reason: Optional[str] = None


def resolve(sheet: Dict[str, Any], stat: str, *, dc: Optional[int] = None, mode: Optional[str] = None,
            faces: Optional[List[int]] = None, binary: Optional[str] = None) -> CheckResult:
    """One `check` action on the sheet's world. Faces are the player's; None lets the world roll."""
    from core.nql import apply, genesis

    world = genesis.build_world([sheet], "check", dice_seed=fresh_seed())
    cid = genesis.character_id(sheet)
    name = str(sheet.get("name", cid))
    parts = [f"check {_q(cid)} stat {_q(stat)} die {DIE}"]
    if dc is not None:
        parts.append(f"against {int(dc)}")
    if mode in MODES:
        parts.append(mode)
    if faces:
        parts.append("faces " + " ".join(str(int(f)) for f in faces))
    action = " ".join(parts) + ";"
    try:
        response = apply.call({"world": world.source, "world_name": "check-genesis.nql", "actions": action,
                               "actions_name": "check.nql", "actor": {"kind": "character", "id": cid},
                               "request": f"check:{os.urandom(8).hex()}"}, binary=binary)
    except apply.EngineUnavailable as error:
        return CheckResult(False, stat, name, dc, mode, reason=str(error))
    if not response.get("ok"):
        fault = response.get("fault") or {}
        detail = fault.get("message") or response.get("diagnostics") or response.get("error")
        if fault.get("code") == "E_ROLL":
            detail = f"{fault.get('message')}: expected {fault.get('expected')}, got {fault.get('actual')}"
        return CheckResult(False, stat, name, dc, mode, reason=f"engine refused the check: {detail}")
    checks = response.get("checks") or []
    if not checks:
        return CheckResult(False, stat, name, dc, mode, reason="engine returned no check result")
    record = checks[-1]
    sources = sorted({str(src.get("type", "")).replace(stats.STATE_PREFIX, "")
                      for src in record.get("roll_sources") or [] if isinstance(src, dict)})
    net = record.get("roll") or (mode if mode in MODES and not sources else "normal")
    if record.get("faces") == [] and record.get("kept") is None:
        net = "fail"
    return CheckResult(True, stat, name, dc, mode, net, sources, list(record.get("faces") or []),
                       bool(record.get("drawn")), record.get("kept"), record.get("bonus"), record.get("total"),
                       record.get("success"), record.get("margin"))


def describe(result: CheckResult) -> str:
    """The one line the DM reads: dice, mode and why, bonus, total, verdict."""
    what = label(result.stat)
    if not result.ok:
        return f"{result.character} {what}: not resolved ({result.reason})"
    why = f" from {', '.join(result.sources)}" if result.sources else (" (situation)" if result.requested in MODES and result.mode == result.requested else "")
    if result.mode == "fail":
        return f"{result.character} {what}" + (f" vs DC {result.dc}" if result.dc is not None else "") + f": automatic failure{why} (no dice)"
    dice = " and ".join(str(f) for f in result.faces)
    how = "the game rolled" if result.drawn else "the player rolled"
    modes = f", {result.mode}{why}, kept {result.kept}" if result.mode in MODES else ""
    if result.requested in MODES and result.sources and result.mode == "normal":
        modes = f" ({result.requested} for the situation and {', '.join(result.sources)} cancel)"
    line = f"{result.character} {what}: {how} {dice}{modes}; {result.kept} {result.bonus:+d} = {result.total}"
    if result.dc is None:
        return line + " (no DC: compare totals)"
    verdict = f"succeeds by {result.margin}" if result.success else f"fails by {-result.margin}"
    return f"{line} vs DC {result.dc}: {verdict}"
