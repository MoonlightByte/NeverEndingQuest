# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Ammunition through the engine (AM): shots, pickups and the after-fight recovery.

Each typed ``ammunition`` row of a sheet is one engine stock (core/nql/genesis).
A shot is ``consume ... recoverable``: the engine lowers the quantity and keeps
the count of shots that can be found again. After the fight ``recover`` closes
the count and returns the world's share (SRD: half, rounded down), or none when
the party had no time to search (``by 0``). The engine refuses a short stock
and an empty count (E_QUANTITY). The quantity and the pending count written
back are the engine's; nothing here reads prose or decides a number.
"""
import copy
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from core.nql import apply, genesis, item_catalog


@dataclass
class AmmunitionOutcome:
    ok: bool
    quantity: Optional[int] = None      # the stock after the request
    recoverable: Optional[int] = None   # the pending count after the request
    reason: str = ""
    fault: Optional[Dict[str, Any]] = None
    receipt: Optional[Dict[str, Any]] = None


def declared_row(sheet: Dict[str, Any], name: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """(engine stock id, row) of the sheet's ammunition row for this name, or None.

    Only rows genesis declares are candidates (a row whose name slugs to an
    earlier row's id is skipped there), so the stock id is always the row's
    own. Exact ``name`` first; otherwise a unique case-insensitive match on the
    same typed field. Shared by transferItem (#902) and storage (#366).
    """
    wanted = str(name).strip()
    rows = genesis.ammunition_rows(sheet, [])
    for iid, row in rows:
        if row.get("name") == wanted:
            return iid, row
    loose = [(iid, row) for iid, row in rows if row["name"].strip().lower() == wanted.lower()]
    return loose[0] if len(loose) == 1 else None


def declared_row_for_catalog(sheet: Dict[str, Any], name: str,
                             catalog_id: Any = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    """(engine stock id, row) of the one declared row holding the same catalog
    ammunition as ``name`` (or ``catalog_id``) under another name, or None.

    The purchase rule (#552): an Arrow row takes Arrows. None, or two or more
    such rows, give None and the caller keeps its own path (#971).
    """
    wanted = item_catalog.ammunition_entry({"name": name, "catalog_id": catalog_id})
    if wanted is None:
        return None
    held = [(iid, row) for iid, row in genesis.ammunition_rows(sheet, [])
            if (item_catalog.ammunition_entry(row) or {}).get("id") == wanted.get("id")]
    return held[0] if len(held) == 1 else None


def declared_row_by_id(sheet: Dict[str, Any], iid: str) -> Optional[Dict[str, Any]]:
    return next((row for stock, row in genesis.ammunition_rows(sheet, []) if stock == iid), None)


def write_view(row: Dict[str, Any], item: Optional[Dict[str, Any]]) -> None:
    """Copy the engine's view of a stock onto its row (no view: the stock left, 0)."""
    quantity = item.get("quantity") if item and type(item.get("quantity")) is int else 0
    pending = item.get("recoverable") if item and type(item.get("recoverable")) is int else 0
    write_back(row, AmmunitionOutcome(True, quantity=quantity, recoverable=pending))


def row_of(sheet: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    for row in sheet.get("ammunition") or []:
        if isinstance(row, dict) and row.get("name") == name:
            return row
    return None


def _request(sheet: Dict[str, Any], name: str, action: str, label: str, binary: Optional[str]) -> AmmunitionOutcome:
    row = row_of(sheet, name)
    if row is None or type(row.get("quantity")) is not int:
        return AmmunitionOutcome(False, reason=f"{sheet.get('name')} has no ammunition row {name!r}")
    declared = dict(genesis.ammunition_rows(sheet, []))
    if declared.get(genesis.ammunition_id(sheet, name)) is not row:
        # Two rows whose names slug to one id: the engine holds only the first.
        return AmmunitionOutcome(False, reason=f"ammunition row {name!r} shares an engine id with another row")
    world_sheet = copy.deepcopy(sheet)
    world = genesis.build_world([world_sheet], "combat")
    cid = genesis.character_id(sheet)
    iid = genesis.ammunition_id(sheet, name)
    try:
        response = apply.call({"world": world.source, "world_name": "ammunition-genesis.nql",
                               "actions": action, "actions_name": "ammunition.nql",
                               "actor": {"kind": "character", "id": cid},
                               "request": f"ammunition:{label}:{uuid.uuid4().hex}",
                               "items_at": [{"kind": "character", "id": cid}]}, binary=binary)
    except apply.EngineUnavailable as error:
        return AmmunitionOutcome(False, reason=str(error))
    if not response.get("ok"):
        fault = response.get("fault") or {}
        detail = response.get("diagnostics") or fault or response.get("error")
        return AmmunitionOutcome(False, fault=fault or None,
                                 reason=f"engine refused at {response.get('phase')}: {detail}")
    for view in response.get("items_at") or []:
        if (view.get("at") or {}).get("id") != cid:
            continue
        for item in view.get("items") or []:
            if item.get("id") == iid:
                quantity = item.get("quantity", 0) if type(item.get("quantity")) is int else 0
                pending = item.get("recoverable", 0) if type(item.get("recoverable")) is int else 0
                return AmmunitionOutcome(True, quantity=quantity, recoverable=pending, receipt=response.get("receipt"))
    return AmmunitionOutcome(False, reason="engine returned no view of the ammunition stock")


def spend(sheet: Dict[str, Any], name: str, amount: int, *, recoverable: bool = True,
          binary: Optional[str] = None) -> AmmunitionOutcome:
    """One shot or volley: the engine lowers the stock and counts the recoverable shots."""
    if type(amount) is not int or amount <= 0:
        return AmmunitionOutcome(False, reason="a spend needs a positive integer amount")
    cid = genesis.character_id(sheet)
    iid = genesis.ammunition_id(sheet, name)
    tail = " recoverable" if recoverable else ""
    return _request(sheet, name, f"consume {genesis._q(iid)} from {genesis._q(cid)} by {amount}{tail};", "spend", binary)


def add(sheet: Dict[str, Any], name: str, amount: int, *, binary: Optional[str] = None) -> AmmunitionOutcome:
    """Shots picked up or bought: the engine raises the stock."""
    if type(amount) is not int or amount <= 0:
        return AmmunitionOutcome(False, reason="an add needs a positive integer amount")
    cid = genesis.character_id(sheet)
    iid = genesis.ammunition_id(sheet, name)
    return _request(sheet, name, f"add {genesis._q(iid)} to {genesis._q(cid)} by {amount};", "add", binary)


def recover(sheet: Dict[str, Any], name: str, *, forfeit: bool = False,
            binary: Optional[str] = None) -> AmmunitionOutcome:
    """After the fight: the engine returns the world's share of the pending count (or none when forfeited)."""
    cid = genesis.character_id(sheet)
    iid = genesis.ammunition_id(sheet, name)
    tail = " by 0" if forfeit else ""
    return _request(sheet, name, f"recover {genesis._q(iid)} from {genesis._q(cid)}{tail};", "recover", binary)


def write_back(row: Dict[str, Any], outcome: AmmunitionOutcome) -> None:
    """Copy the engine's quantity and pending count onto the typed row."""
    row["quantity"] = int(outcome.quantity or 0)
    if outcome.recoverable:
        row["recoverable"] = int(outcome.recoverable)
    else:
        row.pop("recoverable", None)
