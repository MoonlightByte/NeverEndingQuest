# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The SRD item pack the engine world carries (NQL #56; schema srd-item-catalog/<n>, /4 since NUM-H3a).

``data/srd/item_catalog.nql`` holds the ``item type`` declarations the engine
reads; ``data/srd/item_catalog.json`` holds the same entries for the host
(name, kind, price, equipment reference, typed armor and weapon fields).
``data/srd/attack_features.nql`` holds the Condition types the weapon
definitions name (Unarmed Strike, the Martial Arts dice). The files are read
once and re-read only when one changes on disk. A sheet row that carries
``catalog_id`` names one of these types; genesis then declares the row
``from`` the type, which supplies its name, description and equipment.

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
FEATURES_PATH = os.path.join(_DIR, "attack_features.nql")
CHOICES_PATH = os.path.join(_DIR, "choices.json")

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


def _parse(raw_json: Optional[bytes], raw_nql: Optional[bytes],
           raw_features: Optional[bytes] = None) -> Tuple[Optional[Tuple[str, Dict[str, Dict[str, Any]], str]], str]:
    """(source, entries, features) when the files load and describe the same pack, else (None, reason).

    attack_features.nql is required once the pack has weapons with their own
    definitions (srd-item-catalog/4): those definitions name its Condition types."""
    if raw_json is None or raw_nql is None:
        return None, "item_catalog.json" if raw_json is None else "item_catalog.nql"
    try:
        doc = json.loads(raw_json.decode("utf-8"))
        source = raw_nql.decode("utf-8")
        features = raw_features.decode("utf-8") if raw_features is not None else ""
    except (ValueError, UnicodeDecodeError) as error:
        return None, f"unreadable: {error}"
    if not isinstance(doc, dict) or not str(doc.get("schema", "")).startswith("srd-item-catalog/"):
        return None, "item_catalog.json has no srd-item-catalog schema"
    rows = {e["id"]: e for e in doc.get("entries") or [] if isinstance(e, dict) and isinstance(e.get("id"), str)}
    declared = set(_TYPE_LINE.findall(source))
    if not rows or declared != set(rows):
        return None, (f"item_catalog.nql declares {len(declared)} types, item_catalog.json {len(rows)} entries; "
                      f"{len(declared ^ set(rows))} differ")
    if any(_weapon_definition_ref(e) for e in rows.values()) and not features.strip():
        return None, "attack_features.nql (the pack's weapons name its Condition types)"
    return (source, rows, features), ""


def _pack() -> Optional[Tuple[str, Dict[str, Dict[str, Any]], str]]:
    """The pack, read once from its files and re-read when one changes.
    None when a file is missing, unreadable or the files disagree: the
    world then carries no pack and catalog rows fall back to their own fields
    (every call still runs). Logged once per change."""
    stamps = (_stamp(JSON_PATH), _stamp(NQL_PATH), _stamp(FEATURES_PATH))
    if _CACHE["stamps"] == stamps:
        return _CACHE["pack"]
    pack, reason = _parse(_read(JSON_PATH), _read(NQL_PATH), _read(FEATURES_PATH))
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


def features_source() -> str:
    """The attack_features.nql Condition types, or an empty string when there is no pack."""
    pack = _pack()
    return pack[2] if pack else ""


def entries() -> Dict[str, Dict[str, Any]]:
    """Catalog entries by id (``itemdef:srd/<slug>``); empty when there is no pack."""
    pack = _pack()
    return pack[1] if pack else {}


def entry(catalog_id: Any) -> Optional[Dict[str, Any]]:
    """The entry a sheet row's ``catalog_id`` names, or None (unknown or not a string).

    An id with ``MODULE_ID_PREFIX`` is a module item (P3a); only such an id
    reads the module pack, so an SRD lookup never loads or waits on it."""
    if not isinstance(catalog_id, str):
        return None
    if catalog_id.startswith(MODULE_ID_PREFIX):
        return _module_pack()["entries"].get(catalog_id)
    return entries().get(catalog_id)


