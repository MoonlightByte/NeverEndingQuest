# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Temporary effects through the engine (E12a): the numbers.

A live effect (authoredBy classifier or engine) whose modifiers change armor
class or the hit point maximum is held by the engine as a condition instance:
a stat modifier on ``defense`` or a maximum modifier on ``hp``. Once the engine
has applied it, the sheet stores the engine's values (armorClass, maxHitPoints,
hitPoints) and the effect carries ``engineOwned: true`` and, when timed, its
``expiresTick``. The read-time overlay then leaves those two numbers alone.

``reconcile`` is the one request: every engineOwned effect still on the sheet
is declared as an instance the engine takes as already applied (guide step 4);
the effects the caller just removed are declared too and then ended with
``remove condition`` so the engine lowers the maximum and clamps hit points;
every live effect not yet engineOwned is applied with ``apply condition``. An
effect's ``onApply``/``onRemove`` hit point changes are ``heal``/``damage``
lines in the same request, after the condition line they belong to, so a heal
can use the room a raised maximum gives. Nothing is computed here.

Fail-forward: when the engine is unavailable or refuses, the sheet is returned
unchanged with a reason. A not-yet-owned effect is then still rendered by the
overlay; for an owned effect that was removed, ``fallback_unbake`` takes its
numbers off the stored fields so the sheet never keeps a bonus that ended.
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.nql import apply, armor_class, genesis, resources


@dataclass
class EffectsOutcome:
    ok: bool
    sheet: Optional[Dict[str, Any]] = None
    applied: List[str] = field(default_factory=list)   # effect names the engine now holds
    ended: List[str] = field(default_factory=list)     # effect names the engine ended
    operations: List[str] = field(default_factory=list)
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return genesis._q(value)


