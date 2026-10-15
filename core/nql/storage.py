# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Storage transactions through the engine (seam S2).

A store or retrieve request (already a typed operation from T049) becomes NQL
``place`` operations on a world built from the acting character's sheet and
the containers at the current location. The engine decides legality (the item
must exist with enough stock, be unworn, and share the location) and commits
atomically. Code then rewrites the character's ``equipment`` and the container's
``contents`` from the engine's custody facts. No quantity or ownership is
computed here; every number comes from the engine's item records.

Ammunition (#366): a store takes the character's typed ``ammunition`` row first
(the engine stock combat spends from, as transferItem does), and ordinary
ammunition taken back out rejoins that stock; the row's count is the engine's.

A rejection is returned as a typed outcome with the engine's fault. The caller
decides how to report it; nothing is written.
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import ammunition, apply, genesis, transfer
from utils.enhanced_logger import warning


@dataclass
class StorageOutcome:
    ok: bool
    character: Optional[Dict[str, Any]] = None
    container: Optional[Dict[str, Any]] = None
    moved: List[Tuple[str, int]] = field(default_factory=list)
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    fault: Optional[Dict[str, Any]] = None
    worn_items: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return genesis._q(value)


def _requested_items(operation: Dict[str, Any]) -> List[Tuple[str, int]]:
    if isinstance(operation.get("items"), list):
        return [(str(i.get("item_name")), int(i.get("quantity"))) for i in operation["items"]]
    return [(str(operation.get("item_name")), int(operation.get("quantity")))]


def _find_entry(entries: List[Dict[str, Any]], ids: Dict[int, str], name: str) -> Tuple[Optional[int], Optional[str]]:
    """Exact item_name match among entries that have an engine id; index and id."""
    for index, entry in enumerate(entries):
        if isinstance(entry, dict) and entry.get("item_name") == name and index in ids:
            return index, ids[index]
    return None, None


def _ordinary_ammunition(entry: Any) -> bool:
    return isinstance(entry, dict) and entry.get("item_type") == "ammunition" \
        and not entry.get("magical") and not entry.get("effects")


def _stock(entry: Dict[str, Any]) -> int:
    return entry.get("quantity") if type(entry.get("quantity")) is int else 1


def _same_kind(entry: Dict[str, Any], other: Any) -> bool:
    """Whether a retrieve of ``entry`` also draws on ``other``: ordinary
    ammunition of the same name (#971), or an entry of the same name and the
    same stack under transferItem's rule (#1026)."""
    if not isinstance(other, dict) or other.get("item_name") != entry.get("item_name"):
        return False
    if _ordinary_ammunition(entry):
        return _ordinary_ammunition(other)
    return transfer.same_stack(entry, other)


def stored_quantity(contents: List[Dict[str, Any]], entry: Dict[str, Any]) -> Any:
    """What a retrieve of ``entry`` can draw on: the sum over every entry of the
    same kind (#971, #1026), else the entry's quantity."""
    if not _same_kind(entry, entry):
        return entry.get("quantity", 1)
    return sum(_stock(e) for e in contents if _same_kind(entry, e) and _stock(e) > 0)


# Read by the managers (#1039); it lives with the id authority (#1060).
held_ids_on_disk = genesis.held_ids_on_disk


def transact(character: Dict[str, Any], storage: Dict[str, Any], container: Dict[str, Any],
             operation: Dict[str, Any], *, request_id: Optional[str] = None,
             binary: Optional[str] = None, reserved: Optional[set] = None) -> StorageOutcome:
    """Run one store_item or retrieve_item through the engine.

    ``container`` is the target container record inside ``storage`` (already
    resolved by the caller). Returns new copies of the character sheet and the
    container record; the caller writes them and keeps the access log.
    """
    action = operation.get("action")
    if action not in ("store_item", "retrieve_item"):
        return StorageOutcome(False, reason=f"unsupported storage action {action!r}")
    character = copy.deepcopy(character)
    container = copy.deepcopy(container)
    # A minted id, on the sheet or in a chest, steps past every id the
    # storage record and the caller's disk read hold, as a split id does
    # (#1060, #1073).
    held_elsewhere = set(reserved or ()) | genesis.held_ids([], storage.get("playerStorage") or [])
    genesis.assign_ids(character, reserved=held_elsewhere)
    cid = genesis.character_id(character)
    location = str(container.get("locationId") or "unknown")
    siblings = [c for c in storage.get("playerStorage", [])
                if isinstance(c, dict) and c.get("locationId") == container.get("locationId")]
    siblings = [container if c.get("id") == container.get("id") else c for c in siblings]
    world = genesis.build_world([character], location, str(container.get("locationName") or location),
                                containers=siblings, contents_owner=cid, reserved=held_elsewhere)
    sid = str(container.get("id"))
    conid = world.container_ids.get(sid)
    if conid is None:
        return StorageOutcome(False, reason="container is not in the engine world", gaps=world.gaps)
    taken = set(world.container_ids.values())
    for declared in list(world.item_ids.values()) + list(world.content_ids.values()):
        taken.update(declared.values())
    taken.update(aid for aid, _ in genesis.ammunition_rows(character, []))
    # A part travels (chest to sheet, sheet to sheet), so its id is free
    # everywhere, not only in this world: every container in the storage
    # record, and whatever the caller read from disk (#1039).
    taken.update(genesis.held_ids([], storage.get("playerStorage") or []))
    taken.update(reserved or ())

    # Compile the request from the typed operation. Partial stock is split first
    # (a new id under the same scope), then the whole split stock is placed.
    actions: List[str] = []
    planned: List[Tuple[str, int, str]] = []   # (item id to place, quantity, item_name)
    worn: List[str] = []
    entries = character.get("equipment") or []
    contents = container.get("contents") or []
    stocks: Dict[str, Dict[str, Any]] = {}       # ammunition stock id -> its row (written back from the engine)
    stored_parts: Dict[str, Dict[str, Any]] = {} # ammunition stock id -> the contents entry its stored part becomes
    joined: List[str] = []                       # retrieved ids folded into an ammunition stock
    whole: List[str] = []                        # ammunition stock ids placed whole (the row keeps 0)
    new_rows: Dict[str, Dict[str, Any]] = {}     # retrieved id -> contents entry that starts a new row
    for name, quantity in _requested_items(operation):
        if action == "store_item":
            found = ammunition.declared_row(character, name)
            if found is not None:
                aid, row = found
                stock = row["quantity"]
                if quantity <= 0 or quantity > stock:
                    return StorageOutcome(False, reason=f"only {stock} {name!r} available, requested {quantity}",
                                          gaps=world.gaps)
                place_id = aid
                if quantity < stock:
                    place_id = genesis.split_id(aid, quantity, taken)
                    actions.append(f"split {_q(aid)} quantity {quantity} into {_q(place_id)} by {_q(cid)};")
                else:
                    whole.append(aid)
                actions.append(f"place {_q(place_id)} from character {_q(cid)} to item {_q(conid)} by {_q(cid)};")
                planned.append((place_id, quantity, name))
                stocks[aid] = row
                part = {"item_name": row["name"], "item_type": "ammunition",
                        "description": str(row.get("description") or ""), "quantity": quantity}
                if row.get("catalog_id"):
                    part["catalog_id"] = row["catalog_id"]
                stored_parts[aid] = part
                continue
            index, iid = _find_entry(entries, world.item_ids.get(cid, {}), name)
            source, target = f"character {_q(cid)}", f"item {_q(conid)}"
            pool = entries
        else:
            index, iid = _find_entry(contents, world.content_ids.get(sid, {}), name)
            source, target = f"item {_q(conid)}", f"character {_q(cid)}"
            pool = contents
        if iid is None:
            return StorageOutcome(False, reason=f"{name!r} is not present at the source", gaps=world.gaps)
        entry = pool[index]
        if entry.get("equipped") is True:
            worn.append(name)
        # Each deposit is its own chest entry, so a retrieve draws on every
        # entry of the same kind, whole entries first in contents order, an
        # empty one skipped (#971, #1026). A worn or effect-bearing entry, or
        # magical ammunition, takes the one entry.
        parts = [(index, iid)]
        if action == "retrieve_item" and _same_kind(entry, entry):
            ids = world.content_ids.get(sid, {})
            parts = [(i, ids[i]) for i, e in enumerate(contents)
                     if i in ids and _same_kind(entry, e) and _stock(e) > 0]
        stock = sum(_stock(pool[i]) for i, _ in parts)
        if quantity <= 0 or quantity > stock:
            return StorageOutcome(False, reason=f"only {stock} {name!r} available, requested {quantity}", gaps=world.gaps)
        placed: List[Tuple[str, int]] = []
        left = quantity
        for i, part_id in parts:
            if left == 0:
                break
            take = min(_stock(pool[i]), left)
            place_id = part_id
            if take < _stock(pool[i]):
                place_id = genesis.split_id(part_id, take, taken)
                actions.append(f"split {_q(part_id)} quantity {take} into {_q(place_id)} by {_q(cid)};")
            actions.append(f"place {_q(place_id)} from {source} to {target} by {_q(cid)};")
            placed.append((place_id, take))
            left -= take
        planned.append((placed[0][0], quantity, name))
        if action == "retrieve_item" and _ordinary_ammunition(entry):
            # D-366-2: ordinary ammunition rejoins the ammunition stock in the
            # same request (consume each arrival, add to the row's stock).
            item_name = str(entry.get("item_name"))
            found = ammunition.declared_row(character, item_name)
            clash = found is None and any(
                isinstance(r, dict) and isinstance(r.get("name"), str)
                and genesis.ammunition_id(character, r["name"]) == genesis.ammunition_id(character, item_name)
                for r in character.get("ammunition") or [])
            if found is None and not clash:
                # #971: else the one row holding the same catalog ammunition
                # under an older name (Arrow for Arrows), as a purchase does.
                found = ammunition.declared_row_for_catalog(character, item_name, entry.get("catalog_id"))
            if found is not None:
                aid, row = found
                stocks[aid] = row
            elif clash:
                return StorageOutcome(False, reason=f"{character.get('name')}'s {item_name!r} row has no whole-number quantity",
                                      gaps=world.gaps)
            else:
                # A new row starts from the first arrival; later ones join it.
                aid = placed[0][0]
                new_rows[aid] = entry
                placed = placed[1:]
            for place_id, take in placed:
                actions.append(f"consume {_q(place_id)} from {_q(cid)} by {take};")
                actions.append(f"add {_q(aid)} to {_q(cid)} by {take};")
                joined.append(place_id)
        elif action == "retrieve_item" and _same_kind(entry, entry):
            # D-1026-2: the arrivals join the sheet's matching stack, as a
            # hand-off does (transferItem); with none, they join the first one.
            merge_id = transfer._matching_stack(character, world.item_ids.get(cid, {}), entry)
            rest = placed
            if merge_id is None:
                merge_id, rest = placed[0][0], placed[1:]
            for place_id, take in rest:
                actions.append(f"consume {_q(place_id)} from {_q(cid)} by {take};")
                actions.append(f"add {_q(merge_id)} to {_q(cid)} by {take};")
                joined.append(place_id)
    if worn:
        return StorageOutcome(False, reason="selected items are still equipped", worn_items=worn, gaps=world.gaps)

    try:
        response = apply.call({"world": world.source, "world_name": "storage-genesis.nql", "actions": "\n".join(actions),
                               "actions_name": "storage.nql", "actor": {"kind": "character", "id": cid},
                               "request": request_id or f"storage:{uuid.uuid4().hex}",
                               "items_at": [{"kind": "character", "id": cid}, {"kind": "item", "id": conid}]},
                              binary=binary)
    except apply.EngineUnavailable as error:
        return StorageOutcome(False, reason=str(error), gaps=world.gaps)
    if not response.get("ok"):
        detail = response.get("diagnostics") or response.get("fault") or response.get("error")
        return StorageOutcome(False, reason=f"engine refused at {response.get('phase')}: {detail}",
                              fault=response.get("fault"), gaps=world.gaps)

    # Project both records from the engine's custody facts. Each engine item is
    # traced to its source sheet or container entry (by id, or by split parent)
    # so metadata travels with it; quantity comes from the engine.
    source_entry: Dict[str, Dict[str, Any]] = {}
    for index, iid in world.item_ids.get(cid, {}).items():
        source_entry[iid] = entries[index]
    for index, iid in world.content_ids.get(sid, {}).items():
        source_entry[iid] = contents[index]

    def rebuild(items: List[Dict[str, Any]], equipped_default: Optional[bool],
                sources: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for item in items:
            iid = item["id"]
            base = sources.get(iid) or sources.get(item.get("split_from", ""))
            if base is None:
                continue
            entry = copy.deepcopy(base)
            entry["nql_id"] = iid
            entry["quantity"] = item.get("quantity", 1) if type(item.get("quantity")) is int else 1
            if equipped_default is not None:
                entry["equipped"] = equipped_default
            elif item.get("wearer") != cid and entry.get("equipped") is True and world.carried.get(iid) != cid:
                entry["equipped"] = False
            out.append(entry)
        return out

    views = {v["at"]["id"]: v["items"] for v in response.get("items_at", [])}
    char_items = [i for i in views.get(cid, []) if not i.get("container")]
    kept_untracked = [e for i, e in enumerate(entries) if i not in world.item_ids.get(cid, {})]
    gear = [i for i in char_items if i["id"] not in joined and i["id"] not in new_rows]
    character["equipment"] = rebuild(gear, None, source_entry) + kept_untracked
    container["contents"] = rebuild(views.get(conid, []), False, {**source_entry, **stored_parts})
    # An entry genesis could not declare (no name, or an id another entry
    # stores) is not in the engine view; it is kept as it is (#1026).
    unread = [e for i, e in enumerate(contents) if i not in world.content_ids.get(sid, {})]
    container["contents"] += unread
    char_view = {i["id"]: i for i in char_items}
    con_view = {i["id"]: i for i in views.get(conid, [])}
    # A stock placed whole is in the container now: its row keeps 0 and the
    # pending count the engine moved with it (shots still out from the last
    # fight). Every other stock, and every new row, is in the character's view.
    held: Dict[str, Optional[Dict[str, Any]]] = {}
    for aid in stocks:
        placed = con_view.get(aid)
        held[aid] = ({"quantity": 0, "recoverable": placed.get("recoverable")} if placed else None) \
            if aid in whole else char_view.get(aid)
    for pid in new_rows:
        held[pid] = char_view.get(pid)
    if any(item is None or type(item.get("quantity")) is not int for item in held.values()):
        return StorageOutcome(False, reason="engine returned no view of the ammunition stock", gaps=world.gaps)
    for aid, row in stocks.items():
        ammunition.write_view(row, held[aid])
    for pid, entry in new_rows.items():
        item = held[pid]
        row = {"name": str(entry.get("item_name")), "description": str(entry.get("description") or "")}
        if entry.get("catalog_id"):
            row["catalog_id"] = entry["catalog_id"]
        ammunition.write_view(row, item)
        if not isinstance(character.get("ammunition"), list):
            character["ammunition"] = []
        character["ammunition"].append(row)
    if unread:
        warning(f"STORAGE: {sid} keeps {len(unread)} entries the engine could not read: "
                + "; ".join(g for g in world.gaps if g.startswith(f"{sid}:")), category="storage_operations")
    return StorageOutcome(True, character=character, container=container,
                          moved=[(name, quantity) for _, quantity, name in planned],
                          receipt=response.get("receipt"), gaps=world.gaps)