# P3a: items a module authors in modules/<module>/module_items.json, typed by an
# authored itemKey under the module's namespace. Only the loader builds their
# ids, as MODULE_ID_PREFIX + "<namespace>/<itemKey>".
MODULE_ID_PREFIX = "itemdef:module/"
_MODULES_DIR = "modules"
_MODULE_ITEMS_FILE = "module_items.json"
_KEY = re.compile(r"^[a-z0-9_]+$")
_MODULE_KINDS = ("equipment", "consumable", "miscellaneous")
_RESERVED_NAMESPACES = ("srd", "row")
# Per module folder: (stamp, result) from the last read of its module_items.json;
# result is ("ok", namespace, entries) or ("refused", reason).
_MODULE_FILES: Dict[str, Tuple[Any, Tuple]] = {}
# Every loot warning is written once per key: a file's stamp, a location and reason.
_LOOT_WARNED: set = set()
_LISTING_OUTAGE = ("modules listing incomplete",)


def _loot_warn(key: Any, message: str) -> None:
    if key in _LOOT_WARNED:
        return
    _LOOT_WARNED.add(key)
    try:
        from utils.enhanced_logger import warning
        warning(f"MODULE ITEMS: {message}", category="storage_operations")
    except Exception:  # noqa: BLE001 - logging never blocks a world build
        pass


def _stops() -> Tuple[type, ...]:
    """The three stops a wait raises; they always propagate (#654)."""
    from core.combat.invocation import InvocationSupersededError
    from utils.capture.live_provider_call import LiveProviderSuperseded
    from utils.transient_filesystem import ReadOnlySaveStop
    return (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop)


def _default_wait() -> None:
    from utils.capture.live_provider_call import _interruptible_wait, get_live_provider_scope
    _interruptible_wait(0.25, get_live_provider_scope(), "Reading the module's items...")


def _module_entries(doc: Any, path: str, stamp: Any) -> Tuple:
    """("ok", namespace, entries) for a file that passes the top-level schema,
    with each bad entry refused alone; else ("refused", reason)."""
    # Genesis imports this module at module level, so its bounds are read here.
    from core.nql.acquisition import next_item_id
    from core.nql.genesis import ITEM_ID_MAX, TYPE_DESCRIPTION_MAX

    if (not isinstance(doc, dict) or doc.get("format") != "neq-module-items" or doc.get("version") != 1
            or not isinstance(doc.get("items"), list)):
        return ("refused", "it is not a neq-module-items version 1 file with an items list")
    namespace = doc.get("namespace")
    if not isinstance(namespace, str) or not _KEY.fullmatch(namespace) or namespace in _RESERVED_NAMESPACES:
        return ("refused", f"namespace {namespace!r} is not a lower-case word other than srd and row")
    keys = [i.get("itemKey") for i in doc["items"] if isinstance(i, dict)]
    found = []
    for item in doc["items"]:
        key = item.get("itemKey") if isinstance(item, dict) else None
        why = None
        if not isinstance(item, dict) or not isinstance(key, str) or not _KEY.fullmatch(key):
            why = f"itemKey {key!r} is not a lower-case word"
        elif keys.count(key) > 1:
            why = f"itemKey {key!r} repeats in the file"
        elif not isinstance(item.get("name"), str) or not item["name"].strip():
            why = "it has no name"
        elif not isinstance(item.get("description", ""), str):
            why = "its description is not text"
        elif item.get("kind") not in _MODULE_KINDS:
            why = f"kind {item.get('kind')!r} is not one of {', '.join(_MODULE_KINDS)}"
        elif type(item.get("magical")) is not bool or type(item.get("consumable")) is not bool:
            why = "magical and consumable must be true or false"
        elif "equipment" not in item or item["equipment"] not in ("gear:worn", None):
            why = "equipment must be gear:worn or null"
        cid = f"{MODULE_ID_PREFIX}{namespace}/{key}"
        if why is None:
            minted = next_item_id({}, {"id": cid})
            # The counter's widest value: ten digits, more rows than a sheet holds.
            if len((minted[:-1] + "9" * 10).encode("utf-8")) > ITEM_ID_MAX:
                why = f"the item id a grant mints would be over {ITEM_ID_MAX} bytes"
            elif len(str(item.get("description") or "").encode("utf-8")) > TYPE_DESCRIPTION_MAX:
                why = f"its description is over {TYPE_DESCRIPTION_MAX} bytes"
        if why is not None:
            _loot_warn((path, stamp, "entry", repr(key)), f"{path}: entry {key!r} refused: {why}")
            continue
        found.append({"id": cid, "itemKey": key, "namespace": namespace, "name": item["name"],
                      "description": str(item.get("description") or ""), "kind": item["kind"],
                      "magical": item["magical"], "consumable": item["consumable"],
                      "equipment": item.get("equipment")})
    return ("ok", namespace, found)


