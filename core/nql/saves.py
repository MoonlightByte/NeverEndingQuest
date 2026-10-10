# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Spell saves through the rules engine (#703: NQL `save`, engine 6fe468f).

One `save` action per target, in a throwaway per-call world with the
`attacks` law. NEQ sends the typed numbers from its data: the save ability,
the DC, the spell's damage dice and kind, and what a successful save does to
the damage (`half` or `none`, from data/srd_spell_saves.json, never from a
model's wording). NEQ supplies every face and the damage total; the engine
never draws. It keeps the face the target's roll mode needs, decides the
save, applies the effect and then the target's damage traits.

The engine's `damage` is only read: NEQ then applies it as today, through CH
for a party sheet (temporary hit points, concentration) and by arithmetic for
a monster. A party target's world is its genesis world (its save totals and
the conditions' roll modes, as the C2a save check) without its concentration
instance, which CH owns; a monster's world holds its save bonus, hit points
and typed damage traits, as the attack worlds do.
"""
from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import attacks

SUCCESS_EFFECTS = ("half", "none")
SOURCE = "char:save-source"
TARGET = attacks.TARGET
LOCATION = "loc:combat"


@dataclass
class SaveScore:
    ok: bool
    reason: Optional[str] = None
    stat: Optional[str] = None
    faces: List[int] = field(default_factory=list)      # the faces the roll mode took
    unused_faces: List[int] = field(default_factory=list)
    mode: str = "normal"                                  # normal | advantage | disadvantage | fail
    sources: List[str] = field(default_factory=list)      # the conditions behind the mode
    kept: Optional[int] = None
    bonus: Optional[int] = None
    total: Optional[int] = None
    success: Optional[bool] = None
    margin: Optional[int] = None
    effect: Optional[str] = None                          # full | half | none
    damage_rolled: Optional[int] = None
    damage: Optional[int] = None                          # after the effect and the traits; None when nothing was sent
    traits: List[str] = field(default_factory=list)


def stat_id(ability: Any) -> Optional[str]:
    """`save:<ability>` for a full SRD ability name, else None."""
    from core.nql import stats

    ability_name = stats.ability_id(str(ability or "").strip().lower())
    return "save:" + ability_name if ability_name else None


def monster_world(stat: str, save_bonus: int, target_hp: int, target_max_hp: int, target_sheet: Any) -> str:
    hp = max(0, int(target_hp))
    cap = max(hp, int(target_max_hp or 0), 1)
    body = ['stat "ac" = 10;', "stat %s = %d;" % (attacks._q(stat), int(save_bonus)),
            'resource "hp" = %d min 0 max %d;' % (hp, cap)]
    body.extend(attacks.trait_lines(target_sheet))
    return "\n".join([
        "rules { transfer unequips; wear any; }",
        'clock "second" at 0;',
        'attacks { defense "ac"; health "hp"; die 20; miss 1; critical 20; critical dice 2; }',
        'location "%s" named "Combat";' % LOCATION,
        'character %s named "Source" at "%s" { }' % (attacks._q(SOURCE), LOCATION),
        'character %s named "Target" at "%s" { %s }' % (attacks._q(TARGET), LOCATION, " ".join(body)),
        "",
    ])


def party_world(sheet: Dict[str, Any]) -> Tuple[str, str, str]:
    """(world, target id, source id): the sheet's genesis world with the attacks
    law and its traits, no concentration instance, and a bare source."""
    from core.nql import genesis, stats

    working = deepcopy(sheet)
    working.pop(stats.CONCENTRATION_FIELD, None)
    built = genesis.build_world([working], "combat", damage_traits=True)
    target = genesis.character_id(working)
    source = SOURCE if target != SOURCE else SOURCE + "-2"
    text = built.source.rstrip("\n") + "\ncharacter %s named \"Source\" at %s { }\n" % (
        attacks._q(source), attacks._q(built.location))
    return text, target, source


def action(source: str, stat: str, dc: int, count: int, sides: int, bonus: int, kind: str,
           success: str, target: str, faces: List[int], damage: Optional[int] = None) -> str:
    parts = ["save %s profile stat %s dc %d damage %s kind %s success %s against %s"
             % (attacks._q(source), attacks._q(stat), int(dc), attacks.dice_token(count, sides, bonus),
                attacks._q(kind), success, attacks._q(target))]
    if faces:
        parts.append("faces " + " ".join(str(int(face)) for face in faces))
    if damage is not None:
        parts.append("damage %d" % int(damage))
    return " ".join(parts) + ";"


def score(*, ability: Any, dc: int, count: int, sides: int, bonus: int = 0, damage_type: Any,
          success: str, faces: List[int], damage: Optional[int] = None,
          party_sheet: Optional[Dict[str, Any]] = None, save_bonus: Optional[int] = None,
          target_hp: int = 0, target_max_hp: int = 0, target_sheet: Any = None,
          binary: Optional[str] = None) -> SaveScore:
    """One target's save through the engine. A party target passes its sheet
    (`party_sheet`); a monster passes its `save_bonus`, hit points and the
    sheet holding its damage traits. With no damage total the save is only
    scored. Any refusal returns ok False and the caller keeps its arithmetic."""
    from core.nql import apply, stats

    stat = stat_id(ability)
    if stat is None:
        return SaveScore(False, reason="no SRD ability %r" % (ability,))
    if success not in SUCCESS_EFFECTS:
        return SaveScore(False, reason="success effect %r is not half or none" % (success,))
    if not (1 <= int(count) <= attacks.MAX_DICE and 1 <= int(sides) <= attacks.MAX_SIDES):
        return SaveScore(False, reason="damage dice %dd%d outside the engine's bounds" % (count, sides))
    if len(faces) > 2:
        # None for an automatic failure, one or two otherwise; the engine
        # refuses too few for the target's roll mode (E_ROLL).
        return SaveScore(False, reason="%d save faces (at most 2 are sent)" % len(faces))
    if party_sheet is not None:
        world_text, target, source = party_world(party_sheet)
    elif save_bonus is not None:
        world_text, target, source = (monster_world(stat, save_bonus, target_hp, target_max_hp, target_sheet),
                                      TARGET, SOURCE)
    else:
        return SaveScore(False, reason="no party sheet and no save bonus")
    try:
        response = apply.call({
            "world": world_text,
            "world_name": "save-genesis.nql",
            "actions": action(source, stat, dc, count, sides, bonus, attacks.damage_kind(damage_type),
                              success, target, faces, damage),
            "actions_name": "save.nql",
            "actor": {"kind": "character", "id": source},
            "request": "save:%s" % os.urandom(8).hex(),
        }, binary=binary)
    except apply.EngineUnavailable as error:
        return SaveScore(False, reason=str(error), stat=stat)
    if not response.get("ok"):
        fault = response.get("fault") or {}
        detail = fault or response.get("diagnostics") or response.get("error")
        return SaveScore(False, reason="engine refused the save: %s" % (detail,), stat=stat)
    records = response.get("saves") or []
    if not records or not isinstance(records[-1], dict) or not isinstance(records[-1].get("check"), dict):
        return SaveScore(False, reason="engine returned no save result", stat=stat)
    record: Dict[str, Any] = records[-1]
    check = record["check"]
    taken = list(check.get("faces") or [])
    mode = check.get("roll") or "normal"
    if not taken and check.get("kept") is None:
        mode = "fail"
    result = SaveScore(
        True,
        stat=stat,
        faces=taken,
        unused_faces=list(record.get("unused_save_faces") or []),
        mode=mode,
        sources=sorted({str(src.get("type", "")).replace(stats.STATE_PREFIX, "")
                        for src in check.get("roll_sources") or [] if isinstance(src, dict)}),
        kept=check.get("kept"),
        bonus=check.get("bonus"),
        total=check.get("total"),
        success=bool(check.get("success")),
        margin=check.get("margin"),
        effect=record.get("effect"),
        damage_rolled=record.get("damage_rolled"),
        damage=record.get("damage"),
    )
    result.traits = attacks.journal_traits(record.get("treatments"))
    if damage is not None and result.damage is None:
        # A saved `none`, or damage the traits brought to nothing: 0 is applied.
        result.damage = 0
    raw = record.get("raw_damage")
    if result.effect == "none" or raw is None or int(raw) <= 0:
        # Today's journal names no trait when nothing was dealt (#527).
        result.traits = []
    return result


def describe(result: SaveScore, name: str, dc: int) -> str:
    """The one line the DM reads, in the C2a check line's words."""
    what = (result.stat or "save:?").split(":", 1)[1].capitalize() + " saving throw"
    if not result.ok:
        return "%s %s: not resolved (%s)" % (name, what, result.reason)
    why = " from %s" % ", ".join(result.sources) if result.sources else ""
    if result.mode == "fail":
        return "%s %s vs DC %d: automatic failure%s (no dice)" % (name, what, int(dc), why)
    dice = " and ".join(str(face) for face in result.faces)
    modes = ", %s%s, kept %s" % (result.mode, why, result.kept) if result.mode in attacks.MODES else ""
    verdict = "succeeds by %d" % result.margin if result.success else "fails by %d" % -result.margin
    return "%s %s: rolled %s%s; %s %+d = %s vs DC %d: %s" % (
        name, what, dice, modes, result.kept, result.bonus, result.total, int(dc), verdict)
