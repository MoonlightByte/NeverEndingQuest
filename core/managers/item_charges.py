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

Recharge (H2): every charges world declares the party's clock (absolute game
seconds from the fantasy calendar, the same scalar the effects runtime uses),
so an item whose per-row type recharges is counted up to now by the engine
before the spend; a rule-less item gives identical events with or without a
clock. The engine's normalized state comes back in the ``item_charges`` view
and is stored as ``charges.current``, ``charges.asOf``, ``charges.seed`` and
``charges.nextRecharge`` (an absolute tick, our own int field); a value the
view omits is removed, so the sheet never holds a stale anchor.

Catalog rows (H2b): a row whose ``catalog_id`` names a charged pack type takes
its rule from the pack (genesis.charge_rule). A row on a DICE type (dawn dice,
initial dice, an exhausted roll) needs an engine-minted seed before the world
can declare it from its type: ``mint_rows`` creates the item once in a world
that leaves that row out, with the clock and fresh ``dice seed`` words from
os.urandom, and stores the engine's view (count, max, anchor, seed). A spend
that takes the last charge of a type with an exhausted rule writes the
engine's outcome back: a destroyed unit becomes quantity 0 and unequipped (the
row stays, as the owner ruled), a regain stores the new count and seed.
"""
import copy
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.effects.clock import GameTimeError, scalar_from_calendar
from core.nql import apply, genesis, item_catalog, stats
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


def store_view(charges: Dict[str, Any], view: Dict[str, Any], quantity: Any = 1) -> None:
    """Write the engine's normalized charge state from an ``item_charges`` view
    row onto the sheet's ``charges`` object: ``current`` always; ``asOf`` and
    ``seed`` when the view carries them, removed when it does not;
    ``nextRecharge`` only while the item is below max AND the view's clock is
    live (a view read with the clock absent still prints a boundary, but it is
    inert), and never for a destroyed unit (quantity 0: the engine keeps
    counting a destroyed item's charges while nothing can be spent)."""
    charges["current"] = view["current"]
    for key, stored in (("as_of", "asOf"), ("seed", "seed")):
        if key in view:
            charges[stored] = view[key]
        else:
            charges.pop(stored, None)
    boundary = view.get("next_recharge")
    live = view.get("clock") not in (None, "absent") and quantity != 0
    if live and type(boundary) is int:
        charges["nextRecharge"] = boundary
    else:
        charges.pop("nextRecharge", None)


def party_clock(party: Dict[str, Any]) -> Tuple[Optional[int], Optional[str]]:
    """(absolute game seconds, None) from the party tracker's calendar, or
    (None, reason) when the calendar cannot be read."""
    try:
        return scalar_from_calendar((party or {}).get("worldConditions") or {}), None
    except GameTimeError as error:
        return None, str(error)


def charged_rows(sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every equipment row the engine holds charges for: a valid charges
    object, or a catalog row on a charged type (its state may still be minted)."""
    out = []
    for entry in sheet.get("equipment") or []:
        if not isinstance(entry, dict) or not entry.get("item_name"):
            continue
        if genesis.charges_fields(entry)[0] is not None or genesis.charge_rule(entry) is not None:
            out.append(entry)
    return out


def _declared_from_type(world: genesis.Genesis, iid: str, row: Dict[str, Any]) -> bool:
    """True when the world declares this row ``from`` a charged type (the pack
    type of a catalog row, the per-row type otherwise); an own-fields
    declaration (a gap names why) carries no charges."""
    rule = genesis.charge_rule(row)
    type_id = row.get("catalog_id") if rule is not None and rule.source == "pack" else genesis.charged_type_id(iid)
    return f"item {genesis._q(iid)} from {genesis._q(str(type_id))}" in world.source


def _entropy() -> Tuple[int, int]:
    """Two fresh seed words, each os.urandom(8) >> 1 (the engine's literal range)."""
    return int.from_bytes(os.urandom(8), "big") >> 1, int.from_bytes(os.urandom(8), "big") >> 1


def _write_sheet(path: str, working: Dict[str, Any]) -> Optional[str]:
    """Write the sheet atomically (backup, write, discard or restore). None, or the error."""
    out = _projected(working)
    backup = _backup(path)
    try:
        if not safe_write_json(path, out):
            raise RuntimeError("failed to write the character sheet")
    except Exception as error:
        _restore(path, backup)
        return f"could not save the character sheet: {error}"
    _discard(backup)
    return None


def mint_rows(path: str, working: Dict[str, Any], cid: str, location: str, clock: int,
              retry: Optional[set] = None) -> Tuple[List[str], List[str]]:
    """Mint the charge state of every catalog dice-rule row the world cannot
    declare from its type yet (genesis.mint_reason): one create-only engine
    call per row, in a world WITHOUT that row (the other rows as always), WITH
    the party clock and fresh ``dice seed`` words. A stated count is kept by
    the engine, never rolled; without one the type's initial count applies
    (rolled from the entropy for Luck Blade and Nine Lives Stealer, so for
    that case the drawn words are persisted first in ``chargeMints`` and
    reused on a retry). The engine's VIEW is stored on the row (its real
    quantity untouched) and the sheet is written once. A row whose mint the
    engine refused keeps the reason in ``charges.gap`` and is left alone by
    the refresh until a player action (``retry``) tries it again (R4).
    Returns (names minted, problems). Called under the sheet's locks."""
    equipment = working.get("equipment") or []
    minted: List[str] = []
    problems: List[str] = []
    changed = False
    for index, row in enumerate(equipment):
        if not isinstance(row, dict) or row.get("quantity") == 0 or not genesis.mint_reason(row):
            continue
        charges = row.get("charges") if isinstance(row.get("charges"), dict) else None
        if charges and charges.get("gap") and index not in (retry or set()):
            continue
        catalog = item_catalog.entry(row.get("catalog_id"))
        rule = genesis.pack_charge_rule(catalog)
        iid = row.get("nql_id")
        if rule is None or not isinstance(iid, str):
            continue
        stated = charges.get("current") if charges else None
        if type(stated) is not int or not 0 <= stated <= rule.maximum:
            stated = None
        pending = next((m for m in working.get("chargeMints") or []
                        if isinstance(m, dict) and m.get("nqlId") == iid and genesis.valid_seed(m.get("dice"))), None)
        if pending is not None:
            words, request, tick = genesis.valid_seed(pending["dice"]), str(pending.get("request")), pending.get("clock")
            tick = tick if type(tick) is int else clock
        else:
            words, tick = _entropy(), clock
            request = f"mint:{iid}:{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            if stated is None and rule.initial_dice:
                # The count will be rolled from these words: remember them
                # before the call so a retry of this mint rolls the same.
                mints = [m for m in working.get("chargeMints") or [] if isinstance(m, dict)]
                mints.append({"request": request, "nqlId": iid, "dice": list(words), "clock": tick})
                working["chargeMints"] = mints[-RECEIPTS_KEPT:]
                error = _write_sheet(path, working)
                if error:
                    problems.append(f"{row.get('item_name')}: {error}")
                    continue
        rest = copy.deepcopy(working)
        del rest["equipment"][index]
        world = genesis.build_world([rest], location, clock_tick=tick, dice_seed=words)
        for gap in world.gaps:
            debug(f"MINT: genesis gap: {gap}", category="storage_operations")
        count = f" charges {stated};" if stated is not None else ""
        action = (f"create item {genesis._q(iid)} from {genesis._q(catalog['id'])} {{ owner {genesis._q(cid)}; "
                  f"custody character {genesis._q(cid)};{count} }};")
        try:
            response = apply.call({"world": world.source, "world_name": "mint-genesis.nql",
                                   "actions": action, "actions_name": "mint.nql",
                                   "actor": {"kind": "character", "id": cid}, "request": request,
                                   "item_charges": [iid]})
        except apply.EngineUnavailable as error:
            problems.append(f"{row.get('item_name')}: rules engine unavailable: {error}")
            break
        view = next((v for v in response.get("item_charges") or [] if isinstance(v, dict) and v.get("item") == iid), None)
        if not response.get("ok") or view is None or type(view.get("current")) is not int or type(view.get("max")) is not int:
            why = _refusal(response) if not response.get("ok") else "engine returned no charges view"
            if not isinstance(row.get("charges"), dict):
                row["charges"] = {}
            row["charges"]["gap"] = why
            problems.append(f"{row.get('item_name')}: {why}")
            changed = True
            continue
        if not isinstance(row.get("charges"), dict):
            row["charges"] = {}
        row["charges"].pop("gap", None)
        store_view(row["charges"], view, row.get("quantity", 1))
        row["charges"]["max"] = view["max"]
        working["chargeMints"] = [m for m in working.get("chargeMints") or [] if not (isinstance(m, dict) and m.get("nqlId") == iid)]
        if not working["chargeMints"]:
            working.pop("chargeMints", None)
        minted.append(f"{row.get('item_name')} {view['current']} of {view['max']}")
        changed = True
    if changed:
        error = _write_sheet(path, working)
        if error:
            problems.append(error)
    if minted:
        info(f"MINT: {working.get('name')} charge state set by the engine: {'; '.join(minted)}", category="storage_operations")
    return minted, problems


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


def spend_working(working: Dict[str, Any], index: int, charges: int, clock: Optional[int], location: str,
                  request: str) -> Dict[str, Any]:
    """The engine half of a spend, on an already-prepared sheet copy (ids
    assigned, mint done): declares the sheet with the clock, sends one
    ``expend`` and writes the engine's facts onto the working row (the view's
    normalized state; quantity 0 and unworn on a destroyed unit; the status
    view through stats.store). Takes no lock and writes no file, so the
    agentic combat pipeline (H3) can call it on its in-memory sheet and
    journal the result. Returns {"ok": True, "iid", "view", "event",
    "exhausted", "before", "max", "message"} or {"ok": False, "error"}."""
    row = working["equipment"][index]
    cid = genesis.character_id(working)
    pair, reason = genesis.charges_fields(row)
    if pair is None:
        why = reason or "it has no charges"
        if isinstance(row.get("charges"), dict) and row["charges"].get("gap"):
            why = f"the engine could not set up its charges ({row['charges']['gap']})"
        return {"ok": False, "error": f"{row.get('item_name')} cannot spend charges: {why}"}
    world = genesis.build_world([working], location, clock_tick=clock)
    for gap in world.gaps:
        debug(f"EXPEND: genesis gap: {gap}", category="storage_operations")
    iid = (world.item_ids.get(cid) or {}).get(index)
    if not iid:
        return {"ok": False, "error": "the item was not declared to the engine; nothing changed"}
    if not _declared_from_type(world, iid, row):
        # genesis declared the row without charges (a gap names why);
        # refuse here with that reason rather than let the engine say
        # "no charges" for an item the sheet shows charged.
        marker = repr(row.get("item_name")) + " "
        why = next((g.split("; declared ")[0].split(marker, 1)[1] for g in world.gaps
                    if "; declared " in g and marker in g),
                   "its charges could not be declared to the engine")
        if isinstance(row.get("charges"), dict) and row["charges"].get("gap"):
            why = f"the engine could not set up its charges ({row['charges']['gap']})"
        return {"ok": False, "error": f"{row.get('item_name')} cannot spend charges: {why}"}
    try:
        response = apply.call({"world": world.source, "world_name": "expend-genesis.nql",
                               "actions": f'expend {charges} charges of {genesis._q(iid)} by {genesis._q(cid)};',
                               "actions_name": "expend.nql",
                               "actor": {"kind": "character", "id": cid}, "request": request,
                               "status": [cid], "item_charges": [iid]})
    except apply.EngineUnavailable as error:
        return {"ok": False, "error": f"rules engine unavailable: {error}"}
    if not response.get("ok"):
        return {"ok": False, "error": _refusal(response), "fault": response.get("fault") or {}}

    view = next((v for v in response.get("item_charges") or [] if isinstance(v, dict) and v.get("item") == iid), None)
    if view is None or type(view.get("current")) is not int:
        return {"ok": False, "error": "engine returned no charges view for the item; nothing changed"}
    # Write the engine's facts back from the VIEW row: current (never
    # `available`, which is 0 for a quantity-0 unit, and never the
    # event's `before`, which includes recharge from E2 on).
    target = working["equipment"][index]
    before = target["charges"]["current"]
    # The ChargesExpended event: `before` is the count the engine spent
    # from (recharge included), and `exhausted` the outcome of the
    # type's rule when this spend took the last charge (H2b-3).
    event = next((e.get("charges") for e in (response.get("receipt") or {}).get("events") or []
                  if isinstance(e, dict) and e.get("kind") == "ChargesExpended"
                  and isinstance(e.get("charges"), dict) and e["charges"].get("item") == iid), {})
    exhausted = event.get("exhausted") if isinstance(event.get("exhausted"), dict) else None
    if exhausted is not None and exhausted.get("outcome") == "destroyed":
        # The unit is gone: the row stays at quantity 0 and unworn
        # (the engine unequips it first), and store_view then drops
        # its boundary. The DM narrates how it crumbles.
        target["quantity"] = 0
        target["equipped"] = False
    store_view(target["charges"], view, target.get("quantity", 1))
    target["charges"]["max"] = pair[1]
    # The count the engine spent from, from the event (R2); above the
    # stored count means the item had recharged since the sheet was
    # last written (numbers from the engine, not computed here).
    had = event.get("before") if type(event.get("before")) is int else view["current"] + charges
    status = next((s for s in response.get("status") or []
                   if isinstance(s.get("character"), dict) and s["character"].get("id") == cid), None)
    if status is not None:
        stats.store(working, status)
    name = working.get("name")
    regained = f"; it had recharged to {had} of {pair[1]} since its last use" if had > before else ""
    outcome = ""
    if exhausted is not None:
        face = f" (rolled {exhausted['face']})" if type(exhausted.get("face")) is int else ""
        if exhausted.get("outcome") == "destroyed":
            outcome = f"; its last charge is gone and the item is destroyed{face}"
        elif exhausted.get("outcome") == "regained":
            outcome = (f"; its last charge was spent{face}: it regains {exhausted.get('regained')}, "
                       f"now {view['current']} of {pair[1]}")
        else:
            outcome = f"; its last charge was spent{face}: the item holds"
    message = (f"{name} spent {charges} charge{'s' if charges != 1 else ''} of {target['item_name']} "
               f"({view['current']} of {pair[1]} remain{regained}){outcome}")
    return {"ok": True, "iid": iid, "view": view, "event": event, "exhausted": exhausted, "before": before,
            "max": pair[1], "message": message}


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
    clock, clock_error = party_clock(party)

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
            if row.get("quantity") == 0:
                # A destroyed unit (an exhausted roll) keeps its row and its
                # count, but nothing can be spent; say so before any engine call.
                return {"success": False, "error": f"{row.get('item_name')} was destroyed when its last charge was spent; "
                                                   f"nothing can be spent from it"}
            rule = genesis.charge_rule(row)
            if clock is None and rule is not None and (rule.recharges or genesis.mint_reason(row)):
                # A recharging item is counted from the clock, and a catalog
                # dice item is minted on it; without one the engine refuses
                # the spend (E_CHARGES field clock). Say why in plain words.
                # A rule-less item spends in a clockless world.
                return {"success": False, "error": f"{row.get('item_name')} keeps its charges on the game clock, which could "
                                                   f"not be read ({clock_error}); nothing was spent"}

            working = copy.deepcopy(sheet)
            genesis.assign_ids(working)
            cid = genesis.character_id(working)
            if clock is not None:
                # H2b: a catalog dice row without an engine seed is minted
                # first (the one being used is always tried; the others only
                # when no earlier mint was refused).
                mint_rows(path, working, cid, location, clock, retry={index})
            request = request_id or f"expend:{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            spent = spend_working(working, index, charges, clock, location, request)
            if not spent["ok"]:
                return {"success": False, "error": spent["error"]}
            target = working["equipment"][index]
            view, exhausted = spent["view"], spent["exhausted"]
            message = spent["message"]
            receipts = [r for r in working.get("chargeUses") or [] if isinstance(r, dict)]
            receipt = {"request": request, "nqlId": spent["iid"], "item": target["item_name"], "requested": charges,
                       "before": spent["before"], "after": view["current"], "message": message}
            if exhausted is not None:
                receipt["exhausted"] = exhausted
            receipts.append(receipt)
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


def due_rows(sheet: Dict[str, Any], now: int) -> List[int]:
    """Equipment indexes whose recharge the engine should count now: a row
    with a recharge rule and a unit left whose stored boundary has passed, or
    that has no anchor yet. A row anchored later than now (a restored older
    timeline) is not due: the engine would answer "behind" and change nothing
    on every turn until the clock catches up; its boundary rule covers it from
    then on. Value checks on our own int fields only."""
    out = []
    for index, entry in enumerate(sheet.get("equipment") or []):
        if not isinstance(entry, dict) or entry.get("quantity") == 0:
            continue
        rule = genesis.charge_rule(entry)
        if rule is None:
            continue
        charges = entry.get("charges") if isinstance(entry.get("charges"), dict) else {}
        if charges.get("gap"):
            continue  # R4: the engine refused its mint; a player action retries it
        if genesis.mint_reason(entry):
            out.append(index)  # a catalog dice row awaiting its engine seed (H2b-2)
            continue
        if genesis.charges_fields(entry)[0] is None or not rule.recharges:
            continue
        boundary, anchor = charges.get("nextRecharge"), charges.get("asOf")
        below_max = type(charges.get("current")) is int and type(charges.get("max")) is int and charges["current"] < charges["max"]
        if type(anchor) is not int or (type(boundary) is int and boundary <= now) or (type(boundary) is not int and below_max):
            # No anchor yet; a boundary that has passed; or an anchored row
            # below max with no stored boundary (a full item drops its
            # boundary; a hand-written anchor has none): one view fixes it.
            out.append(index)
    return out


def refresh_sheet(character_name: str, now: int, location: str = "party") -> Dict[str, Any]:
    """Count the recharge of one character's due items and store the engine's
    state. One view-only engine call (no actions, no event, revision 0), so
    repeating it is harmless. {"refreshed": [item names]} or {"error"}."""
    from updates.update_character_info import _get_character_update_lock
    from utils.path_transaction_lock import path_transaction_lock

    path = _resolve(character_name)
    if path is None:
        return {"error": f"no character sheet for {character_name!r}"}
    with _get_character_update_lock(os.path.basename(path)[:-5]):
        with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=30.0) as lease:
            if lease is None:
                return {"error": "the character sheet is busy"}
            sheet = safe_read_json(path)
            if not sheet:
                return {"error": "could not load the character sheet"}
            due = due_rows(sheet, now)
            if not due:
                return {"refreshed": []}
            working = copy.deepcopy(sheet)
            genesis.assign_ids(working)
            cid = genesis.character_id(working)
            # H2b: catalog dice rows without an engine seed are minted first
            # (anchored at now by the engine), then whatever is still due is counted.
            minted, _ = mint_rows(path, working, cid, location, now)
            due = due_rows(working, now)
            if not due:
                return {"refreshed": [], "minted": minted}
            world = genesis.build_world([working], location, clock_tick=now)
            ids = {index: (world.item_ids.get(cid) or {}).get(index) for index in due}
            wanted = [iid for index, iid in ids.items() if iid and _declared_from_type(world, iid, working["equipment"][index])]
            if not wanted:
                return {"refreshed": [], "minted": minted}
            try:
                response = apply.call({"world": world.source, "world_name": "charges-refresh-genesis.nql",
                                       "item_charges": wanted})
            except apply.EngineUnavailable as error:
                return {"error": f"rules engine unavailable: {error}"}
            if not response.get("ok"):
                return {"error": _refusal(response)}
            views = {v.get("item"): v for v in response.get("item_charges") or [] if isinstance(v, dict)}
            refreshed, stored = [], 0
            for index, iid in ids.items():
                view = views.get(iid)
                if view is None or type(view.get("current")) is not int:
                    continue
                row = working["equipment"][index]
                before = row["charges"].get("current")
                store_view(row["charges"], view, row.get("quantity", 1))
                stored += 1
                # Only a count that rose is reported (and shown to the DM); an
                # anchor written on a row's first refresh is stored silently.
                if type(before) is int and view["current"] > before:
                    refreshed.append(f"{row['item_name']} {view['current']} of {row['charges']['max']}")
            if not stored:
                return {"refreshed": [], "minted": minted}
            error = _write_sheet(path, working)
            if error:
                return {"error": error}
            if refreshed:
                info(f"CHARGES: {working.get('name')} recharge counted: {'; '.join(refreshed)}", category="storage_operations")
            else:
                debug(f"CHARGES: {working.get('name')} charge anchors stored for {stored} item(s), nothing regained", category="storage_operations")
            return {"refreshed": refreshed, "minted": minted}


def refresh_party(party_tracker: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """Count due recharges for every party member and companion at the party
    clock. Nothing is called when no row is due; an unreadable calendar skips
    the refresh (the next turn tries again). Never raises."""
    party = party_tracker or safe_json_load("party_tracker.json") or {}
    now, clock_error = party_clock(party)
    if now is None:
        debug(f"CHARGES: refresh skipped, the game clock could not be read ({clock_error})", category="storage_operations")
        return {}
    location = str((party.get("worldConditions") or {}).get("currentLocationId") or "party")
    names = list(party.get("partyMembers") or [])
    names += [npc.get("name") for npc in party.get("partyNPCs") or [] if isinstance(npc, dict) and npc.get("name")]
    result: Dict[str, List[str]] = {}
    for name in names:
        try:
            outcome = refresh_sheet(str(name), now, location)
        except Exception as error:  # fail forward: a refresh never breaks the turn
            debug(f"CHARGES: refresh of {name!r} skipped: {error}", category="storage_operations")
            continue
        if outcome.get("error"):
            debug(f"CHARGES: refresh of {name!r} left to the next turn: {outcome['error']}", category="storage_operations")
        elif outcome.get("refreshed"):
            result[str(name)] = outcome["refreshed"]
    return result
