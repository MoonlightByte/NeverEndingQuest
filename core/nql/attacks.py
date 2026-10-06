# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Attack scoring through the rules engine (option 3: NQL X6 + X8).

One `attack` action per swing, in a throwaway per-call world that holds the
typed numbers NEQ already uses: the attacker's to-hit and damage profile, the
target's armor class, hit points and stated damage traits. The engine keeps
the face, scores hit, miss and critical, adds the bonus once, and applies
resistance, vulnerability and immunity. NEQ supplies every face and damage
total (the persisted prerolls, or the player's typed dice); the engine never
draws. The engine's `damage` is the amount NEQ then applies: through CH for a
party sheet (temp HP, concentration), by arithmetic for a monster, as today.

Damage kinds match as exact strings, as today's typed-trait arithmetic
does: the damageType and every trait entry are sent trimmed and casefolded,
so a homebrew type meets a trait that names it exactly. An empty damageType
is sent as `untyped` and no traits are declared, since it meets none today.
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

UNTYPED = "untyped"
MODES = ("advantage", "disadvantage")
MAX_DICE = 64
MAX_SIDES = 1000
ATTACKER = "char:attacker"
TARGET = "char:target"
# Engine treatment words; the journal's #527 trait names are the same words.
TREATMENTS = {"resistance": "resistance", "vulnerability": "vulnerability", "immunity": "immunity"}
_TRAIT_FIELDS = (
    ("damageResistances", "resist"),
    ("damageVulnerabilities", "vulnerable"),
    ("damageImmunities", "immune"),
)


@dataclass
class AttackScore:
    ok: bool
    reason: Optional[str] = None
    kept: Optional[int] = None
    total: Optional[int] = None
    defense: Optional[int] = None
    hit: Optional[bool] = None
    critical: Optional[bool] = None
    raw_damage: Optional[int] = None
    damage_rolled: Optional[int] = None   # the dice total the outcome used
    damage: Optional[int] = None          # after the target's traits; None when nothing was applied
    traits: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def damage_kind(damage_type: Any) -> str:
    """The typed damage kind sent to the engine: the damageType trimmed and
    casefolded, or `untyped` when it is empty."""
    kind = str(damage_type or "").strip().casefold()
    return kind or UNTYPED


def trait_lines(sheet: Any) -> List[str]:
    """`resist`/`vulnerable`/`immune` lines for the sheet's typed damage traits,
    every non-empty entry trimmed and casefolded (exact equality, as today)."""
    lines: List[str] = []
    if not isinstance(sheet, dict):
        return lines
    for field_name, word in _TRAIT_FIELDS:
        seen = set()
        for entry in sheet.get(field_name) or []:
            if not isinstance(entry, str):
                continue
            kind = entry.strip().casefold()
            # The engine refuses an ID holding a control character, which
            # would refuse every swing at this target; such an entry can
            # only meet a kind the engine refuses anyway (today's arithmetic).
            if kind and kind not in seen and not any(unicodedata.category(ch) == "Cc" for ch in kind):
                seen.add(kind)
                lines.append("%s %s;" % (word, _q(kind)))
    return lines


def dice_token(count: int, sides: int, bonus: int) -> str:
    token = "%dd%d" % (count, sides)
    if bonus > 0:
        token += "+%d" % bonus
    elif bonus < 0:
        token += "-%d" % -bonus
    return token


def world(target_ac: int, target_hp: int, target_max_hp: int, target_sheet: Any, typed: bool = True) -> str:
    hp = max(0, int(target_hp))
    cap = max(hp, int(target_max_hp or 0), 1)
    body = ["stat \"ac\" = %d;" % int(target_ac), "resource \"hp\" = %d min 0 max %d;" % (hp, cap)]
    if typed:
        body.extend(trait_lines(target_sheet))
    return "\n".join([
        "rules { transfer unequips; wear any; }",
        "clock \"second\" at 0;",
        "attacks { defense \"ac\"; health \"hp\"; die 20; miss 1; critical 20; critical dice 2; }",
        "location \"loc:combat\" named \"Combat\";",
        "character %s named \"Attacker\" at \"loc:combat\" { }" % _q(ATTACKER),
        "character %s named \"Target\" at \"loc:combat\" { %s }" % (_q(TARGET), " ".join(body)),
        "",
    ])


def action(to_hit: int, count: int, sides: int, bonus: int, kind: str, mode: Optional[str],
           faces: List[int], damage: Optional[int] = None, critical_damage: Optional[int] = None) -> str:
    parts = ["attack %s profile to_hit %d damage %s kind %s against %s"
             % (_q(ATTACKER), int(to_hit), dice_token(count, sides, bonus), _q(kind), _q(TARGET))]
    if mode in MODES:
        parts.append(mode)
    parts.append("faces " + " ".join(str(int(face)) for face in faces))
    if damage is not None:
        parts.append("damage %d" % int(damage))
    if critical_damage is not None:
        parts.append("critical damage %d" % int(critical_damage))
    return " ".join(parts) + ";"


def score(*, to_hit: int, count: int, sides: int, bonus: int, damage_type: Any, mode: Optional[str],
          faces: List[int], target_ac: int, target_hp: int, target_max_hp: int, target_sheet: Any = None,
          damage: Optional[int] = None, critical_damage: Optional[int] = None,
          binary: Optional[str] = None) -> AttackScore:
    """One swing through the engine. With no damage total the swing is only scored."""
    from core.nql import apply

    if not (1 <= int(count) <= MAX_DICE and 1 <= int(sides) <= MAX_SIDES):
        return AttackScore(False, reason="damage dice %dd%d outside the engine's bounds" % (count, sides))
    if len(faces) != (2 if mode in MODES else 1):
        return AttackScore(False, reason="face count %d does not match mode %s" % (len(faces), mode))
    try:
        response = apply.call({
            "world": world(target_ac, target_hp, target_max_hp, target_sheet,
                           typed=bool(str(damage_type or "").strip())),
            "world_name": "attack-genesis.nql",
            "actions": action(to_hit, count, sides, bonus, damage_kind(damage_type), mode, faces,
                              damage, critical_damage),
            "actions_name": "attack.nql",
            "actor": {"kind": "character", "id": ATTACKER},
            "request": "attack:%s" % os.urandom(8).hex(),
        }, binary=binary)
    except apply.EngineUnavailable as error:
        return AttackScore(False, reason=str(error))
    if not response.get("ok"):
        fault = response.get("fault") or {}
        detail = fault or response.get("diagnostics") or response.get("error")
        return AttackScore(False, reason="engine refused the attack: %s" % (detail,))
    records = response.get("attacks") or []
    if not records or not isinstance(records[-1], dict):
        return AttackScore(False, reason="engine returned no attack result")
    record: Dict[str, Any] = records[-1]
    raw = record.get("raw_damage")
    result = AttackScore(
        True,
        kept=record.get("kept"),
        total=record.get("total"),
        defense=record.get("defense"),
        hit=bool(record.get("hit")),
        critical=bool(record.get("critical")),
        raw_damage=max(0, int(raw)) if raw is not None else None,
        damage_rolled=record.get("damage_rolled"),
        damage=record.get("damage"),
    )
    found = {TREATMENTS.get((treatment or {}).get("treatment")) for treatment in record.get("treatments") or []}
    # The journal's #527 order and shape: immunity alone, else resistance
    # then vulnerability, each once.
    result.traits = (["immunity"] if "immunity" in found
                     else [name for name in ("resistance", "vulnerability") if name in found])
    if result.hit and result.raw_damage is not None and result.damage is None:
        result.damage = 0
    if result.raw_damage is not None and result.raw_damage <= 0:
        # Today's journal names no trait when nothing was dealt (#527).
        result.traits = []
    return result