def pending_effects(sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Live effects the engine can hold that it does not hold yet."""
    return [e for e in genesis.live_effects(sheet)
            if e.get(genesis.EFFECT_ENGINE_OWNED) is not True and genesis.effect_engine_modifiers(e)]


def owned_effects(sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [e for e in genesis.live_effects(sheet)
            if e.get(genesis.EFFECT_ENGINE_OWNED) is True and genesis.effect_engine_modifiers(e)]


def _hp_lines(cid: str, operations: Any, sheet: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    if "hitPoints" not in sheet:
        return out
    for operation in operations or []:
        if not isinstance(operation, dict) or operation.get("stat") != "hitPoints":
            continue
        delta = operation.get("delta")
        if type(delta) is not int or delta == 0:
            continue
        verb = "heal" if delta > 0 else "damage"
        out.append(f'{verb} {_q(cid)} resource "hp" by {abs(delta)};')
    return out


def _expires_tick(effect: Dict[str, Any]) -> Optional[int]:
    expiration = effect.get("expiration")
    if not isinstance(expiration, str) or not expiration.strip():
        return None
    from core.effects.clock import scalar_from_display_iso
    try:
        return int(scalar_from_display_iso(expiration))
    except ValueError:
        return None


def reconcile(sheet: Dict[str, Any], removed: Optional[List[Dict[str, Any]]] = None, *,
              location: str = "sheet", request_id: Optional[str] = None,
              binary: Optional[str] = None) -> EffectsOutcome:
    """Hold the sheet's pending effects in the engine and end the removed ones.

    ``removed`` are effect records no longer on the sheet whose numbers are
    still inside its stored fields (they were engineOwned). Returns the sheet
    with the engine's values, or ``ok`` false and the sheet untouched. Makes no
    engine call when there is nothing to apply or end.
    """
    sheet = copy.deepcopy(sheet)
    cid = genesis.character_id(sheet)
    ending = [e for e in removed or [] if isinstance(e, dict)
              and e.get(genesis.EFFECT_ENGINE_OWNED) is True and genesis.effect_engine_modifiers(e)]
    applying = pending_effects(sheet)
    if not ending and not applying:
        return EffectsOutcome(True, sheet=sheet)
    world_sheet = copy.deepcopy(sheet)
    world_sheet["temporaryEffects"] = list(sheet.get("temporaryEffects") or []) + [copy.deepcopy(e) for e in ending]
    world = genesis.build_world([world_sheet], location)
    gaps = list(world.gaps)
    ops: List[str] = []
    for effect in ending:
        ops.append(f'remove condition {_q(genesis.effect_instance_id(effect))} from {_q(cid)};')
        ops.extend(_hp_lines(cid, effect.get("onRemove"), sheet))
    for effect in applying:
        ops.append(f'apply condition {_q(genesis.effect_instance_id(effect))} of {_q(genesis.effect_type_id(effect))} to {_q(cid)};')
        ops.extend(_hp_lines(cid, effect.get("onApply"), sheet))
    try:
        response = apply.call({"world": world.source, "world_name": "effects-genesis.nql",
                               "actions": "\n".join(ops), "actions_name": "effects.nql",
                               "actor": {"kind": "character", "id": cid},
                               "request": request_id or f"effects:{uuid.uuid4().hex}",
                               "status": [cid],
                               "explain": [{"character": cid, "stat": "defense"}]}, binary=binary)
    except apply.EngineUnavailable as error:
        return EffectsOutcome(False, reason=str(error), operations=ops, gaps=gaps)
    if not response.get("ok"):
        detail = response.get("diagnostics") or response.get("fault") or response.get("error")
        return EffectsOutcome(False, reason=f"engine refused at {response.get('phase')}: {detail}",
                              operations=ops, gaps=gaps)
    statuses = [s for s in response.get("status") or []
                if isinstance(s.get("character"), dict) and s["character"].get("id") == cid]
    explanations = response.get("explain") or []
    if not statuses or len(explanations) != 1 or type(explanations[0].get("effective")) is not int:
        return EffectsOutcome(False, reason="engine returned no status or defense explanation",
                              operations=ops, gaps=gaps)
    status = statuses[0]
    problem = resources._write_back(sheet, status)
    if problem:
        return EffectsOutcome(False, reason=problem, operations=ops, gaps=gaps)
    hp = (status.get("resources") or {}).get("hp")
    if "maxHitPoints" in sheet and isinstance(hp, dict) and type(hp.get("maximum")) is int:
        sheet["maxHitPoints"] = hp["maximum"]
    explanation = explanations[0]
    names = dict(world.effect_names)
    for index, item_id in (world.item_ids.get(cid) or {}).items():
        entry = (sheet.get("equipment") or [])[index]
        names[item_id] = str(entry.get("item_name", item_id))
    sheet["armorClass"] = explanation["effective"]
    kept = [e for e in sheet.get("equipment_effects") or []
            if not (isinstance(e, dict) and e.get("target") == armor_class.AC_TARGET)]
    sheet["equipment_effects"] = kept + armor_class._ac_entries(explanation, names)
    applied_ids = {e.get("effectId") for e in applying}
    for effect in sheet.get("temporaryEffects") or []:
        if isinstance(effect, dict) and effect.get("effectId") in applied_ids:
            effect[genesis.EFFECT_ENGINE_OWNED] = True
            tick = _expires_tick(effect)
            if tick is not None:
                effect[genesis.EFFECT_EXPIRES_TICK] = tick
    return EffectsOutcome(True, sheet=sheet, applied=[str(e.get("name")) for e in applying],
                          ended=[str(e.get("name")) for e in ending], operations=ops,
                          receipt=response.get("receipt"), gaps=gaps)


def fallback_unbake(sheet: Dict[str, Any], removed: List[Dict[str, Any]]) -> List[str]:
    """Take ended engineOwned effects off the stored numbers without the engine.

    Used only when ``reconcile`` could not run: the sheet must not keep a bonus
    whose effect is gone. Mirrors the engine's ending rule (maximum down, hit
    points clamped, never a symmetric loss). Returns the names handled.
    """
    handled: List[str] = []
    for effect in removed or []:
        if not (isinstance(effect, dict) and effect.get(genesis.EFFECT_ENGINE_OWNED) is True):
            continue
        modifiers = genesis.effect_engine_modifiers(effect)
        if not modifiers:
            continue
        for kind, amount in modifiers:
            if kind == "defense" and type(sheet.get("armorClass")) is int:
                sheet["armorClass"] -= amount
            elif kind == "hp-max" and type(sheet.get("maxHitPoints")) is int:
                sheet["maxHitPoints"] = max(0, sheet["maxHitPoints"] - amount)
        for operation in effect.get("onRemove") or []:
            if isinstance(operation, dict) and operation.get("stat") == "hitPoints" \
                    and type(operation.get("delta")) is int and type(sheet.get("hitPoints")) is int:
                sheet["hitPoints"] = max(0, sheet["hitPoints"] + operation["delta"])
        if type(sheet.get("hitPoints")) is int and type(sheet.get("maxHitPoints")) is int:
            sheet["hitPoints"] = min(sheet["hitPoints"], sheet["maxHitPoints"])
        handled.append(str(effect.get("name")))
    return handled
