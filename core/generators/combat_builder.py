# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

import json
import random
import sys
import os
import time
import uuid

# Add the project root to the Python path so we can import from utils, core, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import subprocess
from termcolor import colored
import logging
import shutil
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.file_operations import safe_write_json

# Set script name for logging
set_script_name("combat_builder")

logging.basicConfig(filename='modules/logs/combat_builder.log', level=logging.DEBUG)

def format_type_name(name):
    from updates.update_character_info import normalize_character_name
    return normalize_character_name(name)


def _normalize_compendium_key(value):
    """Normalize a name/key for compendium lookup.

    Lowercases, drops anything that is not alphanumeric, and collapses
    runs of whitespace/punctuation into single underscores. This lets
    'Garrick the Innkeeper', 'garrick_the_innkeeper', and
    'garrick the innkeeper' all match the same compendium key.
    """
    if not value:
        return ""
    out = []
    prev_sep = False
    for ch in str(value).lower():
        if ch.isalnum():
            out.append(ch)
            prev_sep = False
        else:
            if not prev_sep and out:
                out.append("_")
            prev_sep = True
    # Trim trailing underscore if present.
    while out and out[-1] == "_":
        out.pop()
    return "".join(out)


def _lookup_npc_in_compendium(requested_name,
                              compendium_path="data/bestiary/npc_compendium.json"):
    """Look the requested NPC up in the central compendium.

    Returns the compendium entry dict on match, or None on miss /
    missing file / malformed file. Never raises -- callers fall through
    to AI generation when this returns None.

    Match strategy: an entry matches when its 'name' has the same
    character-file key as the requested name (format_type_name, the key
    every other path files the sheet under), so a pinned name is filed
    where the rest of the game looks for it. The compendium key is an
    image-asset id and is not compared (#445).
    """
    try:
        with open(compendium_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        # Missing or corrupt compendium must NEVER block production.
        # Log and let the caller proceed with the existing AI path.
        warning(
            f"COMPENDIUM_LOOKUP: skipped (path={compendium_path!r}, "
            f"reason={type(exc).__name__}: {exc})",
            category="combat_builder",
        )
        return None
    except Exception as exc:  # defensive: never raise out of this helper
        warning(
            f"COMPENDIUM_LOOKUP: unexpected error "
            f"({type(exc).__name__}: {exc})",
            category="combat_builder",
        )
        return None

    npcs = data.get("npcs") if isinstance(data, dict) else None
    if not isinstance(npcs, dict):
        return None

    if not isinstance(requested_name, str) or not requested_name.strip():
        return None
    needle = format_type_name(requested_name)
    if not needle:
        return None

    for entry in npcs.values():
        if not isinstance(entry, dict):
            continue
        entry_name = entry.get("name")
        if (isinstance(entry_name, str) and entry_name.strip()
                and format_type_name(entry_name) == needle):
            return entry
    return None

def load_json(file_name):
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            data = json.load(file)
        logging.debug(f"Successfully loaded JSON from {file_name}")
        return data
    except FileNotFoundError:
        logging.error(f"Error: File {file_name} not found.")
        print(colored(f"Error: File {file_name} not found.", "red"))
        return None
    except json.JSONDecodeError:
        logging.error(f"Error: Invalid JSON in {file_name}.")
        print(colored(f"Error: Invalid JSON in {file_name}.", "red"))
        return None

def backup_player_file(player_file):
    backup_file = f"{player_file}.bak"
    try:
        shutil.copy2(player_file, backup_file)
        logging.debug(f"Backed up player file to {backup_file}")
    except Exception as e:
        logging.error(f"Failed to backup player file: {str(e)}")

def save_json(file_name, data):
    """Atomically save JSON to file via safe_write_json.

    Routes through utils.file_operations.safe_write_json so a crash
    mid-write cannot corrupt the target file. Preserves the legacy
    (file_name, data) call order used by existing callers.
    """
    if safe_write_json(file_name, data):
        return True
    print(colored(f"Error saving to {file_name}: atomic write failed", "red"))
    return False

def get_current_area_id():
    with open("party_tracker.json", "r", encoding="utf-8") as file:
        party_tracker = json.load(file)
    return party_tracker["worldConditions"]["currentAreaId"]

def get_current_location():
    party_tracker = load_json("party_tracker.json")
    if not party_tracker:
        print(colored("Error: Failed to load party tracker.", "red"))
        return None
    return party_tracker.get("worldConditions", {}).get("currentLocationId")

def get_next_encounter_number(location):
    """Get the next available encounter number by scanning existing encounter files"""
    import glob
    
    # Look for all encounter files matching this location's pattern
    encounter_pattern = f"modules/encounters/encounter_{location}-E*.json"
    existing_files = glob.glob(encounter_pattern)
    
    if not existing_files:
        debug(f"No existing encounters found for location {location}", category="encounter_creation")
        return 1
    
    # Extract the numbers from existing encounter files
    numbers = []
    for file_path in existing_files:
        # Extract the number from filenames like "encounter_NC01-E1.json"
        try:
            filename = os.path.basename(file_path)
            # Split by '-E' and then by '.json' to get the number
            number_part = filename.split(f"{location}-E")[1].split(".json")[0]
            numbers.append(int(number_part))
        except (IndexError, ValueError) as e:
            warning(f"Could not parse encounter number from {file_path}: {e}", category="encounter_creation")
            continue
    
    if numbers:
        next_number = max(numbers) + 1
        info(f"Found {len(numbers)} existing encounters for {location}, next number: {next_number}", category="encounter_creation")
        return next_number
    else:
        return 1

def _get_party_level():
    """Compute the average party level from party_tracker.json + character
    files. Falls back to level 1 on any failure (file lock, missing files,
    parse errors). This mirrors the legacy fallback in monster_builder.main()
    but resolves the level in the parent process so we can forward it
    explicitly on the subprocess command line via --party-level. That way
    a transient read failure in the child does NOT silently degrade a
    level-8 party to a level-1 encounter (bugs CH-C1, CH-M3).
    """
    try:
        from utils.encoding_utils import safe_json_load
        party_tracker = safe_json_load("party_tracker.json")
        if not party_tracker or not party_tracker.get("partyMembers"):
            return 1
        path_manager = ModulePathManager(party_tracker.get("module", "").replace(" ", "_") or None)
        levels = []
        for character_name in party_tracker["partyMembers"]:
            character_data = safe_json_load(path_manager.get_character_path(character_name))
            if character_data:
                levels.append(character_data.get("level", 1))
        if levels:
            return round(sum(levels) / len(levels))
        # CH-C1: party_tracker had members but NONE of their character files
        # loaded -- a read failure, not a genuinely level-1 party. Make it
        # loud so a level-8 party silently getting CR 1/8 monsters is visible.
        error(
            "CH-C1: party_tracker lists members but no character files loaded; "
            "falling back to party_level=1 (encounter difficulty will be wrong). "
            f"members={party_tracker.get('partyMembers')}",
            category="combat_builder",
        )
        return 1
    except Exception as e:
        # CH-C1: a genuine read/parse failure (file lock, malformed JSON) must
        # not silently degrade the encounter to level 1. Surface it loudly.
        error(
            f"CH-C1: failed to compute party level ({e}); falling back to "
            "party_level=1 -- encounter difficulty may be wrong.",
            exception=e,
            category="combat_builder",
        )
        return 1


def _dexterity_modifier(data):
    try:
        return (int((data.get("abilities") or {})["dexterity"]) - 10) // 2
    except (AttributeError, KeyError, TypeError, ValueError):
        return 0


def _roll_initiative(data, sheet_backed):
    """IN: one combatant's initiative.

    A character sheet (the player, an NPC or companion) is rolled by the rules
    engine: the sheet's initiative total (Dexterity, Alert, effect modifiers)
    and the roll mode its conditions impose. A monster stat block, or a sheet
    the engine cannot answer for, is d20 + its modifier (fail forward, the
    fight never waits for the engine).
    """
    if not sheet_backed:
        return random.randint(1, 20) + _dexterity_modifier(data)
    reason = "engine returned no total"
    try:
        from core.nql import checks
        started = time.monotonic()
        result = checks.resolve(data, "initiative")
        elapsed_ms = (time.monotonic() - started) * 1000
        if result.ok and type(result.total) is int:
            info(
                "IN: engine initiative: %s [%.0f ms]" % (checks.describe(result), elapsed_ms),
                category="combat_builder",
            )
            return result.total
        reason = result.reason or reason
    except Exception as exc:  # engine wrapper faults never stop a fight
        reason = str(exc)
    bonus = data.get("initiative")
    if type(bonus) is not int:
        bonus = _dexterity_modifier(data)
    warning(
        "IN: %s initiative rolled without the engine (%s)" % (data.get("name"), reason),
        category="combat_builder",
    )
    return random.randint(1, 20) + bonus


def load_or_create_monster(monster_key, monster_type):
    """The stat block named by monster_key (#293/typed-monster-key); when it
    does not exist yet, one is generated from monster_type (the typed
    record's name, or the DM's name for a new creature) and saved under
    that key."""
    print(f"[COMBAT_BUILDER] Monster load/create: '{monster_type}' -> key '{monster_key}'")
    # Get current module from party tracker for consistent path resolution
    try:
        from utils.encoding_utils import safe_json_load
        party_tracker = safe_json_load("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    monster_file = path_manager.get_monster_path(monster_key)
    monster_data = load_json(monster_file) if os.path.exists(monster_file) else None
    if not monster_data:
        print(f"[COMBAT_BUILDER] Monster file not found, creating: {monster_file}")
        warning(f"MONSTER_LOADING: Monster loading ({monster_type}) - attempting creation", category="combat_builder")
        # Get the path to monster_builder.py relative to the current file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        monster_builder_path = os.path.join(current_dir, "monster_builder.py")
        # Resolve party level here and pass it explicitly so the child
        # process is not vulnerable to a transient party_tracker.json read
        # failure silently falling back to level 1 (bug CH-M3).
        party_level = _get_party_level()
        from utils.encoding_utils import utf8_child_env
        result = subprocess.run(
            [sys.executable, monster_builder_path, monster_type,
             "--party-level", str(party_level), "--key", monster_key],
            stdin=subprocess.DEVNULL, capture_output=True,
            encoding="utf-8", errors="replace", env=utf8_child_env())
        if result.returncode == 0:
            print(f"[COMBAT_BUILDER] Monster creation successful: {monster_type}")
            info(f"SUCCESS: Monster builder ({monster_type}) - PASS", category="combat_builder")
            if os.path.exists(monster_file):
                monster_data = load_json(monster_file)
                if not monster_data:
                    print(colored(f"Error: Failed to load newly created monster data for {monster_type}", "red"))
                    return None
            else:
                print(colored(f"Error: Monster file {monster_file} was not created", "red"))
                return None
        else:
            # Non-zero return code from monster_builder subprocess
            # MUST surface to the caller -- previously this returned
            # None, which generate_encounter() then returned silently,
            # leaving callers with no indication that the build failed
            # (CH-C1). Raise RuntimeError so the failure propagates.
            print(f"[COMBAT_BUILDER] Monster creation failed: {monster_type}")
            print(f"[COMBAT_BUILDER] Error output: {result.stderr}")
            error(f"FAILURE: Monster builder ({monster_type}) - FAIL", category="combat_builder")
            raise RuntimeError(
                f"monster_builder subprocess failed for "
                f"'{monster_type}' (exit code {result.returncode}): "
                f"{result.stderr}"
            )
    else:
        print(f"[COMBAT_BUILDER] Monster loaded from file: {monster_type}")
    return monster_data

def load_or_create_npc(npc_name):
    from updates.update_character_info import name_refusal
    from utils.status_words import status_word_refusal
    refusal = name_refusal(npc_name, status_words=False)
    if refusal:
        # #949: no sheet for a name that cannot name a character.
        warning(f"COMBAT_BUILDER: NPC not created: {refusal}", category="combat_builder")
        return None
    formatted_npc_name = format_type_name(npc_name)
    print(f"[COMBAT_BUILDER] NPC name normalization: '{npc_name}' -> '{formatted_npc_name}'")
    # Get current module from party tracker for consistent path resolution
    try:
        from utils.encoding_utils import safe_json_load
        party_tracker = safe_json_load("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    # Use the formatted/normalized name for file path
    npc_file = path_manager.get_character_path(formatted_npc_name)
    # A sheet that does not exist yet is the normal first use, not an error.
    npc_data = load_json(npc_file) if os.path.exists(npc_file) else None
    
    # Not under the normalized stem: the one sheet whose own name is this
    # name, else none. A near name is never matched to another NPC's sheet
    # (or to a backup); it is a new NPC, created below as for any new name
    # (#855, family 2 Part B).
    if not npc_data:
        from updates.update_character_info import find_character_file_fuzzy
        matched = find_character_file_fuzzy(npc_name)
        if matched:
            npc_file = path_manager.get_character_path(matched)
            npc_data = load_json(npc_file) if os.path.exists(npc_file) else None

    # CH-H2 (T5-4): consult the central NPC compendium BEFORE falling
    # through to AI generation. The compendium carries identity-only
    # records (canonical name + description); it does NOT contain stat
    # blocks (HP, AC, abilities, actions). To prevent NAME DRIFT without
    # losing the AI-generated stat block, on a compendium hit we PIN
    # the canonical name and then defer stat generation to npc_builder
    # by passing the canonical name into the subprocess. Future calls
    # for the same canonical name will resolve via the module-local
    # character file (named after the canonical form) and skip both
    # compendium lookup and AI generation entirely.
    if not npc_data:
        compendium_entry = _lookup_npc_in_compendium(npc_name)
        if compendium_entry is not None:
            canonical_name = compendium_entry.get("name") or npc_name
            print(f"[COMBAT_BUILDER] Compendium hit for '{npc_name}' "
                  f"-> canonical name '{canonical_name}' "
                  f"(stats deferred to npc_builder)")
            info(
                f"COMPENDIUM_HIT: NPC '{npc_name}' pinned to canonical "
                f"name '{canonical_name}'; stat block will be generated "
                f"by npc_builder",
                category="combat_builder",
            )
            # Re-resolve the target file path using the canonical name
            # so the subprocess output lands at the canonical location.
            # Subsequent calls for any surface form that maps to this
            # canonical name will find the file on disk.
            formatted_npc_name = format_type_name(canonical_name)
            npc_file = path_manager.get_character_path(formatted_npc_name)
            # Use the canonical name as the npc_name fed to npc_builder.
            # The subprocess prompt asks the AI to "create an NPC named
            # '<name>'", so the canonical name flows into the generated
            # JSON and the resulting filename.
            npc_name = canonical_name

    if not npc_data:
        # #1119: a sheet that exists still loads under any name; a new one is
        # never made for a name carrying a status word.
        refusal = status_word_refusal(npc_name)
        if refusal:
            warning(f"COMBAT_BUILDER: NPC not created: {refusal}", category="combat_builder")
            return None
        print(f"[COMBAT_BUILDER] NPC file not found, creating: {npc_file}")
        warning(f"NPC_LOADING: NPC loading ({npc_name}) - attempting creation", category="combat_builder")
        # Resolve party level here and pass it explicitly so npc_builder
        # does not silently fall back to "level 1-3" guidance for a
        # high-level party (bug CH-C1).
        party_level = _get_party_level()
        # The builder gets the NPC's name, not its file stem, and reports the
        # file it loaded or saved, which may be under another stem (#884).
        built = None
        try:
            from core.generators.npc_builder import build_npc_file_with_path, load_schema
            set_script_name("combat_builder")  # importing npc_builder renames the log prefix
            schema = load_schema("schemas/char_schema.json")
            if schema:
                built = build_npc_file_with_path(
                    npc_name, schema, npc_level=party_level, path_manager=path_manager
                )
        except Exception as e:
            set_script_name("combat_builder")
            error(f"FAILURE: NPC builder ({npc_name}) raised", exception=e, category="combat_builder")
            built = None
        if built:
            npc_data, npc_file = built
            print(f"[COMBAT_BUILDER] NPC creation successful: {npc_name}")
            info(f"SUCCESS: NPC builder ({npc_name}) - PASS", category="combat_builder")
        else:
            print(f"[COMBAT_BUILDER] NPC creation failed: {npc_name}")
            error(f"FAILURE: NPC builder ({npc_name}) - FAIL", category="combat_builder")
            return None
    else:
        print(f"[COMBAT_BUILDER] NPC loaded from file: {npc_name}")
    return npc_data, npc_file

def player_sheet_path(path_manager, party_tracker, player):
    """The sheet path of createEncounter's player (#1258): the party member
    whose engine id (genesis.character_id, the id Party stats shows the DM)
    is the given string, an exact compare of a code-built id (D-KW-12); a
    name, or an id no single member carries, keeps the path its text names."""
    from core.nql import genesis
    from utils.encoding_utils import safe_json_load

    found = []
    for name in (party_tracker or {}).get("partyMembers") or []:
        path = path_manager.get_character_path(str(name))
        try:
            sheet = safe_json_load(path) if os.path.exists(path) else None
        except (OSError, ValueError):
            sheet = None  # an unreadable sheet is no member's match
        if isinstance(sheet, dict) and genesis.character_id(sheet) == player:
            found.append(path)
    if len(found) == 1:
        return found[0]
    return path_manager.get_character_path(player)

def _place_occupants(location_id):
    """The engine occupants at the fight's place, by ID: the typed records a
    declared occupantIds slot names. A pure reader (the DM turn makes the
    document). Empty when the engine or the document is unavailable, and the
    slot then takes a listed or a new key (never a stop)."""
    try:
        from core.nql import occupants

        tracker = load_json("party_tracker.json") or {}
        place = occupants.place_id(tracker.get("module") or "", location_id)
        response = occupants.request(view=(place,), create=False)
        if not response or not response.get("ok"):
            return {}
        return {
            occupant["id"]: occupant
            for occupant in (response.get("live_state") or {}).get("occupants") or []
            if isinstance(occupant, dict) and occupant.get("location") == place
            and isinstance(occupant.get("id"), str)
        }
    except Exception as exc:  # fail forward: the fight still starts
        warning(f"MONSTER_KEY: occupants at {location_id} unavailable ({exc})", category="combat_builder")
        return {}


ROSTER_ADDED = "rosterAddedObserver"


def _proposed_side(encounter_data, participant_key):
    """The ``side`` the DM's scene proposal gives this participant key, or None."""
    scene = encounter_data.get("scene") if isinstance(encounter_data, dict) else None
    for item in (scene or {}).get("participants") or []:
        if isinstance(item, dict) and item.get("participantKey") == participant_key:
            return item.get("side")
    return None


def _listed_npc_occupant(place_occupants, npc_file, npc_name, taken, declared=None):
    """The occupant id of the person a listed NPC is (#1415 follow-up; ruling
    on #1403): among the person occupants at the fight's place, the one the
    DM declared for this NPC's own slot (``occupantIds["npc:N"]``), else the
    one whose id ends in the loaded sheet's file stem, else the one whose
    name or alias slugs to the sheet's name. Exactly one match, or None; a
    gone occupant (count 0) or an id already taken in this encounter is
    never used. Typed ids, code-owned identifiers and names only, never a
    near name."""
    from core.nql.occupants import _person_matches
    from utils.roster_conversion import slug

    people = [
        o for o in place_occupants.values()
        if o.get("kind") == "person" and o.get("count") != 0 and o.get("id") not in taken
    ]
    if declared and any(o.get("id") == declared for o in people):
        return declared
    stem = os.path.splitext(os.path.basename(str(npc_file)))[0]
    by_stem = [o for o in people if str(o.get("id")).rsplit("/", 1)[-1] == stem]
    if len(by_stem) == 1:
        return by_stem[0]["id"]
    if by_stem:
        return None
    want = slug(npc_name)
    by_name = [o for o in people if _person_matches(o, want)]
    return by_name[0]["id"] if len(by_name) == 1 else None


def _load_npc_sheet(npc_name, path_manager):
    """(sheet, path) for a name, load only (#1425): the exact stem, else the
    one sheet whose own name is this name. Never the compendium, never
    npc_builder, so no model call. None when there is no such sheet."""
    from updates.update_character_info import find_character_file_fuzzy

    npc_file = path_manager.get_character_path(format_type_name(npc_name))
    if not os.path.exists(npc_file):
        matched = find_character_file_fuzzy(npc_name)
        if not matched:
            return None
        npc_file = path_manager.get_character_path(matched)
        if not os.path.exists(npc_file):
            return None
    npc_data = load_json(npc_file)
    return (npc_data, npc_file) if isinstance(npc_data, dict) and npc_data.get("name") else None


def _sheet_dead(npc_data):
    """A sheet that records death: status dead, or 0 HP with no unconscious
    status and no stable or unconscious condition entry. Typed fields only."""
    status = str(npc_data.get("status") or "alive").strip().lower()
    if status == "dead":
        return True
    hit_points = npc_data.get("hitPoints")
    if not isinstance(hit_points, (int, float)) or hit_points > 0 or status == "unconscious":
        return False
    conditions = npc_data.get("condition_affected") or []
    held = {str(c).strip().lower() for c in conditions if isinstance(c, str)}
    return not held & {"stable", "unconscious"}


def _roster_candidates(place_occupants, party_tracker):
    """The named single persons present by record (#1425): person occupants
    at the fight's place with count 1, then the party's companions. Groups
    are never candidates. One entry per occupant id."""
    out, ids = [], set()
    for occupant_id, occupant in place_occupants.items():
        if occupant.get("kind") != "person" or occupant.get("count", 1) != 1 or occupant.get("range"):
            continue
        if isinstance(occupant.get("name"), str) and occupant["name"].strip():
            out.append({"name": occupant["name"], "occupantId": occupant_id,
                        "attitude": occupant.get("attitude"), "atPlace": True})
            ids.add(occupant_id)
    for entry in (party_tracker or {}).get("partyNPCs") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        occupant_id = entry.get("occupantId")
        if occupant_id in ids:
            continue
        out.append({"name": entry["name"], "occupantId": occupant_id, "attitude": None, "atPlace": False})
        if occupant_id:
            ids.add(occupant_id)
    return out


PENDING_SOURCE = "occupant"


def _pending_observer(candidate, present_names):
    """#1447: the observer creature for a person present at the fight's place
    whose sheet does not exist yet, from the occupant record alone: name,
    occupantId and side, with ``statsPending`` and no hit points, armor class
    or initiative (none are invented). The first intent that targets it
    builds the sheet (combat_orchestrator._ensure_targeted_sheets). None for
    a companion (a party member always has a sheet) or a name already in
    the fight."""
    if not candidate.get("atPlace") or not candidate.get("occupantId"):
        return None
    if candidate["name"] in present_names:
        return None
    return {
        "name": candidate["name"],
        "type": "npc",
        "npcType": format_type_name(candidate["name"]),
        "status": "alive",
        "conditions": [],
        "actions": {"actionType": "", "target": ""},
        "faction": "hostile" if candidate["attitude"] == "hostile" else "party",
        "occupantId": candidate["occupantId"],
        "statsPending": True,
    }


def _roster_observers(encounter, scene_sources, place_occupants, party_tracker,
                      encounter_data, path_manager):
    """Add each present named person the DM left out of the fight as an
    observer creature (#1425). Returns the added scene sources; they are
    kept out of the reconciled snapshot, since the DM proposed no key for
    them. The model still decides who fights."""
    present_ids = {v for v in (encounter_data.get("occupantIds") or {}).values() if isinstance(v, str)}
    present_ids |= {c.get("occupantId") for c in encounter["creatures"] if c.get("occupantId")}
    present_paths = {os.path.realpath(s["sourceRef"]) for s in scene_sources}
    present_names = {s["displayName"] for s in scene_sources}
    added = []
    for candidate in _roster_candidates(place_occupants, party_tracker):
        if candidate["occupantId"] and candidate["occupantId"] in present_ids:
            continue
        loaded = _load_npc_sheet(candidate["name"], path_manager)
        if not loaded:
            pending = _pending_observer(candidate, present_names)
            if pending is None:
                warning(f"ROSTER: no sheet for {candidate['occupantId'] or candidate['name']}, not added",
                        category="combat_builder")
                continue
            present_ids.add(candidate["occupantId"])
            present_names.add(candidate["name"])
            encounter["creatures"].append(pending)
            added.append(
                {
                    "participantKey": f"roster:{len(added)}",
                    "creature": pending,
                    "sourceKind": PENDING_SOURCE,
                    "sourceRef": candidate["occupantId"],
                    "displayName": candidate["name"],
                }
            )
            continue
        npc_data, npc_file = loaded
        if os.path.realpath(npc_file) in present_paths or npc_data["name"] in present_names:
            continue
        if _sheet_dead(npc_data):
            continue
        npc = {
            "name": npc_data["name"],
            "type": "npc",
            "npcType": format_type_name(npc_data["name"]),
            "initiative": _roll_initiative(npc_data, sheet_backed=True),
            "status": npc_data.get("status", "alive"),
            "conditions": npc_data.get("condition_affected", []),
            "actions": {"actionType": "", "target": ""},
            "currentHitPoints": npc_data.get("hitPoints", 10),
            "maxHitPoints": npc_data.get("maxHitPoints", 10),
            "armorClass": npc_data.get("armorClass", 10),
            "faction": "hostile" if candidate["attitude"] == "hostile" else "party",
        }
        if candidate["occupantId"]:
            npc["occupantId"] = candidate["occupantId"]
            present_ids.add(candidate["occupantId"])
        present_paths.add(os.path.realpath(npc_file))
        present_names.add(npc_data["name"])
        encounter["creatures"].append(npc)
        added.append(
            {
                "participantKey": f"roster:{len(added)}",
                "creature": npc,
                "sourceKind": "character",
                "sourceRef": str(npc_file),
                "displayName": npc_data["name"],
            }
        )
    return added


def generate_encounter(encounter_data):
    print(f"[COMBAT_BUILDER] Starting encounter generation with data: player={encounter_data.get('player')}, npcs={encounter_data.get('npcs', [])}, monsters={encounter_data.get('monsters', [])}")
    location = get_current_location()
    if not location:
        return None
    
    encounter_number = get_next_encounter_number(location)
    encounter_id = f"{location}-E{encounter_number}"
    
    encounter = {
        "encounterId": encounter_id,
        "creatures": []
    }
    scene_sources = []

    if "encounterSummary" in encounter_data:
        encounter["encounterSummary"] = encounter_data["encounterSummary"]
    copy_opening_action(encounter_data, encounter)

    # Add player
    # Get current module from party tracker for consistent path resolution
    party_tracker = None
    try:
        from utils.encoding_utils import safe_json_load
        party_tracker = safe_json_load("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    player_file = player_sheet_path(path_manager, party_tracker, encounter_data['player'])
    logging.debug(f"Attempting to load player data from {player_file}")
    
    backup_player_file(player_file)
    player_data = load_json(player_file)
    
    if not player_data:
        logging.error(f"Failed to load player data from {player_file}")
        print(colored(f"Error: Failed to load player data from {player_file}", "red"))
        # Attempt to load from backup
        backup_file = f"{player_file}.bak"
        player_data = load_json(backup_file)
        if player_data:
            logging.info(f"Loaded player data from backup file {backup_file}")
            print(colored(f"Loaded player data from backup file {backup_file}", "yellow"))
        else:
            return None

    logging.debug(f"Loaded player data: {json.dumps(player_data, indent=2)}")

    player = {
        "name": player_data["name"],
        "type": "player",
        "initiative": _roll_initiative(player_data, sheet_backed=True),
        "status": player_data.get("status", "alive"),
        "conditions": player_data.get("condition_affected", []),
        "actions": {"actionType": "", "target": ""},
        "currentHitPoints": player_data["hitPoints"],
        "maxHitPoints": player_data["maxHitPoints"],
        "armorClass": player_data["armorClass"]
    }
    encounter["creatures"].append(player)
    scene_sources.append(
        {
            "participantKey": "player:0",
            "creature": player,
            "sourceKind": "character",
            "sourceRef": str(player_file),
            "displayName": player_data["name"],
        }
    )

    # Add monsters. Each one's stat block is chosen by a typed key, never by
    # the name the DM wrote (#293/typed-monster-key, D-KW-12, D-TMK-1).
    from core.combat.monster_keys import bestiary, monster_key
    place_occupants = _place_occupants(location)
    listed = bestiary()
    used_names = set()
    new_keys = {}
    for monster_index, monster_type in enumerate(encounter_data["monsters"]):
        slot = f"monster:{monster_index}"
        key, key_source, stock_name = monster_key(slot, encounter_data, place_occupants, listed)
        if key_source == "new" and isinstance(monster_type, str):
            # Slots the DM wrote with the same string in this one declaration
            # are one new kind of creature: one key, one generated stat block
            # (D-TMK-3: exact equality within one createEncounter, never a
            # lookup of stored data).
            key = new_keys.setdefault(monster_type, key)
        print(f"[COMBAT_BUILDER] Loading/creating monster: {monster_type} -> key {key} ({key_source})")
        info(f"MONSTER_KEY: {encounter_id} {slot} -> {key} ({key_source})", category="combat_builder")
        monster_data = load_or_create_monster(key, stock_name or monster_type)
        if not monster_data:
            return None

        # Copies are counted by the stat block's own name, so two keys whose
        # blocks share a name still give two names (the resolver keys by name).
        base_name = monster_data['name']
        monster_name, copy = base_name, 1
        while monster_name in used_names:
            copy += 1
            monster_name = f"{base_name}_{copy}"
        used_names.add(monster_name)

        monster = {
            "name": monster_name,
            "type": "enemy",
            "monsterType": key,
            "initiative": _roll_initiative(monster_data, sheet_backed=False),
            "status": "alive",
            "conditions": [],
            "actions": {"actionType": "", "target": ""},
            "currentHitPoints": monster_data["hitPoints"],
            "maxHitPoints": monster_data["hitPoints"],
            # Typed combat reloads represented mechanics immediately before
            # accepting a provider result. Keep the encounter-instance AC
            # beside HP so that reload uses the same authoritative value as
            # intent resolution instead of the resolver's legacy default.
            "armorClass": monster_data.get("armorClass", 10),
        }
        # The engine's occupant this monster belongs to, when the DM declared
        # the fight by ID from the location's occupants list (P4-d). A missing
        # or unknown ID is settled by the host before combat starts.
        declared_id = (encounter_data.get("occupantIds") or {}).get(f"monster:{monster_index}")
        if isinstance(declared_id, str) and declared_id.startswith("occ:"):
            monster["occupantId"] = declared_id
        encounter["creatures"].append(monster)
        scene_sources.append(
            {
                "participantKey": f"monster:{monster_index}",
                "creature": monster,
                "sourceKind": "monster",
                "sourceRef": str(path_manager.get_monster_path(key)),
                "displayName": monster_data["name"],
            }
        )

    # Add NPCs
    npc_counts = {}
    for npc_index, npc_name in enumerate(encounter_data.get("npcs", [])):
        formatted_npc_type = format_type_name(npc_name)
        loaded_npc = load_or_create_npc(npc_name)
        if not loaded_npc:
            return None
        npc_data, canonical_npc_file = loaded_npc

        npc_counts[formatted_npc_type] = npc_counts.get(formatted_npc_type, 0) + 1
        
        if npc_counts[formatted_npc_type] > 1:
            npc_full_name = f"{npc_data['name']}_{npc_counts[formatted_npc_type]}"
        else:
            npc_full_name = npc_data['name']

        npc = {
            "name": npc_full_name,
            "type": "npc",
            "npcType": formatted_npc_type,
            "initiative": _roll_initiative(npc_data, sheet_backed=True),
            "status": npc_data.get("status", "alive"),
            "conditions": npc_data.get("condition_affected", []),
            "actions": {"actionType": "", "target": ""},
            "currentHitPoints": npc_data.get("hitPoints", 10),
            "maxHitPoints": npc_data.get("maxHitPoints", 10),
            "armorClass": npc_data.get("armorClass", 10)
        }
        declared_ids = encounter_data.get("occupantIds") or {}
        own_slot = f"npc:{npc_index}"
        taken = {v for k, v in declared_ids.items() if isinstance(v, str) and k != own_slot}
        taken |= {c["occupantId"] for c in encounter["creatures"] if c.get("occupantId")}
        occupant_id = _listed_npc_occupant(
            place_occupants, canonical_npc_file, npc_data["name"], taken,
            declared=declared_ids.get(own_slot) if isinstance(declared_ids.get(own_slot), str) else None,
        )
        if occupant_id:
            npc["occupantId"] = occupant_id
        # #1449: the DM's typed side for this slot sets the fight's faction;
        # without one, ensure_combatant_ids keeps today's party default. The
        # value is validated with the rest of the scene (reconcile_scene_manifest).
        side = _proposed_side(encounter_data, f"npc:{npc_index}")
        if side in ("hostile", "party"):
            npc["faction"] = side
        # Add the NPC to the encounter's creatures array
        encounter["creatures"].append(npc)
        scene_sources.append(
            {
                "participantKey": f"npc:{npc_index}",
                "creature": npc,
                "sourceKind": "character",
                "sourceRef": str(canonical_npc_file),
                "displayName": npc_data["name"],
            }
        )

    roster_sources = _roster_observers(
        encounter, scene_sources, place_occupants, party_tracker, encounter_data, path_manager
    )

    # Every genuinely new encounter is typed-agentic. Persisted provenance,
    # never a hidden runtime selector, keeps old encounters on their existing
    # compatibility route.
    from core.combat.scene import reconcile_scene_manifest
    from core.managers.combat_state import ensure_combatant_ids, ensure_combat_state

    ensure_combatant_ids(encounter)
    canonical_snapshot = [
        {
            "participantKey": item["participantKey"],
            "combatantId": item["creature"]["combatantId"],
            "sourceKind": item["sourceKind"],
            "sourceRef": item["sourceRef"],
            "displayName": item["displayName"],
        }
        for item in scene_sources
    ]
    reconciled = reconcile_scene_manifest(encounter_data, canonical_snapshot)
    encounter["sceneFacts"] = reconciled["sceneFacts"]
    for item in roster_sources:
        row = {
            "combatantId": item["creature"]["combatantId"],
            "sourceKind": item["sourceKind"],
            "sourceRef": item["sourceRef"],
            "displayName": item["displayName"],
            "participation": "observer",
            "initiativeEligible": False,
            "persistence": "canonical_character",
            "provenance": ROSTER_ADDED,
        }
        if item["creature"].get("occupantId"):
            row["occupantId"] = item["creature"]["occupantId"]
        encounter["sceneFacts"]["participants"].append(row)
        reconciled["controllers"][item["creature"]["combatantId"]] = {
            "controller": "actor_agent",
            "revision": 0,
            "cause": ROSTER_ADDED,
            "scope": "encounter",
            "expiresAtRevision": None,
            "consentEventId": None,
        }
    _apply_surprise(encounter, reconciled["sceneFacts"]["participants"])
    ensure_combat_state(
        encounter,
        new_encounter=True,
        pipeline_mode="agentic",
    )
    encounter["combatState"]["controllers"] = reconciled["controllers"]
    tracker_snapshot = load_json("party_tracker.json") or {}
    expected_active = (
        tracker_snapshot.get("worldConditions", {}).get("activeCombatEncounter") or None
    )
    encounter["combatState"]["activation"] = {
        "activationId": "combat-activation:%s:%s"
        % (encounter["encounterId"], uuid.uuid4().hex),
        "encounterId": encounter["encounterId"],
        "expectedTrackerEncounterId": expected_active,
        "status": "preparing",
        "historyMarkerEncounterId": None,
        "trackerActivated": False,
    }

    return encounter

SURPRISE_EFFECT_NAME = "Surprised"


def _apply_surprise(encounter, participants):
    """Give each surprised monster a one-round incapacitating effect (#834).

    5e surprise: a creature that had not noticed the threat when the fight
    began cannot act on its first turn. The existing incapacitated-turn skip
    consumes that round 1 turn, and the effect expires at the end of round 1
    (its ID is not round-stamped, so the first end-of-round tick removes it).
    """
    from core.combat.resolver import _apply_encounter_effect_operation

    surprised = {
        item["combatantId"]
        for item in participants
        if item.get("surprised") and item.get("initiativeEligible")
    }
    for creature in encounter.get("creatures", []):
        combatant_id = creature.get("combatantId")
        if combatant_id not in surprised:
            continue
        _apply_encounter_effect_operation(
            creature,
            {
                "op": "add",
                "effect": {
                    "effectId": f"surprise-{combatant_id}",
                    "name": SURPRISE_EFFECT_NAME,
                    "description": "Caught unaware: cannot move, act or react in round 1.",
                    "incapacitates": True,
                    "roundsRemaining": 1,
                    "durationKind": "rounds",
                    "tickTrigger": "end_of_round",
                },
            },
        )
        creature["effectIncapacitated"] = True


def surprise_opening_rules(encounter):
    """Name the creatures that open the fight surprised (#837).

    The engine already skips their round 1 turn; without this the opening
    narration has them shouting challenges and moving before anyone acts.
    """
    from core.managers.combat_state import combatant_presentation_name

    names = [
        combatant_presentation_name(
            encounter, creature.get("combatantId"), creature.get("name")
        )
        for creature in encounter.get("creatures", [])
        if any(
            isinstance(effect, dict) and effect.get("name") == SURPRISE_EFFECT_NAME
            for effect in creature.get("activeEffects") or []
        )
    ]
    if not names:
        return ""
    return (
        "Surprise: " + ", ".join(names) + " did not notice the party until "
        "this moment and lose their round 1 turn. Narrate them caught off "
        "guard (startled, turning, scrambling for a weapon); before the party "
        "acts they make no attack, no move and no challenge or speech."
    )


# #882: the longest declared opening action kept on the encounter.
OPENING_ACTION_LIMIT = 300


def copy_opening_action(encounter_data, encounter):
    """#882: keep the player's own declared first action on the encounter, to
    offer it at their first combat turn. The text is passed through, never
    read; anything but a non-empty string is dropped. #1334: one the DM marks
    as from an earlier turn (openingActionSource) is dropped too, so a restored
    or stale declaration is never offered; an absent source keeps it."""
    opening_action = encounter_data.get("openingAction")
    if encounter_data.get("openingActionSource") == "earlier_turn":
        if opening_action is not None:
            logging.debug("openingAction dropped: openingActionSource is earlier_turn")
        return
    if isinstance(opening_action, str) and opening_action.strip():
        encounter["openingAction"] = opening_action.strip()[:OPENING_ACTION_LIMIT]
        encounter["openingActionOffered"] = False
    elif opening_action is not None:
        logging.debug("openingAction dropped: not a non-empty string")


def opening_action_rules(encounter):
    """The opening note for a declared first action (#882), or ""."""
    text = encounter.get("openingAction")
    if not isinstance(text, str) or not text.strip():
        return ""
    text = text.strip()
    if not text.endswith((".", "!", "?")):
        text += "."
    return (
        "The player has declared their first action: " + text + " "
        "It is resolved on the player's turn: do not narrate it resolved and "
        "do not ask the player what they do."
    )



RESULT_VERSION = 1


def _write_result(result_file, status, encounter_id=None, encounter_file=None):
    """Hand the caller a typed result; printed lines are for people only (#812)."""
    if not result_file:
        return True
    result = {"version": RESULT_VERSION, "status": status}
    if encounter_id is not None:
        result["encounterId"] = encounter_id
        result["encounterFile"] = encounter_file
    if save_json(result_file, result):
        return True
    logging.error(f"Failed to write the builder result to {result_file}")
    return False


def main(argv=None):
    """Build one encounter from the JSON on stdin.

    Exits 0 only when the encounter is saved, else 1. With --result-file the
    outcome is also written there as {"version", "status", "encounterId",
    "encounterFile"}; status is saved, invalid_input, generation_failed or
    save_failed (#812).
    """
    import argparse

    parser = argparse.ArgumentParser(description="Build a combat encounter from JSON on stdin.")
    parser.add_argument("--result-file", default=None)
    result_file = parser.parse_args(sys.argv[1:] if argv is None else argv).result_file
    logging.debug("Starting combat encounter creation")
    
    # Read input from stdin
    storyteller_input = sys.stdin.read()

    try:
        # Parse the JSON input
        input_data = json.loads(storyteller_input)

        # Extract the encounter data directly from the input
        encounter_data = input_data["parameters"]

        if "player" not in encounter_data or "monsters" not in encounter_data:
            print(colored("Error: Invalid encounter data format. 'player' and 'monsters' are required.", "red"))
            _write_result(result_file, "invalid_input")
            return 1

        # NPCs are optional, so we don't check for their presence

    except json.JSONDecodeError:
        print(colored("Error: Invalid JSON format in storyteller input.", "red"))
        _write_result(result_file, "invalid_input")
        return 1
    except KeyError as e:
        print(colored(f"Error: Missing key in JSON structure: {e}", "red"))
        _write_result(result_file, "invalid_input")
        return 1

    encounter = generate_encounter(encounter_data)
    
    if encounter:
        print(f"[COMBAT_BUILDER] Encounter generated successfully: {encounter['encounterId']}")
        print(f"[COMBAT_BUILDER] Total creatures in encounter: {len(encounter['creatures'])}")
        # Ensure centralized encounters directory exists
        os.makedirs("modules/encounters", exist_ok=True)
        encounter_file = f"modules/encounters/encounter_{encounter['encounterId']}.json"
        logging.debug(f"Saving encounter data: {json.dumps(encounter, indent=2)}")
        if save_json(encounter_file, encounter):
            logging.info(f"Encounter successfully built and saved to {encounter_file}")
            print(colored(f"Encounter successfully built and saved to {encounter_file}", "green"))
            
            print(
                "[COMBAT_BUILDER] Encounter is durably prepared; "
                "activation waits for the full combat history marker"
            )
            if _write_result(result_file, "saved", encounter["encounterId"], encounter_file):
                return 0
            return 1
        else:
            logging.error(f"Failed to save encounter to {encounter_file}")
            print(colored(f"Error: Failed to save encounter to {encounter_file}", "red"))
            _write_result(result_file, "save_failed")
            return 1
    else:
        print(f"[COMBAT_BUILDER] Encounter generation failed")
        logging.error("Failed to generate encounter due to previous errors.")
        print(colored("Error: Failed to generate encounter due to previous errors.", "red"))
        _write_result(result_file, "generation_failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
