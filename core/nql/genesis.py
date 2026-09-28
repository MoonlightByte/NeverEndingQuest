# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Build an NQL world from character sheets and storage containers (genesis).

Only typed fields are read: ``abilities.dexterity``, ``proficiencies.armor``,
``classFeatures[].name`` (exact feature names), and the equipment entries'
``item_name``, ``nql_id``, ``item_type``, ``armor_category``, ``ac_base``,
``ac_bonus``, ``dex_limit``, ``quantity`` and ``equipped``. Descriptions and any
other prose are never inspected. Anything the engine cannot represent is
reported in ``Genesis.gaps`` rather than silently approximated.

Every item and character carries a stable identity. ``assign_ids`` writes a
``nql_id`` onto each equipment entry that lacks one (schema field, owner
decision D8); ``build_world`` uses that id, or mints a temporary one for an
entry that still lacks it, and returns the id of every entry so callers can map
engine facts back to sheet entries. Display names are not identities.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

EQUIPMENT_VERSION = "nql-equipment-v1"
DEFENSE_STYLE_FEATURE = "Fighting Style: Defense"
DEFENSE_STYLE_CONDITION = "feature:defense-style"

_ARMOR_TRAINING = {
    "light": "training:light",
    "medium": "training:medium",
    "heavy": "training:heavy",
    "shield": "training:shield",
    "shields": "training:shield",
}


@dataclass
class Genesis:
    source: str
    location: str
    character_ids: Dict[str, str] = field(default_factory=dict)          # sheet name -> char id
    item_ids: Dict[str, Dict[int, str]] = field(default_factory=dict)      # char id -> equipment index -> item id
    container_ids: Dict[str, str] = field(default_factory=dict)           # storage id -> container item id
    content_ids: Dict[str, Dict[int, str]] = field(default_factory=dict)   # storage id -> contents index -> item id
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    """NQL strings use JSON escapes."""
    return json.dumps(str(value), ensure_ascii=True)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "x"


def _int(value: Any) -> Optional[int]:
    return value if type(value) is int else None


def character_id(sheet: Dict[str, Any]) -> str:
    return "char:" + slug(sheet.get("name", ""))


def location_id(location: str) -> str:
    return "loc:" + slug(location)


def container_id(storage_id: str) -> str:
    return "container:" + slug(storage_id)


def _mint(entry: Dict[str, Any], scope: str, index: int) -> str:
    return f"item:{slug(entry.get('item_name', ''))}:{scope}:{index}"


def _entry_id(entry: Dict[str, Any], scope: str, index: int) -> str:
    existing = entry.get("nql_id")
    if isinstance(existing, str) and existing.startswith("item:"):
        return existing
    return _mint(entry, scope, index)


def assign_ids(sheet: Dict[str, Any]) -> bool:
    """Write a nql_id onto every equipment entry that lacks one. Returns True if any was added."""
    changed = False
    seen = set()
    scope = slug(sheet.get("name", ""))
    for index, entry in enumerate(sheet.get("equipment") or []):
        if not isinstance(entry, dict) or not entry.get("item_name"):
            continue
        current = entry.get("nql_id")
        if not (isinstance(current, str) and current.startswith("item:")) or current in seen:
            candidate = _mint(entry, scope, index)
            while candidate in seen:
                index += 1000
                candidate = _mint(entry, scope, index)
            entry["nql_id"] = candidate
            changed = True
        seen.add(entry["nql_id"])
    return changed


