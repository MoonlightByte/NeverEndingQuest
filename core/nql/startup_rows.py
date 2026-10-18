# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""A new character's catalog rows and engine attack rows (NUM-H3c, startup only).

- ``type_catalog_rows``: an author equipment row of item_type "weapon" or
  "armor" with no ``catalog_id`` whose ``item_name`` casefold-equals one base
  catalog entry's name of that kind gets the entry's id (owner ruling HQ4:
  exact name, no plural, prose or partial match). An armor row is typed only
  when its present armor fields equal the type's (a drifted row would be declared
  from its own fields with a gap, costing the startup AC certification); its
  absent armor fields are filled from the type and noted (#573). Ammunition
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
- ``grant_starting_packages``: a new character's starting gold and gear from
  its typed picks (D-KW-16): the class's and background's chosen package
  options, read by typed key from the data, merged by catalog id or data key
  and created by one engine request. The engine's views are written back; the
  host adds two typed gp integers and checks membership. It never waits: an
  engine fault is reported in ``faults`` for the caller (D-PKG-1).
"""
import copy
import json
import os
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from core.combat.attacks import FLAT_DAMAGE_DICE
from core.nql import acquisition, apply, genesis, item_catalog

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


def type_catalog_rows(character: Dict[str, Any],
                      filled: Optional[List[str]] = None) -> Tuple[List[str], List[str]]:
    """Give exact-name weapon and armor rows their ``catalog_id`` in place.
    An armor row's absent armor fields are filled from its type, each noted in
    ``filled`` when given (#573); a present field that differs leaves the row
    untyped. Returns (rows typed as "name: id", weapon and armor rows left untyped)."""
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
            armor = entry.get("neq_armor") if isinstance(entry.get("neq_armor"), dict) else {}
            category = armor.get("armor_category")
            missing = [k for k in item_catalog._ARMOR_FIELDS
                       if row.get(k) is None
                       and item_catalog._armor_field(k, None, category)
                       != item_catalog._armor_field(k, armor.get(k), category)]
            fill = {k: armor[k] for k in missing}
            _, drift = item_catalog.row_entry(dict(row, catalog_id=entry["id"], **fill))
            if drift:
                untyped.append(f"{name} {drift}")
                continue
            if fill:
                row.update(fill)
                if filled is not None:
                    filled.append(f"equipment {name!r}: "
                                  + ", ".join(f"{k} None -> {fill[k]!r}" for k in missing)
                                  + " (its SRD catalog type, exact name)")
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
                not_usable_now: Optional[List[str]] = None,
                faults: Optional[list] = None) -> Tuple[Optional[List[Dict[str, Any]]], bool, str]:
    """(rows, item rows included, reason). rows is None when the engine was unavailable or refused.
    Names of carried-mode rows whose slots are taken now are appended to ``not_usable_now``; the
    caught ``apply.EngineUnavailable``, or ("refused", phase) for a refusal, to ``faults``."""
    world = genesis.build_world([copy.deepcopy(character)], location)
    cid = genesis.character_id(character)
    request: Dict[str, Any] = {"world": world.source, "world_name": "genesis.nql", "equipment": [cid]}
    try:
        response = apply.call(dict(request, attack_options=[cid]), binary=binary)
        if not response.get("ok") and response.get("phase") == "input":
            response = apply.call(request, binary=binary)
    except apply.EngineUnavailable as error:
        if faults is not None:
            faults.append(error)
        return None, False, str(error)
    if not response.get("ok"):
        if faults is not None:
            faults.append(("refused", response.get("phase")))
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


# ---- Starting packages (startup only) ----------------------------------------

ORIGINS_PATH = os.path.join(os.path.dirname(os.path.dirname(item_catalog.CHOICES_PATH)), "srd_character_origins.json")
GRANT_REQUEST = "startup:starting-packages"


class PackageRecords(NamedTuple):
    classes: Dict[str, Dict[str, Any]]  # class key: its Starting Equipment option_items
    backgrounds: Dict[str, Dict[str, Any]]  # background key: its origins record


def package_records() -> Optional[PackageRecords]:
    """The typed starting packages, read from the data at each call, or None when a file cannot be read."""
    try:
        with open(item_catalog.CHOICES_PATH, "r", encoding="utf-8") as handle:
            choices = json.load(handle)
        with open(ORIGINS_PATH, "r", encoding="utf-8") as handle:
            origins = json.load(handle)
        classes = {}
        for key, levels in choices["choice_points"].items():
            # The level-1 entry that carries option_items (its typed shape, not its name).
            options = [p["option_items"] for p in levels.get("1", []) if isinstance(p.get("option_items"), dict)]
            if len(options) == 1:
                classes[key] = options[0]
        backgrounds = {b["key"]: b for b in origins["backgrounds"] if isinstance(b.get("equipment_options"), dict)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return PackageRecords(classes, backgrounds) if classes and backgrounds else None


def _legal(values: Any) -> str:
    return ", ".join(sorted(str(v) for v in values)) or "none"


def _package_items(option: Dict[str, Any], label: str) -> List[Tuple[str, Dict[str, Any]]]:
    return [(label, item) for item in option.get("items") or [] if isinstance(item, dict)]


def _slot_problems(items: List[Tuple[str, Dict[str, Any]]], picks: List[Any]) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """The typed pick for each slot of the chosen packages, and every problem with the picks. The pick kind
    comes from the entry's shape: a slot with choose_one is a catalog pick, one with no catalog id a named pick."""
    slots = {item["slot"]: item for _, item in items if isinstance(item.get("slot"), str)}
    chosen: Dict[str, Dict[str, Any]] = {}
    problems = []
    for pick in picks:
        slot = pick.get("slot")
        item = slots.get(slot)
        if item is None:
            problems.append("slot_picks names slot %r, which the chosen packages do not have; their slots: %s"
                            % (slot, _legal(slots)))
        elif slot in chosen:
            problems.append("slot_picks names slot %r twice; give one pick per slot" % slot)
        elif isinstance(item.get("choose_one"), list):
            if pick.get("catalog_id") not in item["choose_one"]:
                problems.append("slot %r is a catalog pick: give catalog_id, one of %s"
                                % (slot, _legal(item["choose_one"])))
            else:
                chosen[slot] = pick
        elif not isinstance(pick.get("display_name"), str) or "catalog_id" in pick:
            problems.append("slot %r is a named pick: give display_name, the player's own choice of %s, "
                            "not a catalog_id" % (slot, json.dumps(item.get("uncatalogued"))))
        else:
            chosen[slot] = pick
    for slot, item in slots.items():
        if slot not in chosen and not any(p.get("slot") == slot for p in picks):
            kind = ("catalog_id, one of %s" % _legal(item["choose_one"]) if isinstance(item.get("choose_one"), list)
                    else "display_name, the player's own choice of %s" % json.dumps(item.get("uncatalogued")))
            problems.append("slot %r has no pick in slot_picks: give %s" % (slot, kind))
    return chosen, problems


def _merged(items: List[Tuple[str, Dict[str, Any]]], chosen: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The packages' items as one list, merged by catalog id or, for an item the catalog lacks, by its data
    key; quantities are summed. A named pick's display_name is display text only, never compared."""
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for _, item in items:
        if isinstance(item.get("choose_one"), list):
            identity, quantity = ("catalog", chosen[item["slot"]]["catalog_id"]), 1
        elif isinstance(item.get("catalog_id"), str):
            identity, quantity = ("catalog", item["catalog_id"]), int(item.get("quantity") or 1)
        else:
            identity, quantity = ("named", str(item["key"])), 1
        if identity in merged:
            merged[identity]["quantity"] += quantity
            continue
        merged[identity] = {"identity": identity, "quantity": quantity, "data": item,
                            "name": (chosen[item["slot"]]["display_name"] if identity[0] == "named"
                                     and isinstance(item.get("slot"), str) else item.get("uncatalogued"))}
    return list(merged.values())


def _named_row(item: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """A starting item the catalog lacks: the engine's item view, with the data's typed item_type."""
    return {
        "item_name": item.get("name") or "",
        "nql_id": item["id"],
        "item_type": data["item_type"],
        "description": item.get("description") or data.get("description", ""),
        "quantity": item.get("quantity") if type(item.get("quantity")) is int else 1,
        "equipped": False,
        "magical": False,
        "consumable": False,
    }


def _ammunition_stock_row(item: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    """The #822 ammunition row a new stock gets: the catalog's name and typed id, the engine's quantity."""
    return {"name": entry["name"], "quantity": int(item.get("quantity", 0)),
            "description": entry.get("description", ""), "catalog_id": entry["id"]}


def grant_starting_packages(sheet: Dict[str, Any], origin: Dict[str, Any], picks: Dict[str, Any],
                            faults: list) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """A new character's starting gold and gear from one engine request over ``sheet`` (zeroed by the caller).

    Returns (granted sheet, report), or (None, None) with the fault appended to ``faults``: the caught
    ``apply.EngineUnavailable`` (a malformed response is reported as one), ("refused", phase) for an
    ``ok`` false response, or ("data_unavailable", "grant") when the package data cannot be read. Raises
    ValueError naming every legal value from the data when a pick is not one of them.
    """
    records = package_records()
    if records is None:
        faults.append(("data_unavailable", "grant"))
        return None, None
    class_options = records.classes.get(origin.get("class_key"))
    background = records.backgrounds.get(origin.get("background_key"))
    problems = []
    if class_options is None:
        problems.append("origin.class_key %r is not a class key; one of %s" % (origin.get("class_key"), _legal(records.classes)))
    if background is None:
        problems.append("origin.background_key %r is not a background key; one of %s"
                        % (origin.get("background_key"), _legal(records.backgrounds)))
    if problems:
        raise ValueError("; ".join(problems))
    class_option = class_options.get(picks.get("class_package"))
    background_option = background["equipment_options"].get(picks.get("background_package"))
    if class_option is None:
        problems.append("starting_equipment.class_package %r is not a %s option; one of %s"
                        % (picks.get("class_package"), origin["class_key"], _legal(class_options)))
    if background_option is None:
        problems.append("starting_equipment.background_package %r is not a %s option; one of %s"
                        % (picks.get("background_package"), origin["background_key"], _legal(background["equipment_options"])))
    if problems:
        raise ValueError("; ".join(problems))
    items = _package_items(class_option, "class") + _package_items(background_option, "background")
    chosen, problems = _slot_problems(items, [p for p in picks.get("slot_picks") or [] if isinstance(p, dict)])
    if problems:
        raise ValueError("; ".join(problems))
    merged = _merged(items, chosen)
    catalog_ids = [m["identity"][1] for m in merged if m["identity"][0] == "catalog"]
    unknown = [cid for cid in catalog_ids if item_catalog.entry(cid) is None]
    if unknown:
        raise ValueError("the package data names catalog ids the item catalog lacks: %s" % _legal(unknown))
    outside = [i for i in picks.get("equipped") or [] if i not in catalog_ids]
    if outside:
        raise ValueError("starting_equipment.equipped lists %s, not catalog items of the chosen packages; "
                         "equipped ids are among %s" % (_legal(outside), _legal(catalog_ids)))

    cid = genesis.character_id(sheet)
    reserved = set(genesis.held_ids_on_disk())
    lines = acquisition.coin_lines(cid, {"gold": int(class_option["coins"]["gp"]) + int(background_option["coins"]["gp"])})
    for m in merged:
        if m["identity"][0] == "catalog":
            entry = item_catalog.entry(m["identity"][1])
            if entry.get("kind") == "ammunition":
                m["id"] = genesis.ammunition_id(sheet, entry["name"])
                lines.append(acquisition.ammunition_lines(cid, m["id"], entry["name"], m["quantity"], False))
                continue
            m["id"] = acquisition.next_item_id(sheet, entry, reserved=reserved)
            lines.append(acquisition.item_line(cid, m["id"], entry, m["quantity"]))
        else:
            # The id's slug is the data key (F-4), never the display text.
            m["id"] = acquisition.next_item_id(sheet, {"id": m["identity"][1], "name": m["identity"][1]}, reserved=reserved)
            quantity = " quantity %d;" % m["quantity"] if m["quantity"] != 1 else ""
            lines.append("create item %s named %s { owner %s; custody character %s;%s description %s; };"
                         % (genesis._q(m["id"]), genesis._q(m["name"]), genesis._q(cid), genesis._q(cid),
                            quantity, genesis._q(m["data"].get("description", ""))))
        reserved.add(m["id"])
    from core.nql.armor_class import PROJECTION_LOCATION
    world = genesis.build_world([copy.deepcopy(sheet)], PROJECTION_LOCATION)
    document = {"world": world.source, "world_name": "genesis.nql",
                "actions": "\n".join(lines), "actions_name": "starting-packages.nql",
                "actor": {"kind": "character", "id": cid}, "request": GRANT_REQUEST,
                "status": [cid], "items_at": [{"kind": "character", "id": cid}],
                "item_definitions": sorted(set(catalog_ids))}
    try:
        response = apply.call(document)
    except apply.EngineUnavailable as error:
        faults.append(error)
        return None, None
    if not response.get("ok"):
        faults.append(("refused", response.get("phase")))
        return None, None

    # Write the engine's facts back: the purse, then each item, or nothing.
    status = next((s for s in response.get("status") or [] if isinstance(s, dict)
                   and isinstance(s.get("character"), dict) and s["character"].get("id") == cid), None)
    resources = (status or {}).get("resources") or {}
    views = response.get("items_at")
    if status is None or not isinstance(views, list):
        faults.append(apply.EngineUnavailable("engine returned no status or items_at view for the character"))
        return None, None
    if any(c not in resources for c in acquisition.COIN_ORDER):
        faults.append(apply.EngineUnavailable("engine returned no coin balance"))
        return None, None
    found = {i.get("id"): i for v in views if isinstance(v, dict) for i in v.get("items") or [] if isinstance(i, dict)}
    definitions = {d.get("id"): d for d in response.get("item_definitions") or [] if isinstance(d, dict)}
    missing = [m["id"] for m in merged if m["id"] not in found]
    if missing:
        faults.append(apply.EngineUnavailable("engine returned no view of the new items %s" % ", ".join(missing)))
        return None, None
    granted = copy.deepcopy(sheet)
    granted["currency"] = {c: int(resources[c]["current"]) for c in acquisition.COIN_ORDER}
    # The new rows follow the sheet's own (none on the caller's zeroed sheet).
    granted["equipment"] = list(granted.get("equipment") or [])
    granted["ammunition"] = list(granted.get("ammunition") or [])
    made = {"equipment": len(granted["equipment"]), "ammunition": len(granted["ammunition"])}
    stock_ids = []  # the minted engine id of each new ammunition stock, in row order
    for m in merged:
        view = found[m["id"]]
        if m["identity"][0] == "named":
            granted["equipment"].append(_named_row(view, m["data"]))
            continue
        entry = item_catalog.entry(m["identity"][1])
        if entry.get("kind") == "ammunition":
            granted["ammunition"].append(_ammunition_stock_row(view, entry))
            stock_ids.append(m["id"])
            continue
        row = acquisition.row_from_views(view, definitions.get(entry["id"]), entry)
        row["equipped"] = row["catalog_id"] in (picks.get("equipped") or [])
        granted["equipment"].append(row)
    report = {
        "source": "core.nql.startup_rows.grant_starting_packages",
        "class": {"key": origin["class_key"], "package": picks["class_package"], "gp": int(class_option["coins"]["gp"])},
        "background": {"key": origin["background_key"], "name": background["name"],
                       "package": picks["background_package"], "gp": int(background_option["coins"]["gp"])},
        "currency": dict(granted["currency"]),
        "equipment": [{"item_name": r["item_name"], "nql_id": r["nql_id"], "quantity": r["quantity"],
                       "equipped": r["equipped"]} for r in granted["equipment"][made["equipment"]:]],
        "ammunition": [{"name": r["name"], "nql_id": iid, "quantity": r["quantity"]}
                       for r, iid in zip(granted["ammunition"][made["ammunition"]:], stock_ids)],
    }
    return granted, report
