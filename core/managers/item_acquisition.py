# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""A party character acquires an item from the SRD catalog (the acquireItem action).

One engine request pays the price (the host makes change) and creates the item
from its catalog type; the sheet is rewritten from the engine's views, or
nothing changes. A receipt on the sheet (``acquisitions``) answers a retried
request id as already applied: a world rebuilt from the sheets has no history
(kit acquire_gate.py), so the host guards its own retries.
"""
import copy
import os
import shutil
from datetime import datetime
from typing import Any, Dict, Optional

from core.nql import acquisition, apply, armor_class, genesis, stats
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, info, warning
from utils.file_operations import safe_read_json, safe_write_json

RECEIPTS_KEPT = 50


def _resolve(character_name: str) -> Optional[str]:
    from core.managers.item_transfer import _resolve as resolve
    return resolve(character_name)


def _backup(path: str) -> Optional[str]:
    backup = f"{path}.acquire.bak"
    try:
        shutil.copy2(path, backup)
        return backup
    except OSError:
        return None


def _restore(path: str, backup: Optional[str]) -> None:
    if backup and os.path.exists(backup):
        try:
            shutil.copy2(backup, path)
        except OSError:
            pass


def _discard(backup: Optional[str]) -> None:
    if backup and os.path.exists(backup):
        try:
            os.remove(backup)
        except OSError:
            pass


def _projected(sheet: Dict[str, Any]) -> Dict[str, Any]:
    projection = armor_class.project(sheet)
    if projection.applied:
        return projection.sheet
    warning(f"ACQUIRE: armor class projection not applied for {sheet.get('name')}: {projection.reason}",
            category="storage_operations")
    return sheet


def _ammunition_row(sheet: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    for row in sheet.get("ammunition") or []:
        if isinstance(row, dict) and str(row.get("name", "")).casefold() == name.casefold():
            return row
    return None


def execute_acquisition(character_name: str, item_name: str, quantity: Any, price: Any = None,
                        request_id: Optional[str] = None,
                        party_tracker: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run one acquisition. Returns {"success": bool, "message": str} or {"success": False, "error": str}."""
    from updates.update_character_info import _get_character_update_lock
    from utils.path_transaction_lock import path_transaction_lock

    path = _resolve(character_name)
    if path is None:
        return {"success": False, "error": f"no character sheet for {character_name!r}"}
    entry, reason = acquisition.find_entry(item_name)
    if entry is None:
        return {"success": False, "error": reason}
    if quantity in (None, ""):
        quantity = 1
    if type(quantity) is bool or type(quantity) is not int or quantity < 1:
        return {"success": False, "error": "quantity must be a positive whole number"}
    stated, reason = acquisition.stated_cost(price)
    if reason:
        return {"success": False, "error": reason}
    if stated is None:
        cost, reason = acquisition.lot_cost(entry, quantity)
        if cost is None:
            return {"success": False, "error": reason}
    else:
        cost = stated
        per_lot = (entry.get("price") or {}).get("units_per_lot")
        if type(per_lot) is int and per_lot > 1 and quantity % per_lot:
            return {"success": False, "error": (f"{entry['name']} is sold in lots of {per_lot}: quantity counts single items "
                                                f"and must be {per_lot}, {2 * per_lot}, ... (one lot = quantity {per_lot})")}

    party = party_tracker or safe_json_load("party_tracker.json") or {}
    location = str((party.get("worldConditions") or {}).get("currentLocationId") or "party")

    with _get_character_update_lock(os.path.basename(path)[:-5]):
        with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=30.0) as lease:
            if lease is None:
                return {"success": False, "error": "the character sheet is busy; nothing was bought"}
            sheet = safe_read_json(path)
            if not sheet:
                return {"success": False, "error": "could not load the character sheet"}

            # A retried request id: already applied, nothing more to do.
            if request_id:
                for receipt in sheet.get("acquisitions") or []:
                    if isinstance(receipt, dict) and receipt.get("request") == request_id:
                        return {"success": True, "message": receipt.get("message") or "already applied", "replay": True}

            purse = acquisition.balance(sheet)
            delta = acquisition.pay(purse, cost)
            if delta is None:
                return {"success": False, "error": (f"{sheet.get('name')} cannot pay {cost} copper worth for "
                                                    f"{quantity} {entry['name']} (purse: {acquisition.purse_text(purse)})")}

            working = copy.deepcopy(sheet)
            genesis.assign_ids(working)
            cid = genesis.character_id(working)
            world = genesis.build_world([working], location)
            for gap in world.gaps:
                debug(f"ACQUIRE: genesis gap: {gap}", category="storage_operations")

            ammunition = entry.get("kind") == "ammunition"
            if ammunition:
                row = _ammunition_row(working, entry["name"])
                iid = genesis.ammunition_id(working, row["name"] if row else entry["name"])
                lines = acquisition.coin_lines(cid, delta) + [
                    acquisition.ammunition_lines(cid, iid, entry["name"], quantity, row is not None)]
            else:
                iid = acquisition.next_item_id(working, entry)
                lines = acquisition.coin_lines(cid, delta) + [acquisition.item_line(cid, iid, entry, quantity)]
            request = request_id or f"acquire:{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            try:
                response = apply.call({"world": world.source, "world_name": "acquire-genesis.nql",
                                       "actions": "\n".join(lines), "actions_name": "acquire.nql",
                                       "actor": {"kind": "character", "id": cid}, "request": request,
                                       "status": [cid], "items_at": [{"kind": "character", "id": cid}],
                                       "item_definitions": [entry["id"]]})
            except apply.EngineUnavailable as error:
                return {"success": False, "error": f"rules engine unavailable: {error}"}
            if not response.get("ok"):
                fault = response.get("fault") or {}
                if fault.get("code") == "E_INSUFFICIENT_RESOURCE":
                    reason = f"{sheet.get('name')} cannot pay (balance would go below zero)"
                else:
                    reason = f"engine refused at {response.get('phase')}: {response.get('diagnostics') or fault or response.get('error')}"
                return {"success": False, "error": reason}

            # Write the engine's facts back: coins and totals, then the item.
            status = next((s for s in response.get("status") or []
                           if isinstance(s.get("character"), dict) and s["character"].get("id") == cid), None)
            if status is None:
                return {"success": False, "error": "engine returned no status for the character"}
            resources = status.get("resources") or {}
            if any(c not in resources for c in acquisition.COIN_ORDER):
                return {"success": False, "error": "engine returned no coin balance"}
            working["currency"] = {c: int(resources[c]["current"]) for c in acquisition.COIN_ORDER}
            stats.store(working, status)
            items = {i["id"]: i for v in response.get("items_at") or [] for i in v.get("items") or []}
            created = items.get(iid)
            if created is None:
                return {"success": False, "error": "engine returned no view of the new item"}
            definitions = response.get("item_definitions") or []
            definition = definitions[0] if definitions and isinstance(definitions[0], dict) else None
            if ammunition:
                if row is not None:
                    row["quantity"] = int(created.get("quantity", 0))
                else:
                    working.setdefault("ammunition", []).append(
                        {"name": entry["name"], "quantity": int(created.get("quantity", quantity)),
                         "description": entry.get("description", "")})
                landed = f"{created.get('quantity', quantity)} {entry['name']} in the ammunition stock"
            else:
                working.setdefault("equipment", []).append(acquisition.row_from_views(created, definition, entry))
                landed = f"{quantity} {entry['name']}"
            message = (f"{working.get('name')} acquired {landed} ({acquisition.describe_coins(delta)}; "
                       f"purse now {acquisition.purse_text(working['currency'])})")
            receipts = [r for r in working.get("acquisitions") or [] if isinstance(r, dict)]
            receipts.append({"request": request, "catalogId": entry["id"], "nqlId": iid, "quantity": quantity,
                             "paid": {k: -v for k, v in delta.items() if v < 0},
                             "change": {k: v for k, v in delta.items() if v > 0}, "message": message})
            working["acquisitions"] = receipts[-RECEIPTS_KEPT:]
            out = _projected(working)

            backup = _backup(path)
            try:
                if not safe_write_json(path, out):
                    raise RuntimeError("failed to write the character sheet")
            except Exception as error:
                _restore(path, backup)
                _discard(backup)
                return {"success": False, "error": f"{error}; sheet restored"}
            _discard(backup)

    if out.get("armorClass") != sheet.get("armorClass"):
        message += f". Armor class now {out.get('armorClass')}"
    info(f"SUCCESS: {message}", category="storage_operations")
    return {"success": True, "message": message, "nql_id": iid, "catalog_id": entry["id"]}
