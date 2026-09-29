# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Coins as engine resources (E6).

Every character carries ``gold``, ``silver`` and ``copper`` as engine resources
with a floor of zero (genesis). A change is a signed whole-number delta per
coin type: a negative amount is a ``spend`` (refused when the balance cannot
cover it), a positive amount is a ``heal`` (an exact credit). All lines of one
request commit together or not at all, so a handoff or an even split across
several sheets can never leave coins duplicated or lost between them. The
balances written back to the sheets are the engine's, never a number computed
here or by a model.

Nothing in this module reads prose or writes files.
"""
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import apply, genesis

COIN_TYPES = genesis.COIN_TYPES


@dataclass
class CurrencyOutcome:
    ok: bool
    sheets: List[Dict[str, Any]] = field(default_factory=list)   # new copies, same order as given
    moved: Dict[str, Dict[str, int]] = field(default_factory=dict)  # receiver name -> coins received
    receipt: Optional[Dict[str, Any]] = None
    reason: str = ""
    fault: Optional[Dict[str, Any]] = None
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    return genesis._q(value)


def _balance(sheet: Dict[str, Any]) -> Dict[str, int]:
    coins = sheet.get("currency") if isinstance(sheet.get("currency"), dict) else {}
    return {c: (coins.get(c) if type(coins.get(c)) is int and coins.get(c) >= 0 else 0) for c in COIN_TYPES}


def normalize_delta(delta: Any) -> Tuple[Optional[Dict[str, int]], str]:
    """A {coin: signed int} mapping restricted to the three coin types, or a reason."""
    if not isinstance(delta, dict):
        return None, "currency delta must be an object of signed whole numbers per coin type"
    out: Dict[str, int] = {}
    for coin, amount in delta.items():
        if coin not in COIN_TYPES:
            return None, f"unknown coin type {coin!r}; use gold, silver, copper"
        if type(amount) is bool or type(amount) is not int:
            return None, f"{coin} delta {amount!r} is not a whole number"
        if amount:
            out[coin] = amount
    return out, ""


def _lines(cid: str, delta: Dict[str, int]) -> List[str]:
    lines = []
    for coin, amount in delta.items():
        verb = "spend" if amount < 0 else "heal"
        lines.append(f'{verb} {_q(cid)} resource {_q(coin)} by {abs(amount)};')
    return lines


def _run(sheets: List[Dict[str, Any]], actions: List[str], actor: str, request_id: Optional[str],
         binary: Optional[str], location: str) -> CurrencyOutcome:
    """Submit the lines against a world built from the sheets; write engine balances back."""
    sheets = [copy.deepcopy(s) for s in sheets]
    world = genesis.build_world(sheets, location)
    ids = [genesis.character_id(s) for s in sheets]
    if len(set(ids)) != len(ids):
        return CurrencyOutcome(False, reason="two of the characters resolve to the same engine id", gaps=world.gaps)
    if not actions:
        return CurrencyOutcome(True, sheets=sheets, gaps=world.gaps)
    try:
        response = apply.call({"world": world.source, "world_name": "currency-genesis.nql",
                               "actions": "\n".join(actions), "actions_name": "currency.nql",
                               "actor": {"kind": "character", "id": actor},
                               "request": request_id or f"currency:{uuid.uuid4().hex}",
                               "status": ids}, binary=binary)
    except apply.EngineUnavailable as error:
        return CurrencyOutcome(False, reason=str(error), gaps=world.gaps)
    if not response.get("ok"):
        fault = response.get("fault") or {}
        if fault.get("code") == "E_INSUFFICIENT_RESOURCE":
            reason = (f"{fault.get('subject')} cannot pay: {fault.get('actual')} {fault.get('field')}"
                      " (balance would go below zero)")
        else:
            reason = f"engine refused at {response.get('phase')}: {response.get('diagnostics') or fault or response.get('error')}"
        return CurrencyOutcome(False, reason=reason, fault=fault or None, gaps=world.gaps)
    balances = {}
    for status in response.get("status") or []:
        who = status.get("character") if isinstance(status.get("character"), dict) else {}
        sid = who.get("id")
        resources = status.get("resources") or {}
        balances[sid] = {c: int(resources[c]["current"]) for c in COIN_TYPES if c in resources}
    for sheet, cid in zip(sheets, ids):
        if cid not in balances or len(balances[cid]) != len(COIN_TYPES):
            return CurrencyOutcome(False, reason="engine returned no balance for a character", gaps=world.gaps)
        sheet["currency"] = dict(balances[cid])
    return CurrencyOutcome(True, sheets=sheets, receipt=response.get("receipt"), gaps=world.gaps)


def apply_delta(sheet: Dict[str, Any], delta: Any, *, location: str = "sheet", request_id: Optional[str] = None,
                binary: Optional[str] = None) -> CurrencyOutcome:
    """One character's signed coin change (a T079 ``currencyDelta``) through the engine."""
    normalized, reason = normalize_delta(delta)
    if normalized is None:
        return CurrencyOutcome(False, reason=reason)
    cid = genesis.character_id(sheet)
    return _run([sheet], _lines(cid, normalized), cid, request_id, binary, location)


