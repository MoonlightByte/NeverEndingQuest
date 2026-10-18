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
import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.nql import acquisition, apply, armor_class, genesis, item_catalog, stats
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, info, warning
from utils.file_operations import safe_read_json, safe_write_json

RECEIPTS_KEPT = 50
# P3a: the refusal texts' fixed route for an item that is not listed.
LOOT_ROUTE = "with updateCharacterInfo, or for standard gear with acquireItem by itemName (price 0 for found gear)"


def _present(value: Any) -> bool:
    """A catalogId or itemName is given only as a non-empty string (P3a)."""
    return isinstance(value, str) and value != ""


def _stops():
    from core.combat.invocation import InvocationSupersededError
    from utils.capture.live_provider_call import LiveProviderSuperseded
    from utils.transient_filesystem import ReadOnlySaveStop
    return (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop)


def _waiting(message: str):
    """The dispatch wait: a no-argument callable on the turn's live-provider scope."""
    def wait() -> None:
        from utils.capture.live_provider_call import _interruptible_wait, get_live_provider_scope
        _interruptible_wait(0.25, get_live_provider_scope(), message)
    return wait


def _path_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _held_member_paths(party_tracker: Dict[str, Any], *, wait=None) -> List[str]:
    """The sheet path of each party member and partyNPC, through #1254's one
    member-to-sheet resolver, normalized for comparison and without repeats."""
    from core.ai.action_handler import _party_sheet_path

    party = party_tracker if isinstance(party_tracker, dict) else {}
    names = [m for m in party.get("partyMembers") or []]
    names += [n.get("name") for n in party.get("partyNPCs") or [] if isinstance(n, dict)]
    paths: List[str] = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        key = _path_key(_party_sheet_path(party.get("module"), name, wait=wait))
        if key not in paths:
            paths.append(key)
    return paths


def _holder_sheet(path: str, wait) -> Any:
    """A holder's sheet read-only, for the loot count. With ``wait`` (the
    commit) a busy read waits and a corrupt or missing sheet counts as 0; without
    it (the views) any unreadable sheet counts as 0 with one WARN per stamp."""
    from utils.transient_filesystem import (
        ReadOnlySaveStop, is_transient_filesystem_error, read_bytes_preserving_errors,
        retry_transient_filesystem,
    )

    while True:
        try:
            raw = retry_transient_filesystem(lambda: read_bytes_preserving_errors(path))
            return json.loads(raw.decode("utf-8"))
        except ReadOnlySaveStop:
            raise
        except FileNotFoundError:
            return None
        except OSError as error:
            if wait is None or not is_transient_filesystem_error(error):
                stamp = item_catalog._stamp(path)
                item_catalog._loot_warn((path, stamp, "holder"),
                                        f"{path} could not be read for the loot count ({error}); counted as 0")
                return None
        except ValueError as error:
            stamp = item_catalog._stamp(path)
            item_catalog._loot_warn((path, stamp, "holder"),
                                    f"{path} could not be read for the loot count ({error}); counted as 0")
            return None
        wait()


def _loot_remaining(listing: List[Dict[str, Any]], location_id: str, party_tracker: Dict[str, Any], *,
                    target=None, wait=None) -> List[Dict[str, Any]]:
    """Each listed entry with ``remaining``: authored minus the quantity of every
    held member's receipt from this location for that catalogId (P3a). The
    commit passes ``target=(path, sheet)``, the sheet it read under its lock."""
    if not listing:
        return []
    taken: Dict[str, int] = {}
    target_key = _path_key(target[0]) if target else None
    for key in _held_member_paths(party_tracker, wait=wait):
        sheet = target[1] if key == target_key else _holder_sheet(key, wait)
        receipts = sheet.get("acquisitions") if isinstance(sheet, dict) else None
        for receipt in receipts if isinstance(receipts, list) else []:
            if not isinstance(receipt, dict) or not isinstance(receipt.get("source"), dict):
                continue
            if receipt["source"].get("locationId") != location_id or type(receipt.get("quantity")) is not int:
                continue
            taken[receipt.get("catalogId")] = taken.get(receipt.get("catalogId"), 0) + receipt["quantity"]
    return [dict(e, remaining=max(0, e["authored"] - taken.get(e["catalogId"], 0))) for e in listing]


