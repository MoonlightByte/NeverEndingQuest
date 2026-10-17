# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Hands after a swing (NUM-B, owner answers BQ1-BQ3).

The model's swing always stands: nothing here refuses an attack or filters
legal actions. After a character's swing, ``after_swing`` asks the engine
which option the swung row belongs to (``attack_options``, matched by the
engine grant's exact name) and returns a typed record for the event:

- a worn option: ``{"row", "item", "mode", "worn": true}``;
- a carried option: ``worn`` false and ``fitsNow`` from the equipment view's
  slot occupancy (slots in use, less the item's own worn mode, plus the
  option's, within capacity), as startup marks rows (NUM-H3c);
  - BQ1 (A): when it fits, one non-thrown unit swung in its definition's
    default mode is drawn: the equip is checked by the engine
    (``equipment.reconcile``, which equips in the default mode) and recorded
    as ``draw: {"index", "item_name", "equippedAfter": true}``, which
    ``resolver.apply_resolution`` applies (an absolute value, so a replay
    is a no-op). Otherwise ``notDrawn`` holds a code and ``notDrawnDetail``
    the reason: "no_sheet_row", "sheet_equipped" (the sheet has no mode
    field), "mode" (not the default mode), "thrown" (the weapon leaves the
    hand), "stack" (the engine wears exactly one) or "refused" (the engine);
  - BQ2 (A): when it does not fit, the record says so and nothing changes.
- BQ3 (A): a row with no engine option (author rows, older heroes) gets no
  record (None).

Rows carry no grant id, so a row is matched by the grant's exact name; when
several options list that name (two Daggers), the worn option is preferred,
then the first in the engine's item-id order.

The engine being unavailable is not a fault in the fight: None.

R3 (the Off-hand Attack, SRD 5.2.1 p89 Light): ``light_melee_rows`` lists the
attack rows of the Light melee weapons in hand (worn engine options), each with
its items and the ability modifier its damage adds (the grant's typed recipe).
"""
import copy
from typing import Any, Dict, List, Optional, Tuple

from core.nql import apply, equipment, genesis, item_catalog

LOCATION = "Combat"


def _fits(option: Dict[str, Any], own: List[Dict[str, Any]], occupancy: Dict[str, Tuple[int, int]]) -> bool:
    freed = {str(s.get("slot")): int(s.get("amount") or 0) for s in own or []}
    for need in option.get("slots") or []:
        slot = str(need.get("slot"))
        used, capacity = occupancy.get(slot, (0, 0))
        if used - freed.get(slot, 0) + int(need.get("amount") or 0) > capacity:
            return False
    return True


def _option_for(response: Dict[str, Any], row_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List]:
    """(option, the grant named ``row_name``, the item's worn slots) or (None, None, []).

    The worn option wins; otherwise the first in the engine's item-id order."""
    found = []
    for view in response.get("attack_options") or []:
        options = view.get("options") or []
        for option in options:
            for grant in option.get("grants") or []:
                if isinstance(grant, dict) and grant.get("name") == row_name:
                    found.append((option, grant, options))
    if not found:
        return None, None, []
    option, grant, options = next((f for f in found if f[0].get("worn") is True), found[0])
    own = [o.get("slots") for o in options if o.get("item") == option.get("item") and o.get("worn") is True]
    return option, grant, (own[0] if own else [])


def two_handed(sheet: Dict[str, Any], row_name: str, *, binary: Optional[str] = None) -> Optional[bool]:
    """Whether the engine option for the row ``row_name`` occupies two hands (#879:
    a Two-Handed weapon, or a Versatile one in its two-handed mode); None when the
    row has no engine option or the engine is unavailable. The option is matched as
    ``after_swing`` matches it (the grant's exact name, the worn option first)."""
    if not isinstance(sheet, dict) or not row_name:
        return None
    world = genesis.build_world([copy.deepcopy(sheet)], LOCATION)
    cid = genesis.character_id(sheet)
    try:
        response = apply.call({"world": world.source, "world_name": "hands.nql", "attack_options": [cid]},
                              binary=binary)
    except apply.EngineUnavailable:
        return None
    if not response.get("ok"):
        return None
    option, _grant, _own = _option_for(response, row_name)
    if option is None:
        return None
    return any(str(s.get("slot")) == "hand" and int(s.get("amount") or 0) == 2
               for s in option.get("slots") or [] if isinstance(s, dict))


def _not_drawn(record: Dict[str, Any], code: str, detail: str) -> Dict[str, Any]:
    record["notDrawn"] = code
    record["notDrawnDetail"] = detail
    return record


def after_swing(sheet: Dict[str, Any], row_name: str, *, binary: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The typed hands record for a swing with the row ``row_name``, or None."""
    if not isinstance(sheet, dict) or not row_name:
        return None
    world = genesis.build_world([copy.deepcopy(sheet)], LOCATION)
    cid = genesis.character_id(sheet)
    try:
        response = apply.call({"world": world.source, "world_name": "hands.nql", "equipment": [cid],
                               "attack_options": [cid]}, binary=binary)
    except apply.EngineUnavailable:
        return None
    if not response.get("ok"):
        return None
    option, grant, own = _option_for(response, row_name)
    if option is None:
        return None  # BQ3 (A): not an engine row
    record: Dict[str, Any] = {"row": row_name, "item": option.get("item"), "mode": option.get("mode"),
                              "worn": option.get("worn") is True}
    if record["worn"]:
        return record
    occupancy = {}
    default_mode = None
    for view in response.get("equipment") or []:
        for slot in view.get("slots") or []:
            occupancy[str(slot.get("slot"))] = (int(slot.get("used") or 0), int(slot.get("capacity") or 0))
        for entry in view.get("items") or []:
            if (entry.get("item") or {}).get("id") == option.get("item"):
                default_mode = (entry.get("definition") or {}).get("default_mode")
    record["fitsNow"] = _fits(option, own, occupancy)
    if not record["fitsNow"]:
        return record  # BQ2 (A): recorded only
    index = next((i for i, iid in (world.item_ids.get(cid) or {}).items() if iid == option.get("item")), None)
    rows = sheet.get("equipment") or []
    if index is None or not 0 <= index < len(rows):
        return _not_drawn(record, "no_sheet_row", "the item has no sheet row")
    row = rows[index]
    if row.get("equipped") is True:
        return _not_drawn(record, "sheet_equipped", "the sheet already marks it equipped (the sheet has no mode field)")
    if not default_mode or option.get("mode") != default_mode:
        return _not_drawn(record, "mode", "swung %s; a draw equips the default mode %s" % (option.get("mode"), default_mode))
    if isinstance(grant.get("thrown"), dict):
        return _not_drawn(record, "thrown", "a thrown swing: the weapon leaves the hand")
    if type(row.get("quantity")) is int and row["quantity"] != 1:
        return _not_drawn(record, "stack", "a stack of %d: the engine wears exactly one" % row["quantity"])
    after = copy.deepcopy(sheet)
    after["equipment"][index]["equipped"] = True
    outcome = equipment.reconcile(sheet, after, location=LOCATION, binary=binary)
    if not outcome.ok:
        return _not_drawn(record, "refused", "the engine refused the draw: %s" % outcome.reason)
    record["draw"] = {"index": index, "item_name": row.get("item_name"), "equippedAfter": True}
    return record


def light_melee_definition(definition: Any) -> bool:
    """Whether the engine definition (gear:srd/<slug>) is a catalog Melee weapon
    with the Light property (typed catalog data)."""
    for entry in item_catalog.weapon_entries():
        if entry.get("equipment") == definition:
            weapon = entry["weapon"]
            return weapon.get("kind") == "Melee" and any(
                isinstance(p, dict) and p.get("name") == "Light" for p in weapon.get("properties") or [])
    return False


def _ability_modifier(grant: Dict[str, Any], stat: Any) -> int:
    """The active term of the grant's damage recipe that reads ``stat``."""
    total = 0
    for term in (grant.get("bonus_recipe") or {}).get("terms") or []:
        if isinstance(term, dict) and term.get("active") is True and (term.get("term") or {}).get("stat") == stat:
            try:
                total += int(str(term.get("exact")))
            except ValueError:
                pass
    return total


def light_melee_rows(sheet: Dict[str, Any], *, binary: Optional[str] = None) -> Optional[Dict[str, Dict[str, Any]]]:
    """R3: {row name: {"items": [item ids], "ability", "abilityModifier"}} for the
    melee grants of the Light melee weapons in hand (worn options), matched by
    the grant's exact name as ``after_swing`` matches rows; None when the engine
    is unavailable or refuses."""
    if not isinstance(sheet, dict):
        return None
    world = genesis.build_world([copy.deepcopy(sheet)], LOCATION)
    cid = genesis.character_id(sheet)
    try:
        response = apply.call({"world": world.source, "world_name": "hands.nql", "attack_options": [cid]},
                              binary=binary)
    except apply.EngineUnavailable:
        return None
    if not response.get("ok"):
        return None
    rows: Dict[str, Dict[str, Any]] = {}
    for view in response.get("attack_options") or []:
        for option in view.get("options") or []:
            if option.get("worn") is not True or not light_melee_definition(option.get("definition")):
                continue
            for grant in option.get("grants") or []:
                if not isinstance(grant, dict) or not isinstance(grant.get("melee"), dict) or not grant.get("name"):
                    continue
                stat = grant["melee"].get("stat")
                row = rows.setdefault(grant["name"], {"items": [], "ability": stat,
                                                      "abilityModifier": _ability_modifier(grant, stat)})
                if option.get("item") not in row["items"]:
                    row["items"].append(option.get("item"))
    return rows