def _read_module_file(path: str, stamp: Any, wait) -> Optional[Tuple]:
    """The file's result, or None when it is absent. A busy read waits (B1)."""
    from utils.transient_filesystem import (
        ReadOnlySaveStop, is_transient_filesystem_error, read_bytes_preserving_errors,
        retry_transient_filesystem,
    )

    while True:
        try:
            raw = retry_transient_filesystem(lambda: read_bytes_preserving_errors(path))
            break
        except FileNotFoundError:
            return None
        except ReadOnlySaveStop:
            raise
        except OSError as error:
            if not is_transient_filesystem_error(error):
                result = ("refused", f"it could not be read ({error})")
                _loot_warn((path, stamp, "refused"), f"{path} refused: {result[1]}")
                return result
            _loot_warn((path, stamp, "busy"), f"{path} is busy; waiting to read it")
        wait()
    try:
        result = _module_entries(json.loads(raw.decode("utf-8")), path, stamp)
    except UnicodeDecodeError as error:
        result = ("refused", f"it is not UTF-8 ({error})")
    except ValueError as error:
        result = ("refused", f"it is not JSON ({error})")
    if result[0] == "refused":
        _loot_warn((path, stamp, "refused"), f"{path} refused: {result[1]}")
    return result


def _module_pack(wait=None) -> Dict[str, Any]:
    """{"entries": {id: entry}, "by_module": {folder: {itemKey: id}}} from every
    modules/*/module_items.json. Each file is re-read only when it is new or its
    stamp changed or cannot be taken; a busy read waits, with ``wait`` (a
    no-argument callable) or the global live-provider wait."""
    from utils.transient_filesystem import scandir_names

    wait = wait if wait is not None else _default_wait
    names, complete = scandir_names(_MODULES_DIR, wait, pattern="*", dironly=True)
    if complete:
        _LOOT_WARNED.discard(_LISTING_OUTAGE)
    else:
        _loot_warn(_LISTING_OUTAGE, f"{_MODULES_DIR}/ could not be listed completely; "
                                    "module items keep their last reads")
    for folder in sorted(names):
        path = os.path.join(_MODULES_DIR, folder, _MODULE_ITEMS_FILE)
        try:
            st = os.stat(path)
            stamp = (st.st_mtime_ns, st.st_size)
        except FileNotFoundError:
            _MODULE_FILES.pop(folder, None)
            continue
        except OSError:
            stamp = None  # unstampable: never equal to a held stamp, so re-read
        held = _MODULE_FILES.get(folder)
        if held is not None and stamp is not None and held[0] == stamp:
            continue
        result = _read_module_file(path, stamp, wait)
        if result is None:
            _MODULE_FILES.pop(folder, None)
        else:
            _MODULE_FILES[folder] = (stamp, result)
    if complete:
        for folder in [f for f in _MODULE_FILES if f not in names]:
            del _MODULE_FILES[folder]
    claims: Dict[str, List[str]] = {}
    for folder, (_, result) in _MODULE_FILES.items():
        if result[0] == "ok":
            claims.setdefault(result[1], []).append(folder)
    pack: Dict[str, Any] = {"entries": {}, "by_module": {}}
    for folder, (stamp, result) in sorted(_MODULE_FILES.items()):
        if result[0] != "ok":
            continue
        if len(claims[result[1]]) > 1:
            _loot_warn((folder, stamp, "collision", tuple(sorted(claims[result[1]]))),
                       f"namespace {result[1]!r} is claimed by {', '.join(sorted(claims[result[1]]))}; "
                       f"every claimant is refused")
            continue
        keys = pack["by_module"].setdefault(folder, {})
        for item in result[2]:
            pack["entries"][item["id"]] = item
            keys[item["itemKey"]] = item["id"]
    return pack


