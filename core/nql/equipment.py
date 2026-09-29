# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Equipment deltas through the engine (seam S3).

T079 proposes a sheet delta; after the delta is merged, ``reconcile`` compares
the equipment before and after and turns every difference into engine
operations on a world built from the sheet before the change: ``equip`` and
``unequip`` for the equipped flag, ``consume`` for a smaller stock or a removed
item, ``create item`` for a new item. The engine decides legality (slots, hands,
one shield, stock) and commits once; the sheet's equipment is then rewritten
from its facts, metadata coming from the merged entries.

A refusal is returned with the engine's reason so the caller can hand it back
to the model as feedback. Nothing here parses prose or computes a stat.

Not modelled by the engine (left as the merged value and reported in ``gaps``):
(nothing: a larger stock of an existing item is an ``add`` since engine ae3ad48).
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import apply, genesis


@dataclass
class EquipmentOutcome:
    ok: bool
    equipment: Optional[List[Dict[str, Any]]] = None
    operations: List[str] = field(default_factory=list)
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    fault: Optional[Dict[str, Any]] = None
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return genesis._q(value)


def _stock(entry: Dict[str, Any]) -> int:
    return entry["quantity"] if type(entry.get("quantity")) is int else 1


def _index_by_id(sheet: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {e["nql_id"]: e for e in sheet.get("equipment") or []
            if isinstance(e, dict) and isinstance(e.get("nql_id"), str)}


def reconcile(before: Dict[str, Any], after: Dict[str, Any], *, location: str = "sheet",
              binary: Optional[str] = None) -> EquipmentOutcome:
    """Return the engine-reconciled equipment list for ``after``, or a refusal.

    ``before`` is the sheet as stored; ``after`` is the same sheet with the T079
    delta merged (by item name, as the legacy merge does). Entries keep their
    ``nql_id`` through the merge; entries only in ``after`` are new items.
    """
    before = copy.deepcopy(before)
    after = copy.deepcopy(after)
    genesis.assign_ids(before)
    # Carry ids into the merged entries by exact name for entries that have none
    # (the T079 delta never carries nql_id), then mint for genuinely new ones.
    by_name = {}
    for e in before.get("equipment") or []:
        if isinstance(e, dict) and e.get("item_name") and e.get("item_name") not in by_name:
            by_name[e["item_name"]] = e["nql_id"]
    for e in after.get("equipment") or []:
        if isinstance(e, dict) and not isinstance(e.get("nql_id"), str) and e.get("item_name") in by_name:
            e["nql_id"] = by_name[e["item_name"]]
    genesis.assign_ids(after)

    cid = genesis.character_id(before)
    old = _index_by_id(before)
    new = _index_by_id(after)
    created = [(iid, e) for iid, e in new.items() if iid not in old]
    world = genesis.build_world([before], location, definition_entries=created)
    ops: List[str] = []
    gaps: List[str] = list(world.gaps)

    # Removed or reduced stock: consume. Increased stock: add (refill, loot, purchase).
    for iid, e in old.items():
        if iid not in new:
            ops.append(f"consume {_q(iid)} from {_q(cid)} by {_stock(e)};")
            continue
        delta = _stock(new[iid]) - _stock(e)
        if delta < 0:
            if e.get("equipped") is True and new[iid].get("equipped") is not False:
                ops.append(f"unequip {_q(iid)};")
            ops.append(f"consume {_q(iid)} from {_q(cid)} by {-delta};")
        elif delta > 0:
            ops.append(f"add {_q(iid)} to {_q(cid)} by {delta};")
    # New items: create, then equip if the merged entry says so.
    for iid, e in created:
        fields = [f"owner {_q(cid)};", f"custody character {_q(cid)};"]
        if _stock(e) != 1:
            fields.append(f"quantity {_stock(e)};")
        if e.get("item_type") == "armor" and type(e.get("ac_base")) is int or e.get("armor_category") == "shield":
            fields.append(f"definition {_q('gear:' + iid.split(':', 1)[1])};")
        elif e.get("item_type") == "weapon":
            fields.append('definition "gear:held";')
        elif e.get("equipped") is True:
            fields.append('definition "gear:worn";')
        ops.append(f"create item {_q(iid)} named {_q(e.get('item_name', ''))} {{ {' '.join(fields)} }};")
    # Equipped flag changes on items that exist before and after.
    for iid, e in new.items():
        if iid not in old or _stock(e) <= 0:
            continue
        was = old[iid].get("equipped") is True
        now = e.get("equipped") is True
        if now and not was:
            ops.append(f"equip {_q(iid)} on {_q(cid)};")
        elif was and not now and _stock(e) >= _stock(old[iid]):
            ops.append(f"unequip {_q(iid)};")
    for iid, e in created:
        if e.get("equipped") is True:
            ops.append(f"equip {_q(iid)} on {_q(cid)};")

    if not ops:
        return EquipmentOutcome(True, equipment=after.get("equipment"), gaps=gaps)

    try:
        response = apply.call({"world": world.source, "world_name": "equipment-genesis.nql",
                               "actions": "\n".join(ops), "actions_name": "equipment.nql",
                               "actor": {"kind": "character", "id": cid},
                               "request": f"equipment:{uuid.uuid4().hex}",
                               "items_at": [{"kind": "character", "id": cid}]}, binary=binary)
    except apply.EngineUnavailable as error:
        return EquipmentOutcome(False, operations=ops, reason=str(error), gaps=gaps)
    if not response.get("ok"):
        fault = response.get("fault")
        detail = response.get("diagnostics") or fault or response.get("error")
        return EquipmentOutcome(False, operations=ops, fault=fault,
                                reason=f"engine refused at {response.get('phase')}: {detail}", gaps=gaps)

    views = {v["at"]["id"]: v["items"] for v in response.get("items_at", [])}
    result: List[Dict[str, Any]] = []
    tracked = set()
    for item in views.get(cid, []):
        iid = item["id"]
        base = new.get(iid) or old.get(iid)
        if base is None:
            continue
        tracked.add(iid)
        stock = item.get("quantity", 1) if type(item.get("quantity")) is int else 1
        if stock <= 0:
            continue
        entry = copy.deepcopy(base)
        entry["nql_id"] = iid
        entry["quantity"] = stock
        entry["equipped"] = item.get("wearer") == cid
        result.append(entry)
    for e in after.get("equipment") or []:
        if isinstance(e, dict) and e.get("nql_id") not in tracked and e.get("nql_id") not in old:
            result.append(e)   # untracked by the engine (no name); keep the merged entry
    return EquipmentOutcome(True, equipment=result, operations=ops, receipt=response.get("receipt"), gaps=gaps)
