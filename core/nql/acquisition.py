# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Buying (or being given) an item from the SRD item pack (the acquireItem action).

The host computes the price and makes change; the engine never converts coins
(NQL docs/ITEM_CATALOG.md). One engine request carries the coin lines and the
``create item ... from`` line, so the coins and the item commit together or
not at all. The sheet row is derived from the engine's views (the item and its
type), never authored by a model. Reference: kit acquire_gate.py (lot_cost,
pay, acquire_lines, sheet_row).
"""
import copy
from typing import Any, Dict, List, Optional, Tuple

from core.nql import genesis, item_catalog

COPPER = {"copper": 1, "silver": 10, "gold": 100}
COIN_ORDER = ("gold", "silver", "copper")


def _q(value: str) -> str:
    return genesis._q(value)


def find_entry(item_name: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """The catalog entry whose typed ``name`` equals ``item_name`` (exact, then a
    unique case-insensitive match), or (None, reason). A value comparison on
    the catalog's name field, the same comparison transferItem makes against
    sheet rows."""
    if not isinstance(item_name, str) or not item_name.strip():
        return None, "itemName must name a catalog item"
    wanted = item_name.strip()
    entries = list(item_catalog.entries().values())
    exact = [e for e in entries if e.get("name") == wanted]
    if len(exact) == 1:
        return exact[0], ""
    loose = [e for e in entries if str(e.get("name", "")).casefold() == wanted.casefold()]
    if len(loose) == 1:
        return loose[0], ""
    return None, f"{wanted!r} is not an item in the SRD catalog"


def lot_cost(entry: Dict[str, Any], quantity: Any) -> Tuple[Optional[int], str]:
    """(copper, "") for ``quantity`` items, or (None, reason). Lots are whole."""
    price = entry.get("price")
    if not isinstance(price, dict):
        return None, f"{entry.get('name')} has no price"
    if type(quantity) is not int or quantity < 1:
        return None, "quantity must be a positive whole number"
    per_lot = price.get("units_per_lot") if type(price.get("units_per_lot")) is int and price["units_per_lot"] > 0 else 1
    if quantity % per_lot:
        return None, f"{entry.get('name')} is sold in lots of {per_lot}"
    unit = COPPER.get(price.get("unit"))
    amount = price.get("amount")
    if unit is None or type(amount) is not int or amount < 0:
        return None, f"{entry.get('name')} has no usable price"
    return unit * amount * (quantity // per_lot), ""


def stated_cost(price: Any) -> Tuple[Optional[int], str]:
    """A DM-stated total price: a {gold, silver, copper} object of whole numbers,
    or 0 for a gift. Returns (copper, "") or (None, reason); (None, "") when no
    price was stated."""
    if price is None:
        return None, ""
    if price == 0:
        return 0, ""
    if not isinstance(price, dict):
        return None, "price must be an object of whole numbers per coin type, or 0 for a gift"
    total = 0
    for coin, amount in price.items():
        if coin not in COPPER:
            return None, f"unknown coin type {coin!r} in price; use gold, silver, copper"
        if type(amount) is bool or type(amount) is not int or amount < 0:
            return None, f"price {coin} {amount!r} is not a non-negative whole number"
        total += COPPER[coin] * amount
    return total, ""


def balance(sheet: Dict[str, Any]) -> Dict[str, int]:
    coins = sheet.get("currency") if isinstance(sheet.get("currency"), dict) else {}
    return {c: (coins.get(c) if type(coins.get(c)) is int and coins.get(c) >= 0 else 0) for c in COIN_ORDER}


def pay(purse: Dict[str, int], cost: int) -> Optional[Dict[str, int]]:
    """Net signed delta per coin that pays ``cost`` copper from ``purse``, or None.

    Exact coins first, largest denomination down (a 1 GP price takes one gold
    coin, not ten silver); when the small coins cannot settle the remainder,
    one more coin of the next larger kind is broken and the change comes back
    in silver and copper. Value is conserved: sum(delta * value) == -cost.
    The kit reference (acquire_gate.pay) pays smallest coins first; this host
    rule differs only in which coins leave the purse, never in the value.
    """
    g, s, c = (purse.get(k, 0) for k in ("gold", "silver", "copper"))
    if cost < 0 or cost > 100 * g + 10 * s + c:
        return None
    rest = cost
    pg = min(g, rest // 100)
    rest -= 100 * pg
    ps = min(s, rest // 10)
    rest -= 10 * ps
    pc = min(c, rest)
    rest -= pc
    if rest:
        # The small coins ran out: break one larger coin and take change.
        if ps < s:
            ps += 1
            rest -= 10
        elif pg < g:
            pg += 1
            rest -= 100
        else:
            return None
    cs, cc = divmod(-rest, 10) if rest < 0 else (0, 0)
    delta = {"gold": -pg, "silver": cs - ps, "copper": cc - pc}
    return {k: v for k, v in delta.items() if v}


def coin_lines(cid: str, delta: Dict[str, int]) -> List[str]:
    lines = [f"spend {_q(cid)} resource {_q(k)} by {-v};" for k, v in delta.items() if v < 0]
    lines += [f"heal {_q(cid)} resource {_q(k)} by {v};" for k, v in delta.items() if v > 0]
    return lines


def item_line(cid: str, iid: str, entry: Dict[str, Any], quantity: int) -> str:
    return (f"create item {_q(iid)} from {_q(entry['id'])} {{ owner {_q(cid)}; custody character {_q(cid)}; "
            f"quantity {quantity}; }};")


def ammunition_lines(cid: str, iid: str, name: str, quantity: int, existing: bool) -> str:
    """Catalog ammunition joins the sheet's ammunition stock (AM), not the equipment list."""
    if existing:
        return f"add {_q(iid)} to {_q(cid)} by {quantity};"
    return f"create item {_q(iid)} named {_q(name)} {{ owner {_q(cid)}; custody character {_q(cid)}; quantity {quantity}; }};"


