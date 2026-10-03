# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The SRD item pack the engine world carries (NQL #56, srd-item-catalog/2).

``data/srd/item_catalog.nql`` holds the 145 ``item type`` declarations the
engine reads; ``data/srd/item_catalog.json`` holds the same entries for the
host (name, kind, price, equipment reference, typed armor fields). Both files
are read once and re-read only when they change on disk. A sheet row that
carries ``catalog_id`` names one of these types; genesis then declares the
row ``from`` the type, which supplies its name, description and equipment.

Portions derived from SRD 5.2.1, CC BY 4.0; the attribution sentence is
inside both pack files.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "srd")
JSON_PATH = os.path.join(_DIR, "item_catalog.json")
NQL_PATH = os.path.join(_DIR, "item_catalog.nql")

_CACHE: Dict[str, Any] = {"stamps": None, "pack": None}
_ARMOR_FIELDS = ("armor_category", "ac_base", "ac_bonus", "dex_limit")
_TYPE_LINE = re.compile(r'^item type "([^"]+)"', re.M)


def _stamp(path: str):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _read(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _parse(raw_json: Optional[bytes], raw_nql: Optional[bytes]) -> Tuple[Optional[Tuple[str, Dict[str, Dict[str, Any]]]], str]:
    """(source, entries) when both files load and describe the same pack, else (None, reason)."""
    if raw_json is None or raw_nql is None:
        return None, "item_catalog.json" if raw_json is None else "item_catalog.nql"
    try:
        doc = json.loads(raw_json.decode("utf-8"))
        source = raw_nql.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        return None, f"unreadable: {error}"
    if not isinstance(doc, dict) or not str(doc.get("schema", "")).startswith("srd-item-catalog/"):
        return None, "item_catalog.json has no srd-item-catalog schema"
    rows = {e["id"]: e for e in doc.get("entries") or [] if isinstance(e, dict) and isinstance(e.get("id"), str)}
    declared = set(_TYPE_LINE.findall(source))
    if not rows or declared != set(rows):
        return None, (f"item_catalog.nql declares {len(declared)} types, item_catalog.json {len(rows)} entries; "
                      f"{len(declared ^ set(rows))} differ")
    return (source, rows), ""


def _pack() -> Optional[Tuple[str, Dict[str, Dict[str, Any]]]]:
    """The pack, read once from both files and re-read when either changes.
    None when either file is missing, unreadable or the two disagree: the
    world then carries no pack and catalog rows fall back to their own fields
    (every call still runs). Logged once per change."""
    stamps = (_stamp(JSON_PATH), _stamp(NQL_PATH))
    if _CACHE["stamps"] == stamps:
        return _CACHE["pack"]
    pack, reason = _parse(_read(JSON_PATH), _read(NQL_PATH))
    if pack is None:
        try:
            from utils.enhanced_logger import warning
            warning(f"ITEM CATALOG: no SRD item pack ({reason}); worlds carry no catalog and catalog rows "
                    f"use their own fields", category="storage_operations")
        except Exception:  # noqa: BLE001 - logging never blocks a world build
            pass
    _CACHE["stamps"] = stamps
    _CACHE["pack"] = pack
    return pack


def pack_source() -> str:
    """The ``item type`` declarations, or an empty string when there is no pack."""
    pack = _pack()
    return pack[0] if pack else ""


def entries() -> Dict[str, Dict[str, Any]]:
    """Catalog entries by id (``itemdef:srd/<slug>``); empty when there is no pack."""
    pack = _pack()
    return pack[1] if pack else {}


def entry(catalog_id: Any) -> Optional[Dict[str, Any]]:
    """The entry a sheet row's ``catalog_id`` names, or None (unknown or not a string)."""
    if not isinstance(catalog_id, str):
        return None
    return entries().get(catalog_id)


def _armor_field(key: str, value: Any) -> Any:
    if key == "ac_bonus":
        return value if type(value) is int else 0
    return value


def row_entry(row: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """The catalog entry a sheet row is still an instance of, or why not.

    (entry, None) while the row's ``catalog_id`` names a pack entry and, for
    armor, its typed armor fields equal the entry's ``neq_armor``; (None, None)
    for a row without a catalog_id; (None, reason) for an unknown id or a row
    whose armor fields drifted from the type (an enchantment, a T079 edit): that
    row is declared from its own fields so the engine sees what the sheet says.
    """
    catalog_id = row.get("catalog_id")
    if not isinstance(catalog_id, str) or not catalog_id:
        return None, None
    found = entries().get(catalog_id)
    if found is None:
        return None, f"names unknown catalog_id {catalog_id!r}"
    if found.get("kind") == "armor":
        armor = found.get("neq_armor") if isinstance(found.get("neq_armor"), dict) else {}
        drift = [k for k in _ARMOR_FIELDS if _armor_field(k, row.get(k)) != _armor_field(k, armor.get(k))]
        if drift:
            return None, f"({catalog_id}) differs from its catalog type in {', '.join(drift)}"
    return found, None


def equipment_mode(item: Dict[str, Any]) -> Optional[str]:
    """How a catalog item is equipped: ``held`` (weapons, the shield), ``worn``
    (body armor and other gear), None (ammunition, no equipment reference).
    Read from the entry's typed ``equipment`` reference and ``neq_armor``."""
    ref = item.get("equipment")
    if not isinstance(ref, str) or not ref:
        return None
    if ref == "gear:held":
        return "held"
    if item.get("kind") == "armor":
        armor = item.get("neq_armor") if isinstance(item.get("neq_armor"), dict) else {}
        return "held" if armor.get("armor_category") == "shield" else "worn"
    return "worn"


def armor_entries() -> List[Dict[str, Any]]:
    """The armor entries with typed fields, in pack order."""
    return [e for e in entries().values() if e.get("kind") == "armor" and isinstance(e.get("neq_armor"), dict)]


def armor_definition_id(item: Dict[str, Any]) -> str:
    """``gear:srd/<slug>``: the equipment definition the pack's armor type names."""
    return str(item.get("equipment") or "")
