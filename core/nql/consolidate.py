# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Inventory consolidation through the engine (E7).

The consolidation model (T054) decides which sheet entries are loose coins or
plain ammunition and what they are worth; this module executes that proposal
as one engine request: ``consume`` each source entry's whole stock and ``heal``
each coin delta. The engine refuses when an entry is missing or short, and
the equipment list and balances written back are the engine's. Ammunition rows
are not engine-modelled; the caller appends them from the typed proposal.

Nothing here reads prose or writes files.
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.nql import apply, currency, genesis


@dataclass
class ConsolidationOutcome:
    ok: bool
    sheet: Optional[Dict[str, Any]] = None
    consumed: List[str] = field(default_factory=list)
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    fault: Optional[Dict[str, Any]] = None
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return genesis._q(value)


def _stock(entry: Dict[str, Any]) -> int:
    quantity = entry.get("quantity")
    return quantity if type(quantity) is int and quantity > 0 else 1


def transact(sheet: Dict[str, Any], removals: List[str], coin_delta: Any, *, location: str = "sheet",
             request_id: Optional[str] = None, binary: Optional[str] = None) -> ConsolidationOutcome:
    """Consume the named entries entirely and credit ``coin_delta`` in one engine request."""
    delta, reason = currency.normalize_delta(coin_delta or {})
    if delta is None:
        return ConsolidationOutcome(False, reason=reason)
    if any(v < 0 for v in delta.values()):
        return ConsolidationOutcome(False, reason="consolidation may not reduce a coin balance")
    sheet = copy.deepcopy(sheet)
    genesis.assign_ids(sheet)
    cid = genesis.character_id(sheet)
    world = genesis.build_world([sheet], location)
    entries = sheet.get("equipment") or []
    ids = world.item_ids.get(cid, {})
    by_name = {}
    for index, iid in ids.items():
        by_name.setdefault(str(entries[index].get("item_name")), (index, iid))

    actions: List[str] = []
    consumed: List[str] = []
    for name in removals:
        if name not in by_name:
            return ConsolidationOutcome(False, reason=f"{name!r} is not on the sheet", gaps=world.gaps)
        index, iid = by_name[name]
        if entries[index].get("equipped") is True:
            return ConsolidationOutcome(False, reason=f"{name!r} is equipped and cannot be consolidated", gaps=world.gaps)
        actions.append(f"consume {_q(iid)} from {_q(cid)} by {_stock(entries[index])};")
        consumed.append(name)
    for coin, amount in delta.items():
        actions.append(f'heal {_q(cid)} resource {_q(coin)} by {amount};')
    if not actions:
        return ConsolidationOutcome(True, sheet=sheet, gaps=world.gaps)

    try:
        response = apply.call({"world": world.source, "world_name": "consolidate-genesis.nql",
                               "actions": "\n".join(actions), "actions_name": "consolidate.nql",
                               "actor": {"kind": "character", "id": cid},
                               "request": request_id or f"consolidate:{uuid.uuid4().hex}",
                               "items_at": [{"kind": "character", "id": cid}], "status": [cid]}, binary=binary)
    except apply.EngineUnavailable as error:
        return ConsolidationOutcome(False, reason=str(error), gaps=world.gaps)
    if not response.get("ok"):
        fault = response.get("fault") or {}
        return ConsolidationOutcome(False, reason=f"engine refused at {response.get('phase')}: "
                                    f"{response.get('diagnostics') or fault or response.get('error')}",
                                    fault=fault or None, gaps=world.gaps)

    source_entry = {iid: entries[index] for index, iid in ids.items()}
    rebuilt: List[Dict[str, Any]] = []
    for item in next((v["items"] for v in response.get("items_at", []) if v["at"]["id"] == cid), []):
        if item.get("container"):
            continue
        base = source_entry.get(item["id"]) or source_entry.get(item.get("split_from", ""))
        if base is None:
            continue
        quantity = item.get("quantity")
        if type(quantity) is int and quantity <= 0:
            continue  # depleted by the consume
        entry = copy.deepcopy(base)
        entry["nql_id"] = item["id"]
        entry["quantity"] = quantity if type(quantity) is int else 1
        rebuilt.append(entry)
    untracked = [e for i, e in enumerate(entries) if i not in ids]
    sheet["equipment"] = rebuilt + untracked
    status = next((s for s in response.get("status", []) if (s.get("character") or {}).get("id") == cid), None)
    if status is None:
        return ConsolidationOutcome(False, reason="engine returned no balance", gaps=world.gaps)
    resources = status.get("resources") or {}
    sheet["currency"] = {c: int(resources[c]["current"]) for c in currency.COIN_TYPES if c in resources}
    return ConsolidationOutcome(True, sheet=sheet, consumed=consumed, receipt=response.get("receipt"), gaps=world.gaps)
