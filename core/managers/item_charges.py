# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Spending the charges of a charged item (the expendCharges action, item charges H1).

A sheet row with a ``charges`` object is declared to the engine from a per-row
item type (core/nql/genesis.py, charges_fields). One engine request spends an
exact count or is refused and nothing changes; the stored count is rewritten
from the engine's ``item_charges`` view, never from a narration. A receipt on
the sheet (``chargeUses``) answers a retried request id without a second
spend, because the engine keeps no memory of request ids across calls and the
world is rebuilt from the sheet on every call.

No clock, seed or recharge in H1: an item type without a recharge rule spends
in a clockless world (NQL docs/ITEM_CHARGES.md). The view's ``as_of`` and
``seed`` are stored when present so a later engine never reads a sheet lossy.
"""
import copy
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.nql import apply, genesis, stats
from core.managers.item_acquisition import _backup, _discard, _projected, _resolve, _restore
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, info
from utils.file_operations import safe_read_json, safe_write_json

RECEIPTS_KEPT = 20

_FAULT_WORDS = {
    "E_CHARGES": "not enough charges",
    "E_OWNER": "the character does not own that item",
    "E_CUSTODY": "the item is not in the character's hands (it is stowed; take it out first)",
    "E_QUANTITY": "the item is no longer there to use",
    "E_AMOUNT": "the number of charges must be a positive whole number",
    "E_REFERENCE": "the engine does not know that character or item",
}


def _norm(text: Any) -> str:
    return " ".join(str(text or "").split()).casefold()


def charged_rows(sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every equipment row the engine will hold charges for (valid charges object)."""
    out = []
    for entry in sheet.get("equipment") or []:
        if isinstance(entry, dict) and entry.get("item_name") and genesis.charges_fields(entry)[0] is not None:
            out.append(entry)
    return out


def _refusal(response: Dict[str, Any]) -> str:
    fault = response.get("fault") or {}
    code = fault.get("code")
    detail = fault.get("message") or ""
    if not code:
        for diag in response.get("diagnostics") or []:
            if isinstance(diag, dict) and diag.get("code"):
                code, detail = diag["code"], diag.get("message") or ""
                break
    words = _FAULT_WORDS.get(code or "", f"engine refused at {response.get('phase')}")
    if code == "E_CHARGES" and fault.get("actual") is not None:
        words = f"not enough charges ({fault.get('actual')} available, {fault.get('expected')})"
    return f"{words} [{code or 'unknown'}]{(': ' + detail) if detail and code not in _FAULT_WORDS else ''}"


def execute_expend(character_name: str, item_name: str, charges: Any, request_id: Optional[str] = None,
                   party_tracker: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Spend ``charges`` of the character's item. {"success": True, "message"} or {"success": False, "error"}."""
    from updates.update_character_info import _get_character_update_lock
    from utils.path_transaction_lock import path_transaction_lock

    path = _resolve(character_name)
    if path is None:
        return {"success": False, "error": f"no character sheet for {character_name!r}"}
    if type(charges) is bool or type(charges) is not int or charges < 1:
        return {"success": False, "error": "charges must be a positive whole number"}
    wanted = _norm(item_name)
    if not wanted:
        return {"success": False, "error": "itemName is required"}

    party = party_tracker or safe_json_load("party_tracker.json") or {}
    location = str((party.get("worldConditions") or {}).get("currentLocationId") or "party")

    with _get_character_update_lock(os.path.basename(path)[:-5]):
        with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=30.0) as lease:
            if lease is None:
                return {"success": False, "error": "the character sheet is busy; nothing was spent"}
            sheet = safe_read_json(path)
            if not sheet:
                return {"success": False, "error": "could not load the character sheet"}

            # A retried request id: already applied, nothing more to do.
            if request_id:
                for receipt in sheet.get("chargeUses") or []:
                    if isinstance(receipt, dict) and receipt.get("request") == request_id:
                        return {"success": True, "message": receipt.get("message") or "already applied", "replay": True}

            rows = charged_rows(sheet)
            matches = [i for i, e in enumerate(sheet.get("equipment") or [])
                       if isinstance(e, dict) and _norm(e.get("item_name")) == wanted]
            if not matches:
                names = ", ".join(sorted({str(e["item_name"]) for e in rows})) or "none"
                return {"success": False, "error": f"{sheet.get('name')} has no item named {item_name!r}; charged items: {names}"}
            if len(matches) > 1:
                return {"success": False, "error": f"{sheet.get('name')} has {len(matches)} items named {item_name!r}; the spend is ambiguous, nothing changed"}
            index = matches[0]
            row = sheet["equipment"][index]
            pair, reason = genesis.charges_fields(row)
            if pair is None:
                why = reason or "it has no charges"
                return {"success": False, "error": f"{row.get('item_name')} cannot spend charges: {why}"}

            working = copy.deepcopy(sheet)
            genesis.assign_ids(working)
            cid = genesis.character_id(working)
            world = genesis.build_world([working], location)
            for gap in world.gaps:
                debug(f"EXPEND: genesis gap: {gap}", category="storage_operations")
            iid = (world.item_ids.get(cid) or {}).get(index)
            if not iid:
                return {"success": False, "error": "the item was not declared to the engine; nothing changed"}
            request = request_id or f"expend:{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            try:
                response = apply.call({"world": world.source, "world_name": "expend-genesis.nql",
                                       "actions": f'expend {charges} charges of {genesis._q(iid)} by {genesis._q(cid)};',
                                       "actions_name": "expend.nql",
                                       "actor": {"kind": "character", "id": cid}, "request": request,
                                       "status": [cid], "item_charges": [iid]})
            except apply.EngineUnavailable as error:
                return {"success": False, "error": f"rules engine unavailable: {error}"}
            if not response.get("ok"):
                return {"success": False, "error": _refusal(response)}

            view = next((v for v in response.get("item_charges") or [] if isinstance(v, dict) and v.get("item") == iid), None)
            if view is None or type(view.get("current")) is not int:
                return {"success": False, "error": "engine returned no charges view for the item; nothing changed"}
            # Write the engine's facts back from the VIEW row: current (never
            # `available`, which is 0 for a quantity-0 unit, and never the
            # event's `before`, which includes recharge from E2 on).
            target = working["equipment"][index]
            before = target["charges"]["current"]
            target["charges"]["current"] = view["current"]
            target["charges"]["max"] = pair[1]
            for key, stored in (("as_of", "asOf"), ("seed", "seed")):
                if key in view:
                    target["charges"][stored] = view[key]
            status = next((s for s in response.get("status") or []
                           if isinstance(s.get("character"), dict) and s["character"].get("id") == cid), None)
            if status is not None:
                stats.store(working, status)
            name = working.get("name")
            message = (f"{name} spent {charges} charge{'s' if charges != 1 else ''} of {target['item_name']} "
                       f"({view['current']} of {pair[1]} remain)")
            receipts = [r for r in working.get("chargeUses") or [] if isinstance(r, dict)]
            receipts.append({"request": request, "nqlId": iid, "item": target["item_name"], "requested": charges,
                             "before": before, "after": view["current"], "message": message})
            working["chargeUses"] = receipts[-RECEIPTS_KEPT:]
            out = _projected(working)

            backup = _backup(path)
            try:
                if not safe_write_json(path, out):
                    raise RuntimeError("failed to write the character sheet")
            except Exception as error:
                _restore(path, backup)
                return {"success": False, "error": f"could not save the character sheet: {error}"}
            _discard(backup)
            info(f"EXPEND: {message}", category="storage_operations")
            return {"success": True, "message": message}
