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
"""
import copy
from typing import Any, Dict, List, Optional, Tuple

from core.nql import apply, equipment, genesis

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
