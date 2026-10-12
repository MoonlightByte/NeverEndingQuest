# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""A new character's catalog rows and engine attack rows (NUM-H3c, startup only).

- ``type_catalog_rows``: an author equipment row of item_type "weapon" or
  "armor" with no ``catalog_id`` whose ``item_name`` casefold-equals one base
  catalog entry's name of that kind gets the entry's id (owner ruling HQ4:
  exact name, no plural, prose or partial match). An armor row is typed only
  when its armor fields equal the type's (a drifted row would be declared from
  its own fields with a gap, costing the startup AC certification). Ammunition
  stays in the typed ``ammunition`` array (HC3).
- ``release_carried``: a typed row the engine would leave unworn is set
  ``equipped`` false, so the sheet says what the engine holds and the
  projection carries no gap for it: a stack (quantity above 1; the engine
  wears exactly one) and a weapon the hand rule declares carried (NUM-H3a).
- ``attack_rows``: the engine's attack grants become ``attacksAndSpellcasting``
  rows, one per weapon (and mode) and attack kind, the best grant winning.
  Condition grants (Unarmed Strike, Martial Arts) come from the ``equipment``
  view; item grants only from the ``attack_options`` view (NUM-P3, engine
  7f6f948), which lists carried weapons and every mode. An older engine
  refuses the field at input; the request is then sent without it, no item
  rows are written and the author's stay.
  A carried option's row says how many hands it needs, and whether it is
  usable now, from the equipment view's typed slot occupancy: slots in use,
  less the item's own worn mode, plus the option's, within capacity. The view
  reports slots and does not enforce them (NUM-P3), so the host marks it.
- ``merge_attack_rows``: engine rows replace the author's melee and ranged
  rows of the same names; every other row stays and is reported.
- ``refresh_rows`` / ``refresh_merge`` (item C): a stored sheet's engine rows
  are rebuilt at a level-up commit and a weapon purchase. Engine rows carry
  the typed mark ``engine: true``; a refresh drops the marked rows, then
  applies the startup name rule (for rows written before the mark), and
  writes the new rows first. It needs the ``attack_options`` view: without
  it (an older engine, unavailable, refused) the rows are left as they are.
"""
import copy
from typing import Any, Dict, List, Optional, Tuple

from core.combat.attacks import FLAT_DAMAGE_DICE
from core.nql import apply, genesis, item_catalog

UNARMED_STRIKE_ROW = "Unarmed Strike"
_ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def _base_entries(kind: str) -> Dict[str, Dict[str, Any]]:
    """Base catalog entries of ``kind`` by casefolded name; a name two entries share is left out."""
    if kind == "weapon":
        pool = [e for e in item_catalog.weapon_entries() if not e.get("weapon_base")]
    else:
        pool = item_catalog.armor_entries()
    out: Dict[str, Dict[str, Any]] = {}
    seen = set()
    for entry in pool:
        key = str(entry.get("name", "")).strip().casefold()
        if not key:
            continue
        if key in seen:
            out.pop(key, None)
            continue
        seen.add(key)
        out[key] = entry
    return out


def type_catalog_rows(character: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Give exact-name weapon and armor rows their ``catalog_id`` in place.
    Returns (rows typed as "name: id", weapon and armor rows left untyped)."""
    notes: List[str] = []
    untyped: List[str] = []
    tables = {"weapon": _base_entries("weapon"), "armor": _base_entries("armor")}
    for row in character.get("equipment") or []:
        if not isinstance(row, dict) or row.get("item_type") not in tables:
            continue
        if isinstance(row.get("catalog_id"), str) and row["catalog_id"]:
            continue
        name = str(row.get("item_name", "")).strip()
        entry = tables[row["item_type"]].get(name.casefold())
        if entry is None:
            untyped.append(name)
            continue
        if row["item_type"] == "armor":
            _, drift = item_catalog.row_entry(dict(row, catalog_id=entry["id"]))
            if drift:
                untyped.append(f"{name} {drift}")
                continue
        row["catalog_id"] = entry["id"]
        notes.append(f"{name}: {entry['id']}")
    return notes, untyped


