# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Coins between party characters (the transferCurrency and splitCurrency actions).

The engine decides the move (core/nql/currency.py); this module owns the
files: it resolves every sheet, holds every character lease in path order,
writes all sheets with backup and rollback, and reports a one-line result.
A refusal writes nothing.
"""
import os
from contextlib import ExitStack
from typing import Any, Dict, List, Optional

from core.managers.item_transfer import _backup, _discard, _resolve, _restore
from core.nql import currency as nql_currency
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, info
from utils.file_operations import safe_read_json, safe_write_json


def _coins(text: Dict[str, int]) -> str:
    parts = [f"{amount} {coin}" for coin, amount in text.items() if amount]
    return ", ".join(parts) if parts else "no coins"


def _run(paths: List[str], build, party_tracker: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Lock every path in order, load the sheets, run ``build(sheets, location)``, write all or none."""
    from updates.update_character_info import _get_character_update_lock
    from utils.path_transaction_lock import path_transaction_lock

    if len(set(os.path.normcase(os.path.realpath(p)) for p in paths)) != len(paths):
        return {"success": False, "error": "the same character appears twice"}
    party = party_tracker or safe_json_load("party_tracker.json") or {}
    location = str((party.get("worldConditions") or {}).get("currentLocationId") or "party")
    ordered = sorted(paths)
    with ExitStack() as stack:
        for path in ordered:
            stack.enter_context(_get_character_update_lock(os.path.basename(path)[:-5]))
        for path in ordered:
            lease = stack.enter_context(path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=30.0))
            if lease is None:
                return {"success": False, "error": "a character sheet is busy; nothing was moved"}
        sheets = [safe_read_json(p) for p in paths]
        if not all(sheets):
            return {"success": False, "error": "could not load every character sheet"}
        outcome = build(sheets, location)
        for gap in outcome.gaps:
            debug(f"CURRENCY: genesis gap: {gap}", category="storage_operations")
        if not outcome.ok:
            return {"success": False, "error": outcome.reason}
        backups = [_backup(p) for p in paths]
        try:
            for path, sheet in zip(paths, outcome.sheets):
                if not safe_write_json(path, sheet):
                    raise RuntimeError(f"failed to write {os.path.basename(path)}")
        except Exception as error:
            for path, backup in zip(paths, backups):
                _restore(path, backup)
                _discard(backup)
            return {"success": False, "error": f"{error}; all sheets restored"}
        for backup in backups:
            _discard(backup)
    return {"success": True, "outcome": outcome, "sheets": sheets}


def execute_currency_transfer(from_character: str, to_character: str, amounts: Dict[str, Any],
                              party_tracker: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Hand named coins from one party character to another. {"success", "message"|"error"}."""
    giver_path = _resolve(from_character)
    receiver_path = _resolve(to_character)
    if giver_path is None:
        return {"success": False, "error": f"no character sheet for giver {from_character!r}"}
    if receiver_path is None:
        return {"success": False, "error": f"no character sheet for receiver {to_character!r}"}
    result = _run([giver_path, receiver_path],
                  lambda sheets, loc: nql_currency.transfer(sheets[0], sheets[1], amounts, location=loc),
                  party_tracker)
    if not result.get("success"):
        return result
    outcome, before = result["outcome"], result["sheets"]
    after = outcome.sheets
    message = (f"{before[0].get('name')} gave {_coins(outcome.moved.get(str(before[1].get('name')), {}))} to "
               f"{before[1].get('name')}. Balances now: {before[0].get('name')} {_coins(after[0]['currency'])}; "
               f"{before[1].get('name')} {_coins(after[1]['currency'])}")
    info(f"SUCCESS: {message}", category="storage_operations")
    return {"success": True, "message": message}


def execute_currency_split(from_character: str, to_characters: List[str], giver_keeps_share: bool = True,
                           party_tracker: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Split the giver's coins evenly with the named party characters."""
    if not isinstance(to_characters, list) or not to_characters:
        return {"success": False, "error": "splitCurrency needs a list of recipients"}
    giver_path = _resolve(from_character)
    if giver_path is None:
        return {"success": False, "error": f"no character sheet for giver {from_character!r}"}
    paths = [giver_path]
    for name in to_characters:
        path = _resolve(name)
        if path is None:
            return {"success": False, "error": f"no character sheet for recipient {name!r}"}
        paths.append(path)
    result = _run(paths,
                  lambda sheets, loc: nql_currency.split(sheets[0], sheets[1:], giver_keeps_share=bool(giver_keeps_share),
                                                         location=loc),
                  party_tracker)
    if not result.get("success"):
        return result
    outcome, before = result["outcome"], result["sheets"]
    after = outcome.sheets
    shares = "; ".join(f"{s.get('name')} received {_coins(outcome.moved.get(str(s.get('name')), {}))}" for s in before[1:])
    message = (f"{before[0].get('name')} split coins evenly: {shares}. Balances now: "
               + "; ".join(f"{s.get('name')} {_coins(a['currency'])}" for s, a in zip(before, after)))
    info(f"SUCCESS: {message}", category="storage_operations")
    return {"success": True, "message": message}