def module_catalog_id(module: Any, item_key: Any) -> Optional[str]:
    """The catalog id of ``item_key`` in ``module``'s module_items.json, or None
    (unknown, refused, or its namespace claimed by two modules). ``module`` is
    the module folder name as party_tracker ``module`` holds it."""
    folder = str(module or "").replace(" ", "_")
    return _module_pack()["by_module"].get(folder, {}).get(item_key)


def resolve_loot(location: Any, module: Any, *, wait=None) -> List[Dict[str, Any]]:
    """[{catalogId, name, authored}] for a location's ``lootItems``, in authored
    order. An unknown itemKey, a quantity that is not a whole number of at
    least 1, or a repeated itemKey (the whole list) is dropped with one
    warning; any other failure gives [] with one warning. Stops propagate."""
    stops = _stops()
    location_id = location.get("locationId") if isinstance(location, dict) else None
    try:
        raw = location.get("lootItems") if isinstance(location, dict) else None
        if not raw:
            return []
        if not isinstance(raw, list):
            _loot_warn((location_id, "not a list"), f"location {location_id}: lootItems is not a list")
            return []
        keys = [i.get("itemKey") if isinstance(i, dict) else None for i in raw]
        named = [k for k in keys if isinstance(k, str)]  # a keyless entry is dropped alone below
        if len(set(named)) != len(named):
            _loot_warn((location_id, "duplicate"), f"location {location_id}: lootItems repeats an itemKey; "
                                                   "the list is not used")
            return []
        folder = str(module or "").replace(" ", "_")
        pack = _module_pack(wait=wait)
        known = pack["by_module"].get(folder, {})
        listing = []
        for item, key in zip(raw, keys):
            quantity = item.get("quantity") if isinstance(item, dict) else None
            if not isinstance(key, str) or key not in known:
                _loot_warn((location_id, "unknown", repr(key)),
                           f"location {location_id}: lootItems itemKey {key!r} is not an item of {folder}")
                continue
            if type(quantity) is not int or quantity < 1:
                _loot_warn((location_id, "quantity", repr(key)),
                           f"location {location_id}: lootItems {key!r} quantity {quantity!r} is not a whole "
                           "number of at least 1")
                continue
            listing.append({"catalogId": known[key], "name": pack["entries"][known[key]]["name"],
                            "authored": quantity})
        return listing
    except stops:
        raise
    except Exception as error:  # noqa: BLE001 - loot never stops a turn
        _loot_warn((location_id, "error"), f"location {location_id}: lootItems could not be resolved ({error})")
        return []


# #552: ammunition row names this game wrote before rows used the SRD catalog
# names (T079 rule 6 and its examples, the T053 example, sheets on disk). A
# compatibility reader for saved rows: exact casefolded value of the stored
# name, never a pattern. It does not grow: new rows are taught catalog names.
_LEGACY_AMMUNITION_NAMES = {
    "arrow": "itemdef:srd/arrows",
    "bolt": "itemdef:srd/bolts",
    "crossbow bolt": "itemdef:srd/bolts",
    "crossbow bolts": "itemdef:srd/bolts",
    "sling bullet": "itemdef:srd/bullets-sling",
    "sling bullets": "itemdef:srd/bullets-sling",
    "needle": "itemdef:srd/needles",
    "blowgun needle": "itemdef:srd/needles",
    "blowgun needles": "itemdef:srd/needles",
}