def _training(sheet: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for label in (sheet.get("proficiencies") or {}).get("armor") or []:
        cond = _ARMOR_TRAINING.get(str(label).strip().lower())
        if cond and cond not in out:
            out.append(cond)
    return out


def _has_defense_style(sheet: Dict[str, Any]) -> bool:
    return any(f.get("name") == DEFENSE_STYLE_FEATURE for f in sheet.get("classFeatures") or [] if isinstance(f, dict))


def _armor_definition(def_id: str, entry: Dict[str, Any], gaps: List[str]) -> Optional[str]:
    """One immutable definition per armor entry, from its typed fields only."""
    category = entry.get("armor_category")
    base = _int(entry.get("ac_base"))
    bonus = _int(entry.get("ac_bonus")) or 0
    name = entry.get("item_name", "")
    if category == "shield":
        amount = (base if base is not None else 2) + bonus
        return (
            f' definition {_q(def_id)} named {_q(name)} {{\n'
            f'  description "Shield.";\n  default "held";\n'
            f'  mode "held" {{ occupy "hand" by 1; occupy "shield" by 1; '
            f'modifier "defense" stat "defense" add {amount} requires "training:shield"; }}\n }}\n'
        )
    if base is None:
        gaps.append(f"armor without ac_base: {name!r}; treated as a worn item with no defense")
        return None
    constant = base + bonus
    style = f'   modifier "style" stat "defense" add 1 requires {_q(DEFENSE_STYLE_CONDITION)};\n'
    if category == "light":
        term = '   term stat "dexterity" offset -10 divide 2;\n'
    elif category == "medium":
        limit = _int(entry.get("dex_limit"))
        term = f'   term stat "dexterity" offset -10 divide 2 ceiling {limit if limit is not None else 2};\n'
    elif category == "heavy":
        term = ""
    else:
        gaps.append(f"armor with unknown armor_category {category!r}: {name!r}; treated as light")
        term = '   term stat "dexterity" offset -10 divide 2;\n'
    return (
        f' definition {_q(def_id)} named {_q(name)} {{\n'
        f'  description "Body armor.";\n  default "worn";\n'
        f'  mode "worn" {{\n   occupy "body" by 1;\n'
        f'   base stat "defense" {{\n    constant {constant};\n{term}   }}\n{style}  }}\n }}\n'
    )


def _item_line(iid: str, entry: Dict[str, Any], owner: str, custody: str, worn: bool,
               definitions: List[str], gaps: List[str], cid: str) -> Tuple[str, Optional[str]]:
    """One item declaration. Returns (line, mode-if-held)."""
    quantity = _int(entry.get("quantity"))
    item_type = entry.get("item_type")
    definition = None
    mode = None
    if item_type == "armor":
        def_id = "gear:" + iid.split(":", 1)[1]
        text = _armor_definition(def_id, entry, gaps)
        if text is not None:
            definitions.append(text)
            definition, mode = def_id, ("held" if entry.get("armor_category") == "shield" else "worn")
        else:
            definition, mode = "gear:worn", "worn"
    elif item_type == "weapon":
        definition, mode = "gear:held", "held"
    elif worn:
        definition, mode = "gear:worn", "worn"
    if worn and quantity not in (None, 1):
        gaps.append(f"{cid}: {entry.get('item_name')!r} is equipped with quantity {quantity}; the engine wears exactly one, item left unworn")
        worn = False
    fields = [f"owner {_q(owner)};", custody]
    if worn:
        fields.append(f"wearer {_q(cid)};")
    if definition:
        fields.append(f"definition {_q(definition)};")
    if worn and mode:
        fields.append(f"mode {_q(mode)};")
    if quantity is not None and quantity != 1:
        fields.append(f"quantity {quantity};")
    return f"item {_q(iid)} named {_q(entry['item_name'])} {{ {' '.join(fields)} }}", (mode if worn else None)


def build_world(sheets: List[Dict[str, Any]], location: str, location_name: str = "",
                containers: Optional[List[Dict[str, Any]]] = None, contents_owner: Optional[str] = None,
                definition_entries: Optional[List[Tuple[str, Dict[str, Any]]]] = None) -> Genesis:
    """Return the NQL world source for these sheets and storage containers at one location.

    ``containers`` are player_storage.json container records at this location. Their
    contents are declared in the container's custody and owned by ``contents_owner``
    (a character id; legacy storage records no owner and the acting character is the
    only party that can retrieve, so the caller passes that character).
    """
    gaps: List[str] = []
    loc = location_id(location)
    lines: List[str] = [
        "// Generated by core/nql/genesis.py from character sheets. Typed fields only.",
        "rules { transfer unequips; wear any; }",
        f"location {_q(loc)} named {_q(location_name or location)};",
    ]
    character_ids: Dict[str, str] = {}
    item_ids: Dict[str, Dict[int, str]] = {}
    container_ids: Dict[str, str] = {}
    content_ids: Dict[str, Dict[int, str]] = {}
    conditions: List[str] = []
    # Declared for every world: armor definitions reference it with `requires`,
    # which is legal only for a declared type. A character gets the instance
    # only when the sheet lists the exact feature name.
    condition_types: List[str] = [DEFENSE_STYLE_CONDITION]
    definitions: List[str] = [
        ' definition "gear:held" named "Held item" { description "Occupies one hand."; default "held"; mode "held" { occupy "hand" by 1; } }\n',
        ' definition "gear:worn" named "Worn item" { description "Worn, occupies no slot."; default "worn"; mode "worn" { } }\n',
    ]
    items: List[str] = []
    all_ids: set = set()

    for sheet in sheets:
        cid = character_id(sheet)
        if cid in character_ids.values():
            gaps.append(f"duplicate character id {cid}; second sheet skipped")
            continue
        character_ids[sheet.get("name", "")] = cid
        dex = _int((sheet.get("abilities") or {}).get("dexterity"))
        if dex is None:
            gaps.append(f"{cid}: abilities.dexterity is not an integer; defense recipe uses 10")
            dex = 10
        lines.append(
            f"character {_q(cid)} named {_q(sheet.get('name', ''))} at {_q(loc)} {{\n"
            f' stat "dexterity" = {dex};\n stat "defense" = 10;\n}}'
        )
        for cond in _training(sheet):
            if cond not in condition_types:
                condition_types.append(cond)
            conditions.append(f"condition {_q(cond + ':' + cid.split(':', 1)[1])} of {_q(cond)} to {_q(cid)};")
        if _has_defense_style(sheet):
            conditions.append(
                f"condition {_q(DEFENSE_STYLE_CONDITION + ':' + cid.split(':', 1)[1])} of {_q(DEFENSE_STYLE_CONDITION)} to {_q(cid)};"
            )
        ids: Dict[int, str] = {}
        hands = 0
        scope = cid.split(":", 1)[1]
        for index, entry in enumerate(sheet.get("equipment") or []):
            if not isinstance(entry, dict) or not entry.get("item_name"):
                gaps.append(f"{cid}: equipment[{index}] has no item_name; skipped")
                continue
            iid = _entry_id(entry, scope, index)
            if iid in all_ids:
                gaps.append(f"{cid}: duplicate item id {iid} at equipment[{index}]; skipped")
                continue
            all_ids.add(iid)
            ids[index] = iid
            line, held = _item_line(iid, entry, cid, f"custody character {_q(cid)};",
                                    entry.get("equipped") is True, definitions, gaps, cid)
            items.append(line)
            if held == "held":
                hands += 1
        if hands > 2:
            gaps.append(f"{cid}: {hands} held items equipped; the engine allows two hands, genesis will be refused")
        item_ids[cid] = ids

    owner = contents_owner or next(iter(character_ids.values()), None)
    for container in containers or []:
        sid = str(container.get("id", ""))
        if not sid:
            gaps.append("storage container without id skipped")
            continue
        conid = container_id(sid)
        container_ids[sid] = conid
        items.append(f"item {_q(conid)} named {_q(container.get('deviceName') or sid)} {{ container true; custody location {_q(loc)}; }}")
        ids = {}
        for index, entry in enumerate(container.get("contents") or []):
            if not isinstance(entry, dict) or not entry.get("item_name"):
                gaps.append(f"{sid}: contents[{index}] has no item_name; skipped")
                continue
            iid = _entry_id(entry, slug(sid), index)
            if iid in all_ids:
                gaps.append(f"{sid}: duplicate item id {iid} at contents[{index}]; skipped")
                continue
            if owner is None:
                gaps.append(f"{sid}: contents need an owner character; none in world")
                break
            all_ids.add(iid)
            ids[index] = iid
            line, _ = _item_line(iid, entry, owner, f"custody item {_q(conid)};", False, definitions, gaps, owner)
            items.append(line)
        content_ids[sid] = ids

    # Definitions for items that do not exist yet (a later create item in the
    # same world needs its equipment definition declared at genesis).
    for iid, entry in definition_entries or []:
        if isinstance(entry, dict) and entry.get("item_type") == "armor":
            text = _armor_definition("gear:" + iid.split(":", 1)[1], entry, gaps)
            if text is not None:
                definitions.append(text)

    for cond in condition_types:
        lines.append(f"condition type {_q(cond)} {{ instances unique; }}")
    lines.extend(conditions)
    lines.append(f"equipment {_q(EQUIPMENT_VERSION)} {{")
    lines.append(' slot "hand" capacity 2;\n slot "body" capacity 1;\n slot "shield" capacity 1;')
    lines.append(' derive stat "defense" { term stat "dexterity" offset -10 divide 2; }')
    lines.extend(d.rstrip("\n") for d in definitions)
    lines.append("}")
    lines.extend(items)
    return Genesis(source="\n".join(lines) + "\n", location=loc, character_ids=character_ids, item_ids=item_ids,
                   container_ids=container_ids, content_ids=content_ids, gaps=gaps)


def expected_armor_class(sheet: Dict[str, Any]) -> Tuple[Optional[int], List[str]]:
    """The armor class the SRD rule gives for this sheet's typed fields.

    Used only as a test oracle next to the engine's explanation; it is not a
    gameplay writer and must never replace the engine's value.
    """
    dex = _int((sheet.get("abilities") or {}).get("dexterity"))
    if dex is None:
        return None, ["no dexterity"]
    mod = (dex - 10) // 2
    parts = [f"dex {mod}"]
    body = None
    shield = 0
    for entry in sheet.get("equipment") or []:
        if not isinstance(entry, dict) or entry.get("equipped") is not True or entry.get("item_type") != "armor":
            continue
        cat = entry.get("armor_category")
        base = _int(entry.get("ac_base"))
        bonus = _int(entry.get("ac_bonus")) or 0
        if cat == "shield":
            shield += (base if base is not None else 2) + bonus
        elif base is not None:
            if body is not None:
                return None, ["two body armors equipped"]
            limit = _int(entry.get("dex_limit"))
            if cat == "medium":
                body = base + bonus + min(mod, limit if limit is not None else 2)
            elif cat == "heavy":
                body = base + bonus
            else:
                body = base + bonus + mod
            parts.append(f"{entry.get('item_name')} {base}+{bonus}")
    total = (body if body is not None else 10 + mod) + shield
    if shield:
        parts.append(f"shield {shield}")
    if _has_defense_style(sheet) and body is not None:
        total += 1
        parts.append("style 1")
    return total, parts
