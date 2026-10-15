"""Proper names for a game saved before #1119.

Module NPCs used to carry status words ("Wounded Ranger Gareth"). The NPC
builder stripped the word, so a recruited companion's sheet was "Ranger
Gareth" while the roster kept the module's name and no lookup found him. New
names can no longer carry a status word (utils/status_words.py); this runs
once at load and gives an existing game the proper names:

- each party NPC whose name carries a status word takes the name without it,
  only when a sheet of exactly that name exists and the old name has none;
- in every module's areas, context and declaration, each NPC name carrying a
  status word takes the name without it (a monster entry of the same name at
  the same place is renamed with it, as the shipped module does). The
  context's npcs entries and references follow only for a name renamed as a
  placed NPC, so an entry no place holds ("Corrupted Woodland Creatures", a
  creature group) keeps its name.

Only structured name fields change, never prose. A save is made first. Nothing
runs during a fight. A game with nothing to rename is left as it is, so the
update is idempotent.
"""

import glob
import json
import os

from utils.enhanced_logger import info, warning
from utils.file_operations import safe_write_json
from utils.status_words import name_without_status_words, status_word_refusal

MODULES_DIR = "modules"


class NameMigrationError(RuntimeError):
    pass


def _load(path):
    """The document as stored, or None. A plain load: safe_json_load also
    rewrites typography, and only name fields may change here."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _proper(name):
    """The proper name for a name carrying a status word, else None."""
    if not isinstance(name, str) or not status_word_refusal(name):
        return None
    return name_without_status_words(name) or None


def _key_proper(key):
    """The context key ("wounded_scout_neris") for the proper name, else None."""
    proper = _proper(key.replace("_", " ")) if isinstance(key, str) else None
    return proper.replace(" ", "_") if proper else None


def _roster_renames(party):
    from updates.update_character_info import find_character_file_fuzzy

    renames = []
    roster = party.get("partyNPCs") or []
    taken = {str(npc.get("name", "")).casefold() for npc in roster if isinstance(npc, dict)}
    for index, npc in enumerate(roster):
        if not isinstance(npc, dict):
            continue
        old = npc.get("name")
        new = _proper(old)
        if not new:
            continue
        if new.casefold() in taken:
            warning(f"NAME_MIGRATION: party NPC {old!r} kept: {new!r} is already in the party",
                    category="character_updates")
        elif find_character_file_fuzzy(old):
            warning(f"NAME_MIGRATION: party NPC {old!r} kept: it has its own sheet",
                    category="character_updates")
        elif not find_character_file_fuzzy(new):
            warning(f"NAME_MIGRATION: party NPC {old!r} kept: no sheet named {new!r}",
                    category="character_updates")
        else:
            renames.append(("party_tracker.json", f"partyNPCs[{index}]", old, new))
    return renames


def _module_dirs():
    return sorted(
        path for path in glob.glob(os.path.join(MODULES_DIR, "*"))
        if os.path.isdir(os.path.join(path, "areas")) and not os.path.basename(path).startswith(".")
    )


def _area_files(module_dir):
    return sorted(
        path for path in glob.glob(os.path.join(module_dir, "areas", "*.json"))
        if ".backup" not in os.path.basename(path) and not path.endswith(".bak")
    )


def _rename_area(data, path, renames):
    for loc in data.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        renamed = {}
        for i, npc in enumerate(loc.get("npcs") or []):
            new = _proper(npc.get("name")) if isinstance(npc, dict) else None
            if new:
                renames.append((path, f"{loc.get('locationId')}.npcs[{i}].name", npc["name"], new))
                renamed[npc["name"]] = new
                npc["name"] = new
        for i, monster in enumerate(loc.get("monsters") or []):
            if isinstance(monster, dict) and monster.get("name") in renamed:
                new = renamed[monster["name"]]
                renames.append((path, f"{loc.get('locationId')}.monsters[{i}].name", monster["name"], new))
                monster["name"] = new


def _rename_list(names, path, where, renames):
    for i, name in enumerate(names):
        new = _proper(name)
        if new:
            renames.append((path, f"{where}[{i}]", name, new))
            names[i] = new


def _rename_context(data, path, renames, placed):
    """placed: the old names renamed as placed NPCs; the context's npcs entries
    and references keys follow those names only."""
    for section in ("areas", "locations"):
        for key, entry in (data.get(section) or {}).items():
            if isinstance(entry, dict) and isinstance(entry.get("npcs"), list):
                found = []
                _rename_list(entry["npcs"], path, f"{section}.{key}.npcs", found)
                placed.update(old for _, _, old, _ in found)
                renames += found
    npcs = data.get("npcs")
    if isinstance(npcs, dict):
        for key in list(npcs):
            entry = npcs[key]
            old = entry.get("name") if isinstance(entry, dict) else None
            if old not in placed:
                continue
            new = _proper(old)
            renames.append((path, f"npcs.{key}.name", old, new))
            entry["name"] = new
            new_key = _key_proper(key)
            if new_key and new_key not in npcs:
                renames.append((path, "npcs key", key, new_key))
                npcs[new_key] = npcs.pop(key)
    refs = data.get("references")
    if isinstance(refs, dict):
        for key in list(refs):
            if not key.startswith("npc:") or key[4:] not in placed:
                continue
            new = "npc:" + _proper(key[4:])
            if new not in refs:
                renames.append((path, "references key", key, new))
                refs[new] = refs.pop(key)


def _rename_declaration(data, path, renames):
    for i, entry in enumerate(data.get("dispositions") or []):
        new = _proper(entry.get("name")) if isinstance(entry, dict) else None
        if new:
            renames.append((path, f"dispositions[{i}].name", entry["name"], new))
            entry["name"] = new


def plan_name_migration():
    """The renames this game needs, and the updated documents by path."""
    party = _load("party_tracker.json")
    if not isinstance(party, dict):
        return [], {}
    renames, documents = [], {}
    roster = _roster_renames(party)
    if roster:
        for _, where, old, new in roster:
            party["partyNPCs"][int(where[len("partyNPCs["):-1])]["name"] = new
        renames += roster
        documents["party_tracker.json"] = party
    for module_dir in _module_dirs():
        placed = {old for _, _, old, _ in roster}
        targets = [(path, _rename_area) for path in _area_files(module_dir)]
        targets.append((os.path.join(module_dir, "module_declaration.json"), _rename_declaration))
        # The context last: its npcs entries follow the names renamed above.
        targets += [(os.path.join(module_dir, name), lambda d, p, f: _rename_context(d, p, f, placed))
                    for name in ("module_context.json", "module_context_BU.json")]
        for path, rename in targets:
            if not os.path.exists(path):
                continue
            data = _load(path)
            if not isinstance(data, dict):
                continue
            found = []
            rename(data, path, found)
            placed.update(old for _, _, old, _ in found)
            if found:
                renames += found
                documents[path] = data
    return renames, documents


def _create_backup():
    from updates.save_game_manager import SaveGameManager

    manager = SaveGameManager()
    before = {item.get("save_folder") for item in manager.list_save_games()}
    success, message = manager.create_save_game(
        "Automatic backup before the NPC name update", "essential"
    )
    if not success:
        raise NameMigrationError("pre-update save failed: %s" % message)
    created = next((item for item in manager.list_save_games()
                    if item.get("save_folder") not in before), None)
    if not created:
        raise NameMigrationError("pre-update save could not be identified")
    return created.get("save_folder")


def run_name_migration(create_backup=True):
    """Give this game proper NPC names once; return what was done.

    {"status": "none"} when nothing needs renaming, {"status": "deferred"}
    during a fight, else {"status": "renamed", "renames": [...],
    "backupFolder": ...}. Raises NameMigrationError when the save before the
    update or a write fails."""
    party = _load("party_tracker.json")
    if isinstance(party, dict) and (party.get("worldConditions") or {}).get("activeCombatEncounter"):
        return {"status": "deferred", "reason": "active combat must reach a safe boundary"}
    renames, documents = plan_name_migration()
    if not renames:
        return {"status": "none"}
    backup_folder = _create_backup() if create_backup else None
    for path, data in documents.items():
        if not safe_write_json(path, data):
            raise NameMigrationError(f"could not write {path}; restore save {backup_folder!r}")
    for path, where, old, new in renames:
        info(f"NAME_MIGRATION: {path} {where}: {old!r} -> {new!r}", category="character_updates")
    return {"status": "renamed", "renames": [list(r) for r in renames], "backupFolder": backup_folder}