def next_item_id(sheet: Dict[str, Any], entry: Dict[str, Any]) -> str:
    """item:buy:<slug>:<n>, the first n not on the sheet."""
    taken = {e.get("nql_id") for e in sheet.get("equipment") or [] if isinstance(e, dict)}
    taken |= {str(e.get("nqlId")) for e in sheet.get("acquisitions") or [] if isinstance(e, dict)}
    slug = entry["id"].split("/", 1)[1] if "/" in entry["id"] else genesis.slug(entry.get("name", ""))
    n = 1
    while f"item:buy:{slug}:{n}" in taken:
        n += 1
    return f"item:buy:{slug}:{n}"


def row_from_views(item: Dict[str, Any], definition: Optional[Dict[str, Any]], entry: Dict[str, Any]) -> Dict[str, Any]:
    """NEQ's equipment row for a bought item: the engine's item view, its type
    view (or the pack entry, which the gate proved identical), and the typed
    armor fields from the entry. Never authored by a model."""
    definition = definition if isinstance(definition, dict) else entry
    row: Dict[str, Any] = {
        "item_name": item.get("name") or entry.get("name", ""),
        "nql_id": item["id"],
        "catalog_id": item.get("from") or entry["id"],
        "item_type": definition.get("kind") or entry.get("kind"),
        "description": item.get("description") or entry.get("description", ""),
        "quantity": item.get("quantity") if type(item.get("quantity")) is int else 1,
        "equipped": False,
        "magical": bool(definition.get("magical", entry.get("magical", False))),
        "consumable": bool(definition.get("consumable", entry.get("consumable", False))),
    }
    subtype = definition.get("subtype") or entry.get("subtype")
    if subtype:
        row["item_subtype"] = subtype
    if entry.get("kind") == "armor" and isinstance(entry.get("neq_armor"), dict):
        row.update(copy.deepcopy(entry["neq_armor"]))
    return row


def describe_coins(delta: Dict[str, int]) -> str:
    paid = ", ".join(f"{-v} {k}" for k, v in delta.items() if v < 0)
    change = ", ".join(f"{v} {k}" for k, v in delta.items() if v > 0)
    text = f"paid {paid}" if paid else "paid nothing"
    if change:
        text += f" and received {change} in change"
    return text


def purse_text(purse: Dict[str, int]) -> str:
    return " ".join(f"{purse.get(k, 0)} {k}" for k in COIN_ORDER)