def _turn_location_id(party: Dict[str, Any]) -> str:
    return str((party.get("worldConditions") or {}).get("currentLocationId") or "party")


def loot_view(location: Any, module: Any, party_tracker: Dict[str, Any], *, wait=None) -> List[Dict[str, Any]]:
    """[{catalogId, name, remaining}] for a location's lootItems, as the DM and
    the validator see them; [] when nothing resolves. Stops propagate."""
    try:
        listing = item_catalog.resolve_loot(location, module, wait=wait)
        if not listing:
            return []
        party = party_tracker if isinstance(party_tracker, dict) else {}
        return [{"catalogId": e["catalogId"], "name": e["name"], "remaining": e["remaining"]}
                for e in _loot_remaining(listing, _turn_location_id(party), party)]
    except _stops():
        raise
    except Exception as error:  # noqa: BLE001 - loot never stops a turn
        location_id = location.get("locationId") if isinstance(location, dict) else None
        item_catalog._loot_warn((location_id, "view"), f"location {location_id}: loot view failed ({error})")
        return []


def listing_text(listing: List[Dict[str, Any]]) -> str:
    """``<catalogId> (<name>)`` entries, or ``(<name>, remaining <n>)`` from the commit's count."""
    return "; ".join(f"{e['catalogId']} ({e['name']}, remaining {e['remaining']})" if "remaining" in e
                     else f"{e['catalogId']} ({e['name']})" for e in listing)


def dispatch_refusal(error: str, listing: List[Dict[str, Any]]) -> str:
    """The dispatch text for a refused catalogId take (section 3.3)."""
    head = (f"Acquire Error: {error}. Nothing changed: no item was added. Later actions from this response have "
            "not executed. Do not repeat earlier completed actions. ")
    if not listing:
        return head + f"No loot is listed here: record the item {LOOT_ROUTE}."
    return head + (f"Loot listed here: {listing_text(listing)}. If the item is listed, use one listed catalogId "
                   "exactly as listed, with quantity no more than remaining (Current Location shows its remaining), "
                   "price 0 or none, for a current party member; being listed is not being seen; when remaining is 0 "
                   f"the party already took it: narrate that it is gone. An item that is not listed is recorded {LOOT_ROUTE}.")


def precheck_refusal(text: str, listing: List[Dict[str, Any]]) -> str:
    """The pre-check text for a refused catalogId take (section 3.3)."""
    head = (f"The previous structured response was rejected before anything was shown: {text}. Keep the outcome "
            "your narration describes and ")
    if not listing:
        return head + f"record the item {LOOT_ROUTE}: no loot is listed here. Return the complete corrected JSON."
    return head + ("correct only that action. If the item is listed, use one listed catalogId exactly as listed, no "
                   "itemName, price 0 or none, a current party member as characterName; a listed item may already be "
                   "gone (Current Location shows its remaining), and being listed is not being seen. Loot listed here: "
                   f"{listing_text(listing)}. An item that is not listed is recorded {LOOT_ROUTE}. Return the complete "
                   "corrected JSON.")


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


def _refresh_attack_rows(sheet: Dict[str, Any], response: Dict[str, Any]) -> None:
    """Item C: the sheet's engine attack rows from the weapon purchase's own views (built after the purchase
    executes, so they hold the new weapon). Never fatal: without the views the rows stay as they are."""
    from core.nql import startup_rows
    try:
        if not isinstance(response.get("attack_options"), list):
            reason = "the engine returned no attack_options view"
        else:
            rows, _ = startup_rows.rows_from_response(response)
            trial = dict(sheet)
            startup_rows.refresh_merge(trial, rows)
            sheet["attacksAndSpellcasting"] = trial["attacksAndSpellcasting"]
            return
    except Exception as error:
        reason = f"{type(error).__name__}: {error}"
    warning(f"ACQUIRE: {sheet.get('name')} attack rows not refreshed ({reason})", category="storage_operations")


