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
from typing import Any, Dict, List, Optional, Tuple

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "srd")
JSON_PATH = os.path.join(_DIR, "item_catalog.json")
NQL_PATH = os.path.join(_DIR, "item_catalog.nql")

_CACHE: Dict[str, Tuple[Any, Any]] = {}


def _stamp(path: str):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _load(path: str, reader):
    stamp = _stamp(path)
    cached = _CACHE.get(path)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    value = None
    if stamp is not None:
        try:
            with open(path, "rb") as handle:
                value = reader(handle.read())
        except (OSError, ValueError):
            value = None
    _CACHE[path] = (stamp, value)
    return value


def pack_source() -> str:
    """The ``item type`` declarations, or an empty string when the pack is missing."""
    text = _load(NQL_PATH, lambda raw: raw.decode("utf-8"))
    return text or ""


def entries() -> Dict[str, Dict[str, Any]]:
    """Catalog entries by id (``itemdef:srd/<slug>``); empty when the pack is missing."""
    def read(raw):
        doc = json.loads(raw.decode("utf-8"))
        return {e["id"]: e for e in doc.get("entries") or [] if isinstance(e, dict) and isinstance(e.get("id"), str)}
    return _load(JSON_PATH, read) or {}


def entry(catalog_id: Any) -> Optional[Dict[str, Any]]:
    """The entry a sheet row's ``catalog_id`` names, or None (unknown or not a string)."""
    if not isinstance(catalog_id, str):
        return None
    return entries().get(catalog_id)


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
