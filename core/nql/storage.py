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

A rejection is returned as a typed outcome with the engine's fault. The caller
decides how to report it; nothing is written.
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import apply, genesis


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


def transact(character: Dict[str, Any], storage: Dict[str, Any], container: Dict[str, Any],
             operation: Dict[str, Any], *, request_id: Optional[str] = None,
             binary: Optional[str] = None) -> StorageOutcome:
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
    genesis.assign_ids(character)
    cid = genesis.character_id(character)
    location = str(container.get("locationId") or "unknown")
    siblings = [c for c in storage.get("playerStorage", [])
                if isinstance(c, dict) and c.get("locationId") == container.get("locationId")]
    siblings = [container if c.get("id") == container.get("id") else c for c in siblings]
    world = genesis.build_world([character], location, str(container.get("locationName") or location),
                                containers=siblings, contents_owner=cid)
    sid = str(container.get("id"))
    conid = world.container_ids.get(sid)
    if conid is None:
        return StorageOutcome(False, reason="container is not in the engine world", gaps=world.gaps)

    # Compile the request from the typed operation. Partial stock is split first
    # (a new id under the same scope), then the whole split stock is placed.
    actions: List[str] = []
    planned: List[Tuple[str, int, str]] = []   # (item id to place, quantity, item_name)
    worn: List[str] = []
    entries = character.get("equipment") or []
    contents = container.get("contents") or []
    for name, quantity in _requested_items(operation):
        if action == "store_item":
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
        stock = entry.get("quantity") if type(entry.get("quantity")) is int else 1
        if quantity <= 0 or quantity > stock:
            return StorageOutcome(False, reason=f"only {stock} {name!r} available, requested {quantity}", gaps=world.gaps)
        place_id = iid
        if quantity < stock:
            place_id = f"{iid}:part:{quantity}"
            actions.append(f"split {_q(iid)} quantity {quantity} into {_q(place_id)} by {_q(cid)};")
        actions.append(f"place {_q(place_id)} from {source} to {target} by {_q(cid)};")
        planned.append((place_id, quantity, name))
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

    def rebuild(items: List[Dict[str, Any]], equipped_default: Optional[bool]) -> List[Dict[str, Any]]:
        out = []
        for item in items:
            iid = item["id"]
            base = source_entry.get(iid) or source_entry.get(item.get("split_from", ""))
            if base is None:
                continue
            entry = copy.deepcopy(base)
            entry["nql_id"] = iid
            entry["quantity"] = item.get("quantity", 1) if type(item.get("quantity")) is int else 1
            if equipped_default is not None:
                entry["equipped"] = equipped_default
            elif item.get("wearer") != cid and entry.get("equipped") is True:
                entry["equipped"] = False
            out.append(entry)
        return out

    views = {v["at"]["id"]: v["items"] for v in response.get("items_at", [])}
    char_items = [i for i in views.get(cid, []) if not i.get("container")]
    kept_untracked = [e for i, e in enumerate(entries) if i not in world.item_ids.get(cid, {})]
    character["equipment"] = rebuild(char_items, None) + kept_untracked
    container["contents"] = rebuild(views.get(conid, []), False)
    return StorageOutcome(True, character=character, container=container,
                          moved=[(name, quantity) for _, quantity, name in planned],
                          receipt=response.get("receipt"), gaps=world.gaps)
