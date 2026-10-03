# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Character-to-character handoff as one engine transaction (E4b, owner decision D10).

A give is three engine operations on a world built from both sheets at the
party's location: ``split`` when only part of a stack moves, ``transfer``
(ownership; the world rule ``transfer unequips`` hands a worn item over
unworn), then ``place`` (custody into the receiver). The engine commits all of
them or none, so the item can neither vanish nor be duplicated between two
independent sheet updates. Code then rewrites both sheets' ``equipment`` from
the engine's custody facts; every quantity comes from the engine's item records.

A refusal (absent item, over-request, self-transfer, engine fault) is a typed
outcome with the engine's reason. Nothing is written by this module; the
caller owns files and locks.
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import apply, genesis, item_catalog


@dataclass
class TransferOutcome:
    ok: bool
    giver: Optional[Dict[str, Any]] = None
    receiver: Optional[Dict[str, Any]] = None
    item_name: str = ""
    quantity: int = 0
    unequipped: bool = False
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    fault: Optional[Dict[str, Any]] = None
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return genesis._q(value)


def _find_entry(entries: List[Dict[str, Any]], ids: Dict[int, str], name: str) -> Tuple[Optional[int], Optional[str]]:
    """The giver's entry for this item name among entries the engine knows.

    Exact ``item_name`` first; otherwise a unique case-insensitive match on the
    same typed field. No other text is inspected.
    """
    wanted = str(name).strip()
    for index, entry in enumerate(entries):
        if isinstance(entry, dict) and entry.get("item_name") == wanted and index in ids:
            return index, ids[index]
    loose = [(i, ids[i]) for i, e in enumerate(entries)
             if isinstance(e, dict) and i in ids and str(e.get("item_name", "")).strip().lower() == wanted.lower()]
    if len(loose) == 1:
        return loose[0]
    return None, None


_STACK_IDENTITY = ("item_name", "item_type", "item_subtype", "magical", "armor_category", "ac_base", "ac_bonus")


def _matching_stack(receiver: Dict[str, Any], ids: Dict[int, str], entry: Dict[str, Any]) -> Optional[str]:
    """The receiver's engine item id for an entry of the same typed identity, or None."""
    if entry.get("equipped") is True or entry.get("effects"):
        return None
    for index, other in enumerate(receiver.get("equipment") or []):
        if not isinstance(other, dict) or index not in ids or other is entry:
            continue
        if other.get("equipped") is True or other.get("effects"):
            continue
        mine = item_catalog.row_entry(entry)[0]
        theirs = item_catalog.row_entry(other)[0]
        if mine is not None or theirs is not None:
            # SA: a catalog row stacks only with another row of the same catalog
            # type; a row that drifted from its type is its own kind of thing.
            if mine is not None and theirs is not None and mine["id"] == theirs["id"]:
                return ids[index]
            continue
        if all(_identity_value(other, k) == _identity_value(entry, k) for k in _STACK_IDENTITY):
            return ids[index]
    return None


def _identity_value(entry: Dict[str, Any], key: str) -> Any:
    """Typed identity with the schema defaults applied (unset magical is False, unset subtype is other)."""
    value = entry.get(key)
    if key == "magical":
        return bool(value)
    if key == "item_subtype" and value in (None, ""):
        return "other"
    return value


