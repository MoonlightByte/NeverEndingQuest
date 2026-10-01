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
from typing import Any, Dict, Optional

from core.nql import apply, genesis


@dataclass
class AmmunitionOutcome:
    ok: bool
    quantity: Optional[int] = None      # the stock after the request
    recoverable: Optional[int] = None   # the pending count after the request
    reason: str = ""
    fault: Optional[Dict[str, Any]] = None
    receipt: Optional[Dict[str, Any]] = None


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