def transfer(giver: Dict[str, Any], receiver: Dict[str, Any], amounts: Any, *, location: str = "party",
             request_id: Optional[str] = None, binary: Optional[str] = None) -> CurrencyOutcome:
    """Coins from the giver to the receiver in one request; ``amounts`` are non-negative per coin."""
    normalized, reason = normalize_delta(amounts)
    if normalized is None:
        return CurrencyOutcome(False, reason=reason)
    if any(v < 0 for v in normalized.values()):
        return CurrencyOutcome(False, reason="amounts to hand over must not be negative")
    if not normalized:
        return CurrencyOutcome(False, reason="no coins named")
    gid, rid = genesis.character_id(giver), genesis.character_id(receiver)
    if gid == rid:
        return CurrencyOutcome(False, reason="giver and receiver are the same character")
    actions = _lines(gid, {c: -v for c, v in normalized.items()}) + _lines(rid, normalized)
    outcome = _run([giver, receiver], actions, gid, request_id, binary, location)
    if outcome.ok:
        outcome.moved = {str(receiver.get("name")): dict(normalized)}
    return outcome


def split(giver: Dict[str, Any], receivers: List[Dict[str, Any]], *, giver_keeps_share: bool = True,
          location: str = "party", request_id: Optional[str] = None, binary: Optional[str] = None) -> CurrencyOutcome:
    """Divide every coin type of the giver evenly; remainders stay with the giver.

    Each receiver gets the giver's balance divided (whole numbers) by the number
    of shares: the receivers plus the giver when ``giver_keeps_share`` is true
    ("split it with you"), the receivers alone when false ("hand it all out
    among you"). The engine moves every share in one request.
    """
    if not receivers:
        return CurrencyOutcome(False, reason="no one to split with")
    gid = genesis.character_id(giver)
    rids = [genesis.character_id(r) for r in receivers]
    if gid in rids or len(set(rids)) != len(rids):
        return CurrencyOutcome(False, reason="split recipients must be distinct characters other than the giver")
    balance = _balance(giver)
    shares = len(receivers) + (1 if giver_keeps_share else 0)
    share = {c: balance[c] // shares for c in COIN_TYPES}
    share = {c: v for c, v in share.items() if v}
    if not share:
        return CurrencyOutcome(False, reason="the giver has too few coins to split")
    actions = _lines(gid, {c: -v * len(receivers) for c, v in share.items()})
    for rid in rids:
        actions += _lines(rid, share)
    outcome = _run([giver] + list(receivers), actions, gid, request_id, binary, location)
    if outcome.ok:
        outcome.moved = {str(r.get("name")): dict(share) for r in receivers}
    return outcome
