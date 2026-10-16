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

The engine wears exactly one unit (#1135): equipping a stack splits one unit
off and equips that part in the same request, and the part's row follows its
parent's. Unequipping a single worn unit folds it back into a carried stack of
the same typed identity, so a drawn and sheathed dagger leaves one row.

A refusal is returned with the engine's reason so the caller can hand it back
to the model as feedback. Nothing here parses prose or computes a stat.

Not modelled by the engine (left as the merged value and reported in ``gaps``):
(nothing: a larger stock of an existing item is an ``add`` since engine ae3ad48).
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import apply, genesis, item_catalog, transfer


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


def _refusal_reason(before, old, new, fault):
    """The reason for an engine E_QUANTITY refusal of an item held before and
    after: a shortage when its stock was used or lost, otherwise the engine's
    own typed rule (``expected``/``actual``). None keeps the engine's text."""
    iid = str(fault.get("subject") or "")
    if iid not in old or iid not in new:
        return None
    name = old[iid].get("item_name", iid)
    have = _stock(old[iid])
    want = have - _stock(new[iid])
    if want > 0:
        return f"{before.get('name')} has {have} of {name!r} and cannot use or lose {want} (not enough stock)"
    if fault.get("expected") is None or fault.get("actual") is None:
        return None
    return f"{name} cannot be equipped: the engine allows {fault['expected']} ({fault['actual']} held)"


def _capacity_reason(before, fault):
    """The reason for an engine E_EQUIPMENT refusal (no free hand, a second
    shield): the engine's typed capacity, ``expected``/``actual``. None keeps
    the engine's text."""
    if fault.get("field") is None or fault.get("expected") is None or fault.get("actual") is None:
        return None
    return (f"{before.get('name')} cannot equip that: the engine's {fault['field']} allows "
            f"{fault['expected']} ({fault['actual']} would be in use)")


def _fold_target(old, new, iid, world) -> Optional[str]:
    """The carried stack a single worn unit folds back into when it is
    unequipped (#1135): an existing, unworn entry of the same typed identity
    (transfer.same_stack, never an effect-bearing one). None leaves its own row."""
    if iid not in old or iid not in new or iid in world.carried:
        return None
    if not (old[iid].get("equipped") is True and new[iid].get("equipped") is not True):
        return None
    if _stock(old[iid]) != 1 or _stock(new[iid]) != 1:
        return None
    for other, e in new.items():
        if other != iid and other in old and _stock(e) > 0 and old[other].get("equipped") is not True \
                and transfer.same_stack(new[iid], e):
            return other
    return None


def reconcile(before: Dict[str, Any], after: Dict[str, Any], *, location: str = "sheet",
              binary: Optional[str] = None, reserved: Optional[set] = None) -> EquipmentOutcome:
    """Return the engine-reconciled equipment list for ``after``, or a refusal.

    ``before`` is the sheet as stored; ``after`` is the same sheet with the T079
    delta merged (by item name, as the legacy merge does). Entries keep their
    ``nql_id`` through the merge; entries only in ``after`` are new items.
    A new item's minted id steps past ``reserved``, the ids held on other
    sheets and in chests (#1060).
    """
    before = copy.deepcopy(before)
    after = copy.deepcopy(after)
    genesis.assign_ids(before, reserved=reserved)
    # Carry ids into the merged entries by exact name for entries that have none
    # (an entry that names its nql_id was merged into that row and keeps it), then
    # mint for genuinely new ones.
    by_name = {}
    for e in before.get("equipment") or []:
        if isinstance(e, dict) and e.get("item_name") and e.get("item_name") not in by_name:
            by_name[e["item_name"]] = e["nql_id"]
    for e in after.get("equipment") or []:
        if isinstance(e, dict) and not isinstance(e.get("nql_id"), str) and e.get("item_name") in by_name:
            e["nql_id"] = by_name[e["item_name"]]
    genesis.assign_ids(after, reserved=reserved)

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
            # Only a single unit can be worn (genesis leaves an equipped stack
            # unworn), so only a stock of one is unequipped first.
            if (e.get("equipped") is True and new[iid].get("equipped") is not False
                    and _stock(e) == 1 and iid not in world.carried):
                ops.append(f"unequip {_q(iid)};")
            ops.append(f"consume {_q(iid)} from {_q(cid)} by {-delta};")
        elif delta > 0:
            ops.append(f"add {_q(iid)} to {_q(cid)} by {delta};")
    # New items: create, then equip if the merged entry says so.
    wearable: Dict[str, bool] = {}
    for iid, e in created:
        fields = [f"owner {_q(cid)};", f"custody character {_q(cid)};"]
        if _stock(e) != 1:
            fields.append(f"quantity {_stock(e)};")
        wearable[iid] = True
        catalog, catalog_gap = item_catalog.row_entry(e)
        if catalog_gap:
            gaps.append(f"{cid}: {e.get('item_name')!r} {catalog_gap}; created from its own fields")
        if catalog is not None:
            # GP: a new catalog row is created from the pack's type, which
            # supplies its name, description and equipment (no definition).
            # A type without equipment (ammunition) cannot be worn.
            wearable[iid] = item_catalog.equipment_mode(catalog) is not None
            ops.append(f"create item {_q(iid)} from {_q(catalog['id'])} {{ {' '.join(fields)} }};")
            continue
        if e.get("item_type") == "armor" and type(e.get("ac_base")) is int or e.get("armor_category") == "shield":
            fields.append(f"definition {_q('gear:' + iid.split(':', 1)[1])};")
        elif e.get("item_type") == "weapon":
            fields.append('definition "gear:held";')
        elif e.get("equipped") is True:
            fields.append('definition "gear:worn";')
        ops.append(f"create item {_q(iid)} named {_q(e.get('item_name', ''))} {{ {' '.join(fields)} }};")
    # Equipped flag changes on items that exist before and after. The engine
    # wears exactly one unit: a stack is drawn from (#1135, below).
    draws: List[str] = []
    for iid, e in new.items():
        if iid not in old or _stock(e) <= 0:
            continue
        was = old[iid].get("equipped") is True
        now = e.get("equipped") is True
        fold = _fold_target(old, new, iid, world)
        if now and not was:
            if _stock(e) > 1:
                draws.append(iid)
                continue
            ops.append(f"equip {_q(iid)} on {_q(cid)};")
        elif (was and not now and _stock(old[iid]) == 1 and _stock(e) >= _stock(old[iid])
              and iid not in world.carried):
            # A row the hand rule declared carried (NUM-H3a) is not worn in the
            # engine: unequipping it changes the sheet's flag only.
            ops.append(f"unequip {_q(iid)};")
            if fold is not None:
                ops.append(f"consume {_q(iid)} from {_q(cid)} by 1;")
                ops.append(f"add {_q(fold)} to {_q(cid)} by 1;")
    for iid, e in created:
        if e.get("equipped") is True:
            if not wearable.get(iid):
                gaps.append(f"{cid}: {e.get('item_name')!r} is marked equipped but its type has no "
                            "equipment; left unequipped")
            elif _stock(e) > 1:
                draws.append(iid)
            else:
                ops.append(f"equip {_q(iid)} on {_q(cid)};")
    if draws:
        # One unit is split off each drawn stack and worn; the stack keeps the
        # rest, carried. The part's id is free here and wherever the caller
        # read (genesis.split_id, as transfer does).
        taken = set(reserved or ()) | set(old) | set(new)
        for declared in world.item_ids.values():
            taken.update(declared.values())
        taken.update(aid for aid, _ in genesis.ammunition_rows(before, []))
        for iid in draws:
            part = genesis.split_id(iid, 1, taken)
            ops.append(f"split {_q(iid)} quantity 1 into {_q(part)} by {_q(cid)};")
            ops.append(f"equip {_q(part)} on {_q(cid)};")

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
        reason = f"engine refused at {response.get('phase')}: {detail}"
        if isinstance(fault, dict) and fault.get("code") == "E_QUANTITY":
            reason = _refusal_reason(before, old, new, fault) or reason
        elif isinstance(fault, dict) and fault.get("code") == "E_EQUIPMENT":
            reason = _capacity_reason(before, fault) or reason
        return EquipmentOutcome(False, operations=ops, fault=fault, reason=reason, gaps=gaps)

    views = {v["at"]["id"]: v["items"] for v in response.get("items_at", [])}
    result: List[Dict[str, Any]] = []
    parts: Dict[str, List[Dict[str, Any]]] = {}
    tracked = set()
    for item in views.get(cid, []):
        iid = item["id"]
        parent = item.get("split_from") if iid not in new and iid not in old else None
        base = new.get(iid) or old.get(iid) or new.get(parent or "") or old.get(parent or "")
        if base is None:
            continue
        tracked.add(iid)
        stock = item.get("quantity", 1) if type(item.get("quantity")) is int else 1
        if stock <= 0:
            continue
        entry = copy.deepcopy(base)
        entry["nql_id"] = iid
        entry["quantity"] = stock
        entry["equipped"] = item.get("wearer") == cid or (world.carried.get(iid) == cid and base.get("equipped") is True)
        if parent:
            parts.setdefault(parent, []).append(entry)   # a drawn unit: its row follows its stack's
        else:
            result.append(entry)
    if parts:
        ordered: List[Dict[str, Any]] = []
        for entry in result:
            ordered.append(entry)
            ordered.extend(parts.pop(entry["nql_id"], []))
        result = ordered + [entry for rest in parts.values() for entry in rest]
    for e in after.get("equipment") or []:
        if isinstance(e, dict) and e.get("nql_id") not in tracked and e.get("nql_id") not in old:
            result.append(e)   # untracked by the engine (no name); keep the merged entry
    return EquipmentOutcome(True, equipment=result, operations=ops, receipt=response.get("receipt"), gaps=gaps)