def transact(giver: Dict[str, Any], receiver: Dict[str, Any], item_name: str, quantity: int, *,
             location: str = "party", request_id: Optional[str] = None,
             binary: Optional[str] = None) -> TransferOutcome:
    """Move ``quantity`` of the giver's ``item_name`` to the receiver through the engine.

    Returns new copies of both sheets with ``equipment`` rewritten from the
    engine's custody facts, or a refusal with nothing changed.
    """
    giver = copy.deepcopy(giver)
    receiver = copy.deepcopy(receiver)
    genesis.assign_ids(giver)
    genesis.assign_ids(receiver)
    gid = genesis.character_id(giver)
    rid = genesis.character_id(receiver)
    if gid == rid:
        return TransferOutcome(False, reason="giver and receiver are the same character")
    world = genesis.build_world([giver, receiver], location)
    if rid not in world.item_ids:
        return TransferOutcome(False, reason="receiver is not in the engine world", gaps=world.gaps)

    entries = giver.get("equipment") or []
    index, iid = _find_entry(entries, world.item_ids.get(gid, {}), item_name)
    if iid is None:
        return TransferOutcome(False, reason=f"{item_name!r} is not on the giver's sheet", gaps=world.gaps)
    entry = entries[index]
    stock = entry.get("quantity") if type(entry.get("quantity")) is int else 1
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return TransferOutcome(False, reason=f"quantity {quantity!r} is not a whole number", gaps=world.gaps)
    if quantity <= 0 or quantity > stock:
        return TransferOutcome(False, reason=f"only {stock} {entry.get('item_name')!r} available, requested {quantity}",
                               gaps=world.gaps)
    was_worn = entry.get("equipped") is True

    move_id = iid
    actions: List[str] = []
    if quantity < stock:
        move_id = f"{iid}:part:{quantity}"
        actions.append(f"split {_q(iid)} quantity {quantity} into {_q(move_id)} by {_q(gid)};")
    actions.append(f"transfer {_q(move_id)} from {_q(gid)} to {_q(rid)};")
    actions.append(f"place {_q(move_id)} from character {_q(gid)} to character {_q(rid)} by {_q(gid)};")
    # Same stock on the receiver: fold the arriving units into that entry in
    # the same request (consume the arrival, add to the existing stack), so a
    # sheet never carries two entries for one kind of thing. Only an unworn,
    # unequipped entry with the same typed identity merges.
    merge_id = _matching_stack(receiver, world.item_ids.get(rid, {}), entry)
    if merge_id is not None:
        actions.append(f"consume {_q(move_id)} from {_q(rid)} by {quantity};")
        actions.append(f"add {_q(merge_id)} to {_q(rid)} by {quantity};")

    try:
        response = apply.call({"world": world.source, "world_name": "transfer-genesis.nql",
                               "actions": "\n".join(actions), "actions_name": "transfer.nql",
                               "actor": {"kind": "character", "id": gid},
                               "request": request_id or f"transfer:{uuid.uuid4().hex}",
                               "items_at": [{"kind": "character", "id": gid}, {"kind": "character", "id": rid}]},
                              binary=binary)
    except apply.EngineUnavailable as error:
        return TransferOutcome(False, reason=str(error), gaps=world.gaps)
    if not response.get("ok"):
        detail = response.get("diagnostics") or response.get("fault") or response.get("error")
        return TransferOutcome(False, reason=f"engine refused at {response.get('phase')}: {detail}",
                               fault=response.get("fault"), gaps=world.gaps)

    # Every engine item traces to the sheet entry it came from (by id, or by
    # split parent) so metadata travels with it; quantity and wearer come from
    # the engine.
    source_entry: Dict[str, Dict[str, Any]] = {}
    for sheet, cid in ((giver, gid), (receiver, rid)):
        for i, item_id in world.item_ids.get(cid, {}).items():
            source_entry[item_id] = (sheet.get("equipment") or [])[i]

    def rebuild(cid: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for item in items:
            if item.get("container"):
                continue
            base = source_entry.get(item["id"]) or source_entry.get(item.get("split_from", ""))
            if base is None:
                continue
            rebuilt = copy.deepcopy(base)
            rebuilt["nql_id"] = item["id"]
            rebuilt["quantity"] = item.get("quantity", 1) if type(item.get("quantity")) is int else 1
            if rebuilt["quantity"] <= 0:
                continue   # depleted by a merge: its units live in the matching stack
            if item.get("wearer") != cid and rebuilt.get("equipped") is True:
                rebuilt["equipped"] = False
            out.append(rebuilt)
        return out

    views = {v["at"]["id"]: v["items"] for v in response.get("items_at", [])}
    for sheet, cid in ((giver, gid), (receiver, rid)):
        untracked = [e for i, e in enumerate(sheet.get("equipment") or []) if i not in world.item_ids.get(cid, {})]
        sheet["equipment"] = rebuild(cid, views.get(cid, [])) + untracked
    return TransferOutcome(True, giver=giver, receiver=receiver, item_name=str(entry.get("item_name")),
                           quantity=quantity, unequipped=was_worn, receipt=response.get("receipt"), gaps=world.gaps)