def ammunition_entry(row: Any) -> Optional[Dict[str, Any]]:
    """The catalog ammunition entry a sheet ammunition row holds, or None.

    The row's catalog_id first; else the ammunition entry whose name
    casefold-equals the row name; else the frozen legacy names above."""
    if not isinstance(row, dict):
        return None
    typed = entry(row.get("catalog_id"))
    if typed is not None:
        return typed if typed.get("kind") == "ammunition" else None
    name = str(row.get("name") or "").strip().casefold()
    if not name:
        return None
    for candidate in entries().values():
        if candidate.get("kind") == "ammunition" and str(candidate.get("name", "")).casefold() == name:
            return candidate
    found = entry(_LEGACY_AMMUNITION_NAMES.get(name))
    return found if found is not None and found.get("kind") == "ammunition" else None


def _armor_field(key: str, value: Any, category: Any = None) -> Any:
    if key == "ac_bonus":
        return value if type(value) is int else 0
    if key == "dex_limit" and category == "heavy" and type(value) is int and value == 0:
        return None  # heavy armor adds no Dexterity: a limit of 0 is no limit (#764)
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
    found = entry(catalog_id)
    if found is None:
        return None, f"names unknown catalog_id {catalog_id!r}"
    if found.get("kind") == "armor":
        armor = found.get("neq_armor") if isinstance(found.get("neq_armor"), dict) else {}
        category = armor.get("armor_category")
        drift = [k for k in _ARMOR_FIELDS
                 if _armor_field(k, row.get(k), category) != _armor_field(k, armor.get(k), category)]
        if drift:
            return None, f"({catalog_id}) differs from its catalog type in {', '.join(drift)}"
    return found, None


def equipment_mode(item: Dict[str, Any]) -> Optional[str]:
    """How a catalog item is equipped: ``held`` (weapons, the shield), ``worn``
    (body armor and other gear), None (ammunition, no equipment reference).
    Read from the entry's typed ``equipment`` reference, ``kind`` and ``neq_armor``."""
    ref = item.get("equipment")
    if not isinstance(ref, str) or not ref:
        return None
    if ref == "gear:held" or item.get("kind") == "weapon":
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


def _weapon_definition_ref(item: Dict[str, Any]) -> bool:
    ref = item.get("equipment")
    return (item.get("kind") == "weapon" and isinstance(ref, str) and ref.startswith("gear:srd/")
            and isinstance(item.get("weapon"), dict))


def weapon_entries() -> List[Dict[str, Any]]:
    """The weapon entries that name their own definition (gear:srd/<slug>, /4), in pack order."""
    return [e for e in entries().values() if _weapon_definition_ref(e)]


def held_hands(item: Dict[str, Any]) -> int:
    """The hands a catalog item occupies in its ``held`` mode: a /4 weapon's
    held attack mode states them (2 for a Greatsword, 1 for a Longsword, whose
    two-handed grip is a separate mode); everything else held takes 1."""
    if _weapon_definition_ref(item):
        for mode in item["weapon"].get("attack_modes") or []:
            if isinstance(mode, dict) and mode.get("mode") == "held" and type(mode.get("hands")) is int:
                return mode["hands"]
    return 1


def monk_weapon_rules() -> List[Dict[str, Any]]:
    """choices.json class_traits.monk.monk_weapons.rules (category, kind,
    optional property_any); empty when the file or the record is absent.
    Read once and re-read when the file changes."""
    stamp = _stamp(CHOICES_PATH)
    if _CACHE.get("choices_stamp") == stamp and "monk_rules" in _CACHE:
        return _CACHE["monk_rules"]
    raw = _read(CHOICES_PATH)
    try:
        doc = json.loads(raw.decode("utf-8")) if raw is not None else {}
    except (ValueError, UnicodeDecodeError):
        doc = {}
    monk = ((doc.get("class_traits") or {}).get("monk") or {}) if isinstance(doc, dict) else {}
    rules = (monk.get("monk_weapons") or {}).get("rules") if isinstance(monk, dict) else None
    _CACHE["choices_stamp"] = stamp
    _CACHE["monk_rules"] = [r for r in rules or [] if isinstance(r, dict)]
    return _CACHE["monk_rules"]
