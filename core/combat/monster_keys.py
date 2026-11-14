# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Typed monster keys (#293/typed-monster-key, D-TMK-1).

A monster key names one stat block, modules/<module>/monsters/<key>.json, and
is stored as the encounter creature's ``monsterType``. A new fight takes each
monster's key from typed sources only, never from the name the model writes
(D-KW-12):

1. the engine occupant the DM declared for that slot (``occupantIds``): its
   typed ``type``;
2. else a key the DM named for that slot (``monsterKeys``) that is exactly one
   of the listed keys it was shown;
3. else a new key that no name can select: the stat block is generated from
   the DM's name and flavor, so the DM can always bring a new creature.

The listed keys are the global compendium's keys (data/bestiary) and the
stems of the current module's own monster files (#1997), the module's file
winning a key both have. A minted key is never listed, so the list the DM sees
never grows with opaque keys; a minted creature is reached again through the
occupant created for it. Play writes only minted files and compendium keys, so
the list changes only when a module's own sheets are built.
"""

import json
import os
import re
import uuid

COMPENDIUM = os.path.join("data", "bestiary", "monster_compendium.json")
# #1997: at most this many of a module's own keys that are not compendium keys
# are listed (sorted order); the rest behave as before (occupant or new key).
MODULE_KEY_CAP = 40
_MINTED = re.compile(r"new_[0-9a-f]{32}")
# normalize_character_name's fixed points for ASCII: get_monster_path(stem)
# names this same file only for such a stem (so no _BU, .bak or capitals).
_STEM = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")
# {monsters folder: (stamps, ((stem, name), ...))}. An entry is never changed
# after it is made; a new one replaces it by one assignment, so a reader on any
# thread sees one whole folder state.
_MODULE_KEYS_MEMO = {}
_CAP_LOGGED = set()


def mint_key():
    """A new monster key; never the stem of an existing stat block, and its
    own file name (normalize_character_name leaves it unchanged)."""
    return "new_%s" % uuid.uuid4().hex


def _compendium():
    """{key: name} for the compendium's entries."""
    try:
        with open(COMPENDIUM, encoding="utf-8") as handle:
            monsters = json.load(handle).get("monsters")
    except (OSError, ValueError, AttributeError):
        return {}
    if not isinstance(monsters, dict):
        return {}
    return {
        key: entry["name"]
        for key, entry in monsters.items()
        if isinstance(key, str) and key and isinstance(entry, dict)
        and isinstance(entry.get("name"), str) and entry["name"].strip()
    }


def _folder_stamps(folder):
    """((file name, mtime_ns, size), ...) of the folder's *.json files; () when
    there is no folder, None when a stat fails."""
    stamps = []
    try:
        with os.scandir(folder) as it:
            for entry in sorted(it, key=lambda e: e.name):
                if entry.name.endswith(".json") and entry.is_file():
                    st = entry.stat()
                    stamps.append((entry.name, st.st_mtime_ns, st.st_size))
    except FileNotFoundError:
        return ()
    except OSError:
        return None
    return tuple(stamps)


def _sheet_name(path):
    """The stat block's own name, or None when the file is not a readable
    monster stat block with a non-empty name: it must have hitPoints and
    armorClass (mon_schema requires both) and neither character_role nor
    character_type (char_schema's markers, which mon_schema does not have)."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if "character_role" in data or "character_type" in data:
        return None
    if "hitPoints" not in data or "armorClass" not in data:
        return None
    name = data.get("name")
    return name if isinstance(name, str) and name.strip() else None


def module_monsters(module, modules_root="modules"):
    """{stem: name} for the module's own monster files (#1997): a stem that
    get_monster_path maps back to its file, not a minted key, whose file is a
    monster stat block with a name (_sheet_name). Read once per folder state (the stamps are taken before the read, so
    a file changed during it is read again next time)."""
    if not isinstance(module, str) or not module.strip():
        return {}
    folder = os.path.abspath(os.path.join(modules_root, module.replace(" ", "_"), "monsters"))
    stamps = _folder_stamps(folder)
    if stamps is None:
        return {}
    entry = _MODULE_KEYS_MEMO.get(folder)
    if entry is not None and entry[0] == stamps:
        return dict(entry[1])
    pairs = []
    for file_name, _mtime, _size in stamps:
        stem = file_name[:-len(".json")]
        if not _STEM.fullmatch(stem) or _MINTED.fullmatch(stem):
            continue
        name = _sheet_name(os.path.join(folder, file_name))
        if name is not None:
            pairs.append((stem, name))
    _MODULE_KEYS_MEMO[folder] = (stamps, tuple(pairs))
    return dict(pairs)


def bestiary(module=None, modules_root="modules"):
    """{key: name} for the keys the DM may name: the compendium's entries,
    and with a module its own monster files (module_monsters), whose name
    replaces the compendium's for a key both have (the file is the one
    load_or_create_monster loads). At most MODULE_KEY_CAP module keys that are
    not compendium keys, in sorted order."""
    listed = _compendium()
    if module is None:
        return listed
    own = module_monsters(module, modules_root)
    added = sorted(key for key in own if key not in listed)
    if len(added) > MODULE_KEY_CAP:
        mark = (module, tuple(added))
        if mark not in _CAP_LOGGED:
            _CAP_LOGGED.add(mark)
            try:
                from utils.enhanced_logger import warning
                warning("MONSTER_KEYS: %s has %d own keys; the first %d are listed" % (
                    module, len(added), MODULE_KEY_CAP), category="combat_builder")
            except Exception:
                pass
    allowed = set(added[:MODULE_KEY_CAP])
    for key, name in own.items():
        if key in listed or key in allowed:
            listed[key] = name
    return listed


def bestiary_keys(module=None, modules_root="modules"):
    """The keys the DM may name, sorted."""
    return sorted(bestiary(module, modules_root))


def monster_key(slot, encounter_data, place_occupants, listed):
    """(key, source, stock name) for one createEncounter monster slot
    ("monster:N").

    ``place_occupants`` maps the occupant IDs at the fight's place to their
    engine records; ``listed`` is bestiary(module). source is "occupant", "listed"
    or "new". The stock name is the typed record's own name (the occupant's
    or the bestiary entry's), which a missing stat block is generated from;
    None for a new key, whose block is generated from the DM's name."""
    declared_ids = encounter_data.get("occupantIds")
    declared = declared_ids.get(slot) if isinstance(declared_ids, dict) else None
    occupant = place_occupants.get(declared) if isinstance(declared, str) else None
    if (isinstance(occupant, dict) and occupant.get("kind") == "creatures"
            and isinstance(occupant.get("type"), str) and occupant["type"]):
        return occupant["type"], "occupant", occupant.get("name") or None
    named_keys = encounter_data.get("monsterKeys")
    named = named_keys.get(slot) if isinstance(named_keys, dict) else None
    if isinstance(named, str) and named in listed:
        return named, "listed", listed[named]
    return mint_key(), "new", None