def release_carried(character: Dict[str, Any], location: str) -> List[str]:
    """Unequip, in place, each typed stack and each row the hand rule declares carried. Returns notes."""
    rows = character.get("equipment") or []
    notes: List[str] = []
    for row in rows:
        if (isinstance(row, dict) and row.get("equipped") is True and item_catalog.row_entry(row)[0] is not None
                and type(row.get("quantity")) is int and row["quantity"] > 1):
            row["equipped"] = False
            notes.append(f"equipment {row.get('item_name')!r}: equipped -> false "
                         f"(a stack of {row['quantity']}; the engine wears exactly one)")
    world = genesis.build_world([copy.deepcopy(character)], location)
    cid = genesis.character_id(character)
    for index, iid in sorted((world.item_ids.get(cid) or {}).items()):
        if iid in world.carried and 0 <= index < len(rows) and rows[index].get("equipped") is True:
            rows[index]["equipped"] = False
            notes.append(f"equipment {rows[index].get('item_name')!r}: equipped -> false "
                         f"(its hands are taken; carried, as the engine holds it)")
    return notes


def _kind(grant: Dict[str, Any]) -> str:
    return "melee" if isinstance(grant.get("melee"), dict) else "ranged"


def _average(grant: Dict[str, Any]) -> float:
    count, sides = int(grant.get("damage_count") or 0), int(grant.get("damage_sides") or 0)
    return count * (sides + 1) / 2.0 + int(grant.get("damage_bonus") or 0)


def _term_label(term: Dict[str, Any]) -> str:
    spec = term.get("term") or {}
    stat = str(spec.get("stat") or "")
    requires = str(spec.get("requires") or "")
    if requires.startswith("prof:") or (stat == "level" and spec.get("offset") == 7 and spec.get("divisor") == 4):
        return "proficiency"
    if stat == genesis.ARCHERY_STAT:
        return "Archery"
    return stat.capitalize() if stat in _ABILITIES else stat


def _slot_text(slots: List[Dict[str, Any]]) -> str:
    return ", ".join("%s %d" % (s.get("slot"), int(s.get("amount") or 0)) for s in slots or [])


def _usable_now(option: Dict[str, Any], own: List[Dict[str, Any]], occupancy: Dict[str, Tuple[int, int]]) -> bool:
    """True when the option's slots fit beside what is worn now, the item's own worn mode set aside."""
    freed = {str(s.get("slot")): int(s.get("amount") or 0) for s in own or []}
    for need in option.get("slots") or []:
        slot = str(need.get("slot"))
        used, capacity = occupancy.get(slot, (0, 0))
        if used - freed.get(slot, 0) + int(need.get("amount") or 0) > capacity:
            return False
    return True


def _describe(grant: Dict[str, Any], use: str = "") -> str:
    parts = []
    recipe = grant.get("hit_recipe") or {}
    if recipe.get("base"):
        parts.append("%+d" % int(recipe["base"]))
    for term in recipe.get("terms") or []:
        exact = str(term.get("exact"))
        if term.get("active") is True and exact.lstrip("-").isdigit() and int(exact) != 0:
            parts.append("%+d %s" % (int(exact), _term_label(term)))
    return "Engine attack (NUM-H3c): to hit %s.%s" % (", ".join(parts) or "+0", use)


def _dice(grant: Dict[str, Any]) -> str:
    count, sides = int(grant.get("damage_count") or 0), int(grant.get("damage_sides") or 0)
    return FLAT_DAMAGE_DICE if (count, sides) == (0, 0) else "%dd%d" % (count, sides)