def _ammunition_row(sheet: Dict[str, Any], entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rows = [r for r in sheet.get("ammunition") or [] if isinstance(r, dict)]
    for row in rows:
        if str(row.get("name", "")).casefold() == entry["name"].casefold():
            return row
    # #552: the one row already holding this catalog ammunition under an older
    # name takes the purchase; two such rows, or none, keep today's new row.
    held = [r for r in rows if (item_catalog.ammunition_entry(r) or {}).get("id") == entry["id"]]
    return held[0] if len(held) == 1 else None


def _loot_check(item_name: Any, catalog_id: str, quantity: Any, price: Any, party: Any, wait) -> Dict[str, Any]:
    """The sheet-free checks of a catalogId take: the structural check, then the
    listing check. Every result carries ``listing``, from one location read."""
    from core.managers.current_location import current_location_data

    party = party if isinstance(party, dict) else {}
    pack = item_catalog._module_pack(wait=wait)
    try:
        record = current_location_data(party, consumer="acquire_loot", wait=wait)
    except _stops():
        raise
    except Exception as error:  # noqa: BLE001 - an unreadable area lists no loot
        item_catalog._loot_warn((_turn_location_id(party), "area"),
                                f"location {_turn_location_id(party)}: the area could not be read ({error})")
        record = None
    listing = item_catalog.resolve_loot(record, party.get("module"), wait=wait) if record is not None else []
    cid = json.dumps(catalog_id)
    if _present(item_name):
        return {"error": "give either itemName or catalogId, not both", "listing": listing}
    # The entry comes from the pack loaded above with the caller's wait, never a second load on the global wait.
    found = pack["entries"].get(catalog_id)
    if found is None:
        return {"error": f"{cid} is not a module item here", "listing": listing}
    if acquisition.stated_cost(price) not in ((None, ""), (0, "")):
        return {"error": "a listed item is taken at price 0 or with no price", "listing": listing}
    if quantity in (None, ""):
        quantity = 1
    if type(quantity) is not int or quantity < 1:
        return {"error": "quantity must be a whole number of at least 1", "listing": listing}
    if not any(e["catalogId"] == catalog_id for e in listing):
        return {"error": f"{cid} is not listed at the current location", "listing": listing}
    return {"entry": found, "quantity": quantity, "cost": 0, "rule": None, "listing": listing}


def catalog_check(item_name: Any, quantity: Any, price: Any = None, kind: Any = None, *,
                  catalog_id: Any = None, party: Any = None, wait=None) -> Dict[str, Any]:
    """The checks of one acquisition that need no sheet and no purse (#878).

    Returns {"entry", "quantity", "cost", "rule"} or {"error": reason}, with
    the reasons execute_acquisition has always returned. The DM's draft is
    checked with it before review and display; the purchase runs it again.
    With a ``catalog_id`` (P3a) the take is checked against the current
    location's lootItems, read from ``party`` with ``wait``, and every result
    carries ``listing``; ``kind`` is ignored.
    """
    if _present(catalog_id):
        return _loot_check(item_name, catalog_id, quantity, price, party, wait)
    entry, reason = acquisition.find_entry(item_name, kind)
    if entry is None:
        return {"error": reason}
    if quantity in (None, ""):
        quantity = 1
    if type(quantity) is bool or type(quantity) is not int or quantity < 1:
        return {"error": "quantity must be a positive whole number"}
    stated, reason = acquisition.stated_cost(price)
    if reason:
        return {"error": reason}
    if stated is None:
        cost, reason = acquisition.lot_cost(entry, quantity)
        if cost is None:
            return {"error": reason}
    else:
        cost = stated
        per_lot = (entry.get("price") or {}).get("units_per_lot")
        if type(per_lot) is int and per_lot > 1 and quantity % per_lot:
            return {"error": (f"{entry['name']} is sold in lots of {per_lot}: quantity counts single items "
                              f"and must be {per_lot}, {2 * per_lot}, ... (one lot = quantity {per_lot})")}
    # H2b-4: a charged catalog type (an SRD magic item) is one physical unit.
    rule = genesis.pack_charge_rule(entry)
    if rule is not None and quantity != 1:
        return {"error": f"{entry['name']} is one charged item; acquire it one at a time (quantity 1)"}
    return {"entry": entry, "quantity": quantity, "cost": cost, "rule": rule}


def execute_acquisition(character_name: str, item_name: str, quantity: Any, price: Any = None,
                        request_id: Optional[str] = None,
                        party_tracker: Optional[Dict[str, Any]] = None, kind: Any = None, *,
                        catalog_id: Any = None) -> Dict[str, Any]:
    """Run one acquisition. Returns {"success": bool, "message": str} or {"success": False, "error": str}.

    With a ``catalog_id`` (P3a) the item is a listed module loot item, taken at
    no cost; every error result then carries ``listing`` for the refusal text."""
    if not _present(catalog_id):
        return _acquire(character_name, item_name, quantity, price, request_id, party_tracker, kind, None, {})
    loot: Dict[str, Any] = {}
    result = _acquire(character_name, item_name, quantity, price, request_id, party_tracker, kind, catalog_id, loot)
    if not result.get("success"):
        result.setdefault("listing", loot.get("listing") or [])
    return result


def _acquire(character_name, item_name, quantity, price, request_id, party_tracker, kind, catalog_id,
             loot) -> Dict[str, Any]:
    from updates.update_character_info import _get_character_update_lock
    from utils.path_transaction_lock import path_transaction_lock

    if catalog_id is not None:
        # P3a: the party read and the sheet-free check come first, so every
        # error, main's "no character sheet" included, has its listing.
        party = party_tracker or safe_json_load("party_tracker.json") or {}
        checked = catalog_check(item_name, quantity, price, kind, catalog_id=catalog_id, party=party,
                                wait=_waiting("Checking the area..."))
        loot["listing"] = checked["listing"]
    path = _resolve(character_name)
    if path is None:
        return {"success": False, "error": f"no character sheet for {character_name!r}"}
    if catalog_id is None:
        checked = catalog_check(item_name, quantity, price, kind)
    if "error" in checked:
        return {"success": False, "error": checked["error"]}
    entry, quantity, cost, rule = checked["entry"], checked["quantity"], checked["cost"], checked["rule"]
    count_wait = _waiting("Checking the party's sheets...")
    if catalog_id is not None and _path_key(path) not in _held_member_paths(party, wait=count_wait):
        return {"success": False, "error": f"{json.dumps(character_name)} is not a current party member"}

    # H2b-4: a charged item's purchase world carries the party clock (the
    # engine anchors the new item's recharge at purchase) and, for a type that
    # rolls dice, fresh ``dice seed`` words (the engine draws the item's seed
    # from them). The item's charge state is stored from the engine's view.
    from core.managers.item_charges import _entropy, party_clock, store_view

    if catalog_id is None:
        party = party_tracker or safe_json_load("party_tracker.json") or {}
    location = str((party.get("worldConditions") or {}).get("currentLocationId") or "party")
    clock, clock_error = party_clock(party) if rule is not None else (None, None)
    if rule is not None and clock is None:
        debug(f"ACQUIRE: {entry['name']} bought without the game clock ({clock_error}); its recharge anchors at first use",
              category="storage_operations")
    dice = _entropy() if rule is not None and rule.uses_dice else None

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

            if catalog_id is not None:
                # The commit's count, inside the target's lock (G9).
                counted = _loot_remaining(loot["listing"], location, party, target=(path, sheet), wait=count_wait)
                left = next(e["remaining"] for e in counted if e["catalogId"] == entry["id"])
                if quantity > left:
                    loot["listing"] = counted
                    return {"success": False, "error": f"only {left} of {json.dumps(entry['id'])} remain here"}

            purse = acquisition.balance(sheet)
            delta = acquisition.pay(purse, cost)
            if delta is None:
                return {"success": False, "error": (f"{sheet.get('name')} cannot pay {cost} copper worth for "
                                                    f"{quantity} {entry['name']} (purse: {acquisition.purse_text(purse)})")}

            working = copy.deepcopy(sheet)
            held = genesis.held_ids_on_disk()  # nothing is written before the buy below
            genesis.assign_ids(working, reserved=held)
            cid = genesis.character_id(working)
            world = genesis.build_world([working], location, clock_tick=clock, dice_seed=dice,
                                        module_ids=[entry["id"]] if catalog_id is not None else None)
            for gap in world.gaps:
                debug(f"ACQUIRE: genesis gap: {gap}", category="storage_operations")

            ammunition = entry.get("kind") == "ammunition"
            if ammunition:
                row = _ammunition_row(working, entry)
                iid = genesis.ammunition_id(working, row["name"] if row else entry["name"])
                lines = acquisition.coin_lines(cid, delta) + [
                    acquisition.ammunition_lines(cid, iid, entry["name"], quantity, row is not None)]
            else:
                iid = acquisition.next_item_id(working, entry, reserved=held)
                lines = acquisition.coin_lines(cid, delta) + [acquisition.item_line(cid, iid, entry, quantity)]
            request = request_id or f"acquire:{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            document = {"world": world.source, "world_name": "acquire-genesis.nql",
                        "actions": "\n".join(lines), "actions_name": "acquire.nql",
                        "actor": {"kind": "character", "id": cid}, "request": request,
                        "status": [cid], "items_at": [{"kind": "character", "id": cid}],
                        "item_definitions": [entry["id"]]}
            if rule is not None and not ammunition:
                document["item_charges"] = [iid]
            weapon = entry.get("kind") == "weapon"
            if weapon:
                # Item C: the same call returns the attack views for the engine rows; 0 extra calls.
                document["equipment"] = [cid]
                document["attack_options"] = [cid]
            try:
                response = apply.call(document)
                if weapon and not response.get("ok") and response.get("phase") == "input":
                    # An older engine refuses the views at input: today's document; the rows stay as they are.
                    response = apply.call({k: v for k, v in document.items() if k not in ("equipment", "attack_options")})
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
                    # #822: a new row keeps the catalog's typed id; a top-up (found by name) is left as it is.
                    working.setdefault("ammunition", []).append(
                        {"name": entry["name"], "quantity": int(created.get("quantity", quantity)),
                         "description": entry.get("description", ""), "catalog_id": entry["id"]})
                landed = f"{created.get('quantity', quantity)} {entry['name']}" + (
                    f" in the {row['name']} stock" if row is not None and row["name"] != entry["name"]
                    else " in the ammunition stock")
            else:
                row = acquisition.row_from_views(created, definition, entry)
                if rule is not None:
                    view = next((v for v in response.get("item_charges") or []
                                 if isinstance(v, dict) and v.get("item") == iid), None)
                    if view is None or type(view.get("current")) is not int or type(view.get("max")) is not int:
                        return {"success": False, "error": "engine returned no charges view for the new item; nothing was bought"}
                    row["charges"] = {"max": view["max"]}
                    store_view(row["charges"], view, row.get("quantity", 1))
                working.setdefault("equipment", []).append(row)
                if weapon:
                    _refresh_attack_rows(working, response)
                landed = f"{quantity} {entry['name']}"
                if rule is not None:
                    landed += f" ({row['charges']['current']} of {row['charges']['max']} charges)"
            message = (f"{working.get('name')} acquired {landed} ({acquisition.describe_coins(delta)}; "
                       f"purse now {acquisition.purse_text(working['currency'])})")
            receipts = [r for r in working.get("acquisitions") or [] if isinstance(r, dict)]
            receipt = {"request": request, "catalogId": entry["id"], "nqlId": iid, "quantity": quantity,
                       "paid": {k: -v for k, v in delta.items() if v < 0},
                       "change": {k: v for k, v in delta.items() if v > 0}, "message": message}
            if dice is not None:
                receipt["dice"] = list(dice)
            if catalog_id is not None:
                receipt["source"] = {"locationId": location}
            receipts.append(receipt)
            # P3a: a receipt with a source counts listed loot, so it is never trimmed.
            plain = [i for i, r in enumerate(receipts) if "source" not in r]
            kept = set(plain[-RECEIPTS_KEPT:])
            working["acquisitions"] = [r for i, r in enumerate(receipts) if "source" in r or i in kept]
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