def _row(grant: Dict[str, Any], use: str = "") -> Dict[str, Any]:
    row = {
        "name": str(grant.get("name") or ""),
        "attackBonus": int(grant.get("to_hit") or 0),
        "damageDice": _dice(grant),
        "damageBonus": int(grant.get("damage_bonus") or 0),
        "damageType": str(grant.get("damage_kind") or ""),
        "type": _kind(grant),
        "description": _describe(grant, use),
        "engine": True,
    }
    if isinstance(grant.get("thrown"), dict):
        # #801: a thrown grant stays a "ranged" row (range, the prone rule) and is
        # marked thrown, so the resolver never spends or requires ammunition for it.
        row["thrown"] = True
    ranged = grant.get("ranged")
    if isinstance(ranged, dict) and isinstance(ranged.get("ammunition_type"), str) and ranged["ammunition_type"]:
        # #822: the engine's typed ammunition definition, so a shot spends the matching stock.
        row["ammunitionType"] = ranged["ammunition_type"]
    return row


def _best(groups: Dict[Tuple[str, ...], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """One grant per group: the best to-hit, then the best average damage, then engine order."""
    out = []
    for key in groups:
        ranked = sorted(enumerate(groups[key]), key=lambda pair: (-int(pair[1].get("to_hit") or 0), -_average(pair[1]), pair[0]))
        out.append(ranked[0][1])
    return out


def attack_rows(character: Dict[str, Any], location: str, *, binary: Optional[str] = None,
                not_usable_now: Optional[List[str]] = None) -> Tuple[Optional[List[Dict[str, Any]]], bool, str]:
    """(rows, item rows included, reason). rows is None when the engine was unavailable or refused.
    Names of carried-mode rows whose slots are taken now are appended to ``not_usable_now``."""
    world = genesis.build_world([copy.deepcopy(character)], location)
    cid = genesis.character_id(character)
    request: Dict[str, Any] = {"world": world.source, "world_name": "genesis.nql", "equipment": [cid]}
    try:
        response = apply.call(dict(request, attack_options=[cid]), binary=binary)
        if not response.get("ok") and response.get("phase") == "input":
            response = apply.call(request, binary=binary)
    except apply.EngineUnavailable as error:
        return None, False, str(error)
    if not response.get("ok"):
        return None, False, "engine refused the world at %s" % response.get("phase")
    rows, with_items = rows_from_response(response, not_usable_now)
    return rows, with_items, ""


def rows_from_response(response: Dict[str, Any],
                       not_usable_now: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], bool]:
    """(rows, item rows included) from an engine response holding the ``equipment`` view and, when the
    engine took it, the ``attack_options`` view."""
    groups: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    occupancy: Dict[str, Tuple[int, int]] = {}
    for view in response.get("equipment") or []:
        for slot in view.get("slots") or []:
            occupancy[str(slot.get("slot"))] = (int(slot.get("used") or 0), int(slot.get("capacity") or 0))
        for grant in view.get("attacks") or []:
            origin = grant.get("origin") or {}
            if isinstance(grant, dict) and origin.get("condition"):
                groups.setdefault(("condition", origin["condition"], _kind(grant)), []).append(grant)
    options = response.get("attack_options")
    with_items = isinstance(options, list)
    uses: Dict[Tuple[str, ...], Tuple[str, bool]] = {}
    ranks: Dict[Tuple[str, ...], int] = {}
    for view in options or []:
        worn = {str(o.get("item")): o.get("slots") for o in view.get("options") or [] if o.get("worn") is True}
        for option in view.get("options") or []:
            item = str(option.get("item"))
            if option.get("worn") is True:
                use, usable = " In hand.", True
            else:
                usable = _usable_now(option, worn.get(item) or [], occupancy)
                use = " Carried mode: needs %s%s." % (_slot_text(option.get("slots")),
                                                    "" if usable else "; not usable now, the slots are taken")
            # #814: one row per weapon type and mode. Two items of one weapon share the option's typed
            # definition; an option without one keeps its own item's rows.
            definition = option.get("definition")
            owner = definition if isinstance(definition, str) and definition else item
            for grant in option.get("grants") or []:
                if isinstance(grant, dict):
                    key = ("item", owner, str(option.get("mode")), _kind(grant))
                    groups.setdefault(key, []).append(grant)
                    # The group's text is its best option's: worn, then carried and usable now, then any.
                    rank = 0 if option.get("worn") is True else 1 if usable else 2
                    if key not in uses or rank < ranks[key]:
                        uses[key], ranks[key] = (use, usable), rank
    rows = []
    for key, grant in zip(groups, _best(groups)):
        use, usable = uses.get(key, ("", True))
        rows.append(_row(grant, use))
        if not usable and not_usable_now is not None:
            not_usable_now.append(rows[-1]["name"])
    return rows, with_items


def owned_weapon_names(character: Dict[str, Any]) -> List[str]:
    """Casefolded names of the character's typed catalog weapons."""
    names = []
    for row in character.get("equipment") or []:
        entry = item_catalog.entry(row.get("catalog_id")) if isinstance(row, dict) else None
        if entry is not None and entry.get("kind") == "weapon":
            names.append(str(entry.get("name", "")).strip().casefold())
    return names


def merge_attack_rows(character: Dict[str, Any], rows: List[Dict[str, Any]],
                      with_items: bool) -> Dict[str, List[str]]:
    """Put the engine rows on the sheet in place; returns what was written, replaced and kept."""
    replace = {r["name"].strip().casefold() for r in rows}
    if any(r["name"].startswith(UNARMED_STRIKE_ROW) for r in rows):
        replace.add(UNARMED_STRIKE_ROW.casefold())
    if with_items:
        replace.update(owned_weapon_names(character))
    kept_rows, replaced, kept = [], [], []
    for row in character.get("attacksAndSpellcasting") or []:
        name = str(row.get("name", "")).strip() if isinstance(row, dict) else ""
        if isinstance(row, dict) and row.get("type") in ("melee", "ranged") and name.casefold() in replace:
            replaced.append(name)
            continue
        kept_rows.append(row)
        if isinstance(row, dict) and row.get("type") in ("melee", "ranged"):
            kept.append(name)
    character["attacksAndSpellcasting"] = list(rows) + kept_rows
    return {"written": [r["name"] for r in rows], "replaced": replaced, "kept_author_rows": kept}


def refresh_merge(character: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Item C: drop the sheet's marked engine rows, then merge the new rows as startup does (C-Q2 A: the
    startup name rule replaces unmarked rows written before the mark)."""
    dropped = [str(r.get("name", "")) for r in character.get("attacksAndSpellcasting") or []
               if isinstance(r, dict) and r.get("engine") is True]
    character["attacksAndSpellcasting"] = [r for r in character.get("attacksAndSpellcasting") or []
                                           if not (isinstance(r, dict) and r.get("engine") is True)]
    report = merge_attack_rows(character, rows, True)
    report["dropped_engine_rows"] = dropped
    return report


def refresh_rows(character: Dict[str, Any], location: str, *, binary: Optional[str] = None) -> Dict[str, Any]:
    """Item C: rebuild the engine rows of a stored sheet in place, from one engine call. Never raises; the
    rows are left unchanged unless the engine returned the ``attack_options`` view."""
    try:
        rows, with_items, reason = attack_rows(character, location, binary=binary)
        if rows is None or not with_items:
            return {"refreshed": False, "reason": reason or "the engine returned no attack_options view"}
        trial = dict(character)  # all or nothing: the sheet's list is replaced only after a whole merge
        report = refresh_merge(trial, rows)
        character["attacksAndSpellcasting"] = trial["attacksAndSpellcasting"]
        return dict(report, refreshed=True)
    except Exception as error:  # fail forward: the caller's commit proceeds with the rows unchanged
        return {"refreshed": False, "reason": "%s: %s" % (type(error).__name__, error)}
