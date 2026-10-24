# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Community Tools - Npc Builder
Copyright (c) 2024 MoonlightByte
Licensed under Apache License 2.0

See LICENSE-APACHE file for full terms.
"""

# ============================================================================
# NPC_BUILDER.PY - AI-POWERED CHARACTER CREATION
# ============================================================================
#
# ARCHITECTURE ROLE: Content Generation Layer - Character Creation
#
# This module provides comprehensive AI-driven NPC creation with schema validation,
# generating detailed character profiles, stats, and background information
# for integration with the module-centric architecture.
#
# KEY RESPONSIBILITIES:
# - AI-powered NPC character generation with personality and background
# - Schema-compliant character data creation and validation
# - Integration with module path management for file organization
# - Character stat generation with 5th edition of the world's most popular roleplaying game rule compliance
# - NPC profile creation with narrative and mechanical consistency
# - Batch character creation for module population
#

import copy
import json
import sys
import os
import re

# Add the project root to the Python path so we can import from utils, core, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jsonschema import validate, ValidationError
import config
from core.ai import api_client
from core.leveling import choices as class_choices
from core.leveling import tables as class_tables
from core.nql.legacy_loadout import RECEIPT_FIELD, migrate as repair_initial_loadout
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.character_sheet_contract import repair_required_ammunition_field
from utils.file_operations import safe_write_json
from utils.single_target_generation import (
    load_valid_generated_target,
    single_target_generation,
)
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T035", "core/generators/npc_builder.py", 185)
from utils.capture.live_provider_call import LiveProviderSuperseded
from core.combat.invocation import InvocationSupersededError
from utils.schema_feedback import (
    informed_retry_messages,
    issue_paths_for_log,
    json_correction,
    schema_correction,
    validation_issues,
)

# Token tracking import
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except ImportError:
    USAGE_TRACKING_AVAILABLE = False

# Set script name for logging
set_script_name("npc_builder")

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# For now, I'll assume OPENAI_API_KEY is correctly defined in your config.py as used by other scripts.

def load_schema(file_name):
    try:
        with open(file_name, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"{RED}Error: File {file_name} not found.{RESET}")
        return None
    except json.JSONDecodeError:
        print(f"{RED}Error: Invalid JSON in {file_name}.{RESET}")
        return None

def load_prompt(file_name):
    try:
        with open(file_name, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"{RED}Error: File {file_name} not found.{RESET}")
        return None
    except Exception as e:
        print(f"{RED}Error reading {file_name}: {str(e)}{RESET}")
        return None

def _requested_level(npc_level):
    """The level a request names, 1 to 20, or None."""
    text = str(npc_level).strip() if npc_level is not None else ""
    return int(text) if text.isascii() and text.isdigit() and 1 <= int(text) <= 20 else None

def _srd_class_reference(npc_class, npc_level):
    """The game's SRD 5.2.1 class tables for one NPC request (#533): for the
    requested class when it is an SRD class, else for every SRD class (a blank
    request, or one naming a class the tables do not have), the features each
    level grants up to the requested level (3 when it names none), and at that
    level the class table's columns, spell slots and spell counts; once the
    level reaches the subclass level, each subclass with the features it grants
    up to that level; and for a caster, its SRD spell list (#1001): cantrips when
    the class has them, then each spell level it has slots for at that level.
    When the spell repository cannot be read, the reference has no lists."""
    level = _requested_level(npc_level) or 3
    classes = class_tables.tables()["classes"]
    try:
        repository = list({id(entry): entry for entry in class_choices.spells().values()}.values())
    except Exception as e:
        warning(f"NPC spell lists not built: {e}", category="npc_creation")
        repository = None
    key = class_tables.class_key({"class": str(npc_class or "").strip()})
    keys = [key] if key else list(classes)
    reference = {}
    for key in keys:
        data = classes[key]
        entry = {
            "features_by_level": {str(n): data["features_by_level"].get(str(n), []) for n in range(1, level + 1)},
            "table_columns": {name: rows.get(str(level)) for name, rows in (data.get("table_columns") or {}).items()
                              if isinstance(rows, dict) and str(level) in rows},
            "spell_slots": {slot: n for slot, n in class_tables.slot_maxima(key, level).items() if n},
            "spell_counts": {kind: n for kind, n in class_tables.spell_counts(key, level).items() if n is not None},
        }
        if type(data.get("subclass_level")) is int and level >= data["subclass_level"]:
            entry["subclasses"] = {
                name: {str(n): features for n in range(1, level + 1)
                       for features in [class_tables.subclass_features(key, name, n)] if features}
                for name in class_tables.subclass_options(key)}
        name = data.get("name") or key.capitalize()
        levels = ([0] if entry["spell_counts"].get("cantrips") else []) + [
            int(slot[len("level"):]) for slot in entry["spell_slots"] if slot.startswith("level")]
        if repository is not None and levels:
            entry["spells"] = {str(n): sorted(spell["name"] for spell in repository
                                              if spell.get("level") == n and name in (spell.get("classes") or []))
                               for n in range(0 if 0 in levels else 1, max(levels) + 1)}
        reference[name] = entry
    return {"level": level, "classes": reference}

def _srd_origin_reference(npc_race, npc_background):
    """The game's SRD 5.2.1 origins for one NPC request (#1055): the background
    ability score rule, the species the request names (every species when it
    names none, or one the data does not have, such as a subrace) and likewise
    the background, each entry as the origins file holds it, less the new
    character's typed starting packages (key, equipment_options and its slots)
    and the creation scope's typed refs (species key, background feat_ref),
    which no NPC draft uses."""
    from core.leveling.fighting_style import ORIGINS_BASENAME
    from utils.encoding_utils import safe_json_load
    origins = safe_json_load(os.path.join(os.path.dirname(os.path.dirname(class_tables._DATA)), ORIGINS_BASENAME))

    def named(entries, request):
        wanted = str(request or "").strip().casefold()
        match = [entry for entry in entries if str(entry.get("name", "")).casefold() == wanted]
        return match or list(entries)

    # the slots are inside equipment_options; key, feat_ref and the typed lists are the creation scope's and
    # the engine build's typed refs (D-CREATE-COST-4/-5)
    startup_only = ("equipment_options", "key", "feat_ref", "skill_keys", "tool_keys", "tool_choice",
                    "ability_keys")
    return {
        "background_ability_scores_rule": origins["background_ability_scores_rule"],
        "species": [{k: v for k, v in entry.items() if k not in ("key", "grants")}
                    for entry in named(origins["species"], npc_race)],
        "backgrounds": [{k: v for k, v in entry.items() if k not in startup_only}
                        for entry in named(origins["backgrounds"], npc_background)],
    }

def _set_class_tables(npc_data):
    """A fresh draft's spell slots and feature uses from the SRD class tables
    (#533), as startup sets them for a new hero (#704). Each slot level the
    class table grants at the sheet's level is set full, and each use pool
    the class has is set full on the classFeatures entry that names it; a
    pool whose feature the sheet does not list is logged, not invented. Slot
    levels the table does not grant are left as written. A sheet without an
    SRD class and a level from 1 to 20 is returned unchanged, and so is one
    this step fails on."""
    cls = class_tables.class_key(npc_data)
    level = npc_data.get("level")
    if cls is None or type(level) is not int or not 1 <= level <= 20:
        return npc_data
    try:
        sheet = copy.deepcopy(npc_data)
        notes = []
        features = sheet.get("classFeatures") if isinstance(sheet.get("classFeatures"), list) else []
        for name, pool in class_tables.use_pools_at(cls, level, sheet.get("abilities")).items():
            feature = class_tables.pool_feature(features, name)
            if feature is None:
                notes.append(f"{name}: no classFeatures entry of that name; its use pool is not set")
                continue
            usage = pool.usage()
            if feature.get("usage") != usage:
                notes.append(f"{feature['name']} usage -> {usage['current']}/{usage['max']} {usage['refreshOn']}")
                feature["usage"] = usage
        granted = {slot: n for slot, n in class_tables.slot_maxima(cls, level).items() if n}
        casting = sheet.get("spellcasting")
        if granted and isinstance(casting, dict):
            slots = casting.get("spellSlots") if isinstance(casting.get("spellSlots"), dict) else {}
            for slot, n in granted.items():
                if slots.get(slot) != {"current": n, "max": n}:
                    notes.append(f"spellSlots {slot} -> {n}/{n}")
                    slots[slot] = {"current": n, "max": n}
            casting["spellSlots"] = slots
        elif granted:
            notes.append(f"spell slots {granted} not set: the sheet has no spellcasting object")
    except Exception as e:
        warning(f"NPC class tables not applied to {npc_data.get('name')}: {e}", category="npc_creation")
        return npc_data
    for note in notes:
        info(f"NPC class tables ({sheet.get('name')}, SRD {sheet.get('class')} level {level}): {note}",
             category="npc_creation")
    return sheet

def save_json(file_name, data):
    """Atomically save JSON to file via safe_write_json.

    Routes through utils.file_operations.safe_write_json so a crash
    mid-write cannot corrupt the target file. Preserves the legacy
    (file_name, data) call order used by existing callers.
    """
    if safe_write_json(file_name, data):
        info(f"SUCCESS: NPC save ({file_name}) - PASS", category="npc_creation")
        return True
    print(f"{RED}Error saving to {file_name}: atomic write failed{RESET}")
    return False

def generate_npc(npc_name, schema, npc_race=None, npc_class=None, npc_level=None, npc_background=None,
                 npc_identity=None):
    system_prompt_text = load_prompt("prompts/generators/npc_builder_prompt.txt") # Renamed variable
    if not system_prompt_text:
        return None

    try:
        class_reference = _srd_class_reference(npc_class, npc_level)
    except Exception as e:
        # The reference is guidance; a failure to build it never stops generation.
        warning(f"NPC class reference not built for {npc_name}: {e}", category="npc_creation")
        class_reference = None
    class_reference_text = "" if class_reference is None else (
        "\n\nSRD 5.2.1 CLASS REFERENCE (the game's rules tables): use these class features, the levels that grant "
        "them, these numbers and these class spell lists; a class feature absent here is not part of that class "
        "at that level.\n"
        + json.dumps(class_reference))
    try:
        origin_reference = _srd_origin_reference(npc_race, npc_background)
    except Exception as e:
        # The reference is guidance; a failure to build it never stops generation.
        warning(f"NPC origin reference not built for {npc_name}: {e}", category="npc_creation")
        origin_reference = None
    origin_reference_text = "" if origin_reference is None else (
        "\n\nSRD 5.2.1 ORIGIN REFERENCE (the game's species and backgrounds): use these species, their traits and "
        "these backgrounds. A species grants no ability score increase: the background raises ability scores "
        "by background_ability_scores_rule, over the three abilities it lists.\n"
        + json.dumps(origin_reference))

    system_message = f"""You are an assistant that creates NPC schema JSON files from a master NPC schema template for a 5e game. Given an NPC name and optional details, create a JSON representation of the NPC's stats and abilities according to 5e rules following the NPC schema template exactly. Ensure your new NPC JSON adheres to the provided schema template. Do not include any additional properties or nested 'type' and 'value' fields. Return only the JSON content without any markdown formatting.

NAME HANDLING: The `name` field is exactly the NPC name you are given, including any title or role prefix (Scout, Guard, Captain, Ranger, etc.). Never add or remove a word. Examples:
- 'Ranger Thane' -> 'Ranger Thane'
- 'Scout Kira' -> 'Scout Kira'
- 'Guard Marcus' -> 'Guard Marcus'

EQUIPMENT REQUIREMENTS: Give the NPC a complete carried inventory, not five simultaneously held items. Include:
- Armor appropriate for class (studded leather for rogues, chain mail for fighters, etc.)
- Primary weapon (matching class proficiencies)
- Secondary/ranged weapon
- Shield (if class supports and build uses one)
- Class tools (thieves' tools, holy symbol, component pouch, etc.)
- At least 2 adventuring items (backpack, rope, rations, torches, etc.)

The equipped flag means currently held or worn, not merely owned. Keep spare weapons
in inventory with equipped=false. Use one primary weapon and an optional shield;
a two-handed primary weapon needs both hands and no shield. Keep all other weapons
stowed. Wear only one suit of armor and at most one shield. Do not invent code-owned
nqlEquipmentMigration receipts.

RACIAL TRAITS: Include every trait the NPC's species grants in the ORIGIN REFERENCE as a separate entry in the racialTraits array, named as there. A species grants no ability score increase.

Use the following rules information when creating the NPC:

{system_prompt_text}{class_reference_text}{origin_reference_text}

Adhere strictly to 5e rules and the provided schema."""

    # Create smarter level guidance
    level_guidance = npc_level if npc_level else "1-3 (appropriate for early adventuring parties)"
    # The NPC's authored record, when the adventure has one (#534); the retry
    # below is rebuilt from this first request, so every attempt carries it.
    identity_text = "" if not npc_identity else (
        "\n\nEstablished NPC from the adventure (keep race, class, appearance and personality consistent with "
        "it; it wins over any Race or Class above that contradicts it): " + json.dumps(npc_identity))
    
    prompt_messages = [ # Renamed variable
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Create an NPC named '{npc_name}' using 5e rules. Race: {npc_race or 'Any appropriate race'}, Class: {npc_class or 'Any appropriate class'}, Level: {level_guidance}, Background: {npc_background or 'Any appropriate background'}. Schema: {json.dumps(schema)}{identity_text}"}
    ]

    # Select model config per provider
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        npc_config = config.NPC_BUILD_GPT52_NONE
    elif MODEL_PROVIDER == "gemini":
        npc_config = config.NPC_BUILD_GEMINI_FLASH_LOW
    elif MODEL_PROVIDER == "lmstudio":
        npc_config = config.NPC_BUILD_LMSTUDIO
    else:  # legacy
        npc_config = config.NPC_BUILD_LEGACY

    # T035: force Gemini to emit the NPC character OBJECT, not DM narration. Reuse the
    # char schema already passed in (the same one used for jsonschema.validate below)
    # -- no second file load, no None risk. legacy/openai/lmstudio unaffected.
    _extra = {k: v for k, v in npc_config.items() if k != "model"}
    if MODEL_PROVIDER == "gemini":
        from model_config import convert_to_gemini_schema
        _extra["response_schema"] = convert_to_gemini_schema(schema)

    # CH-H1: Retry on JSON parse / schema validation failures. The AI
    # occasionally returns truncated or malformed JSON on the first try;
    # retrying recovers without failing the whole combat/module build.
    # Bound by model_config.MAX_VALIDATION_RETRIES (default 1 => 2 total
    # attempts). Network/API exceptions are NOT retried -- only parse and
    # validation errors. Defensive fallback to 1 if the constant is
    # missing or model_config import fails.
    try:
        import model_config as _mc
        _max_retries = getattr(_mc, "MAX_VALIDATION_RETRIES", 1)
    except Exception:
        _max_retries = 1

    last_json_err = None
    last_validation_err = None
    last_ai_response = None
    last_parsed_data = None

    # A failed attempt is retried with its own reply and the validation
    # error, rebuilt from the first request each time (#886).
    attempt_messages = prompt_messages
    for attempt in range(_max_retries + 1):
        try:
            response = capture_and_fanout("T035", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=attempt_messages,
                model=npc_config["model"],
                temperature=0.7,
                **_extra)

            ai_response = response.choices[0].message.content.strip()
            #print(f"{YELLOW}AI Response:{RESET}\n{ai_response}")

            # Remove markdown code block if present
            ai_response = re.sub(r'^```json\s*|\s*```$', '', ai_response, flags=re.MULTILINE)
            last_ai_response = ai_response

            try:
                npc_data = json.loads(ai_response)
                # Remove nested 'value' fields if they exist
                npc_data = remove_nested_values(npc_data)
                npc_data, _ = repair_required_ammunition_field(npc_data)
                last_parsed_data = npc_data
                validate(instance=npc_data, schema=schema)
                npc_data = _set_class_tables(npc_data)
                # A fresh AI draft is not an established player's loadout. Apply
                # the existing saved-order, shield-first capacity repair before
                # its first save so the first inventory delta can build a world.
                # Never run this on an existing target or a proposed equip action.
                npc_data.pop(RECEIPT_FIELD, None)
                changes = repair_initial_loadout(npc_data)
                if changes:
                    warning(
                        f"NPC initial loadout stowed {len(changes)} excess held items",
                        category="npc_creation",
                    )
                return npc_data
            except json.JSONDecodeError as e:
                last_json_err = e
                last_validation_err = None
                warning(
                    f"NPC build attempt {attempt + 1}/{_max_retries + 1} "
                    f"returned invalid JSON at line {e.lineno} column {e.colno}",
                    category="npc_creation",
                )
                attempt_messages = informed_retry_messages(
                    prompt_messages, ai_response, json_correction(e))
                continue
            except ValidationError as e:
                last_json_err = None
                last_validation_err = e
                issues = validation_issues(last_parsed_data, schema, e)
                warning(
                    f"NPC build attempt {attempt + 1}/{_max_retries + 1} "
                    f"failed schema validation at {issue_paths_for_log(issues)} "
                    f"({len(issues)} issue(s))",
                    category="npc_creation",
                )
                attempt_messages = informed_retry_messages(
                    prompt_messages, ai_response, schema_correction(last_parsed_data, schema, e))
                continue
        except (LiveProviderSuperseded, InvocationSupersededError):
            # A superseded live turn is not a generation failure; its own
            # handler ends the turn (#893).
            raise
        except Exception as e:
            # Network / API failures are not retried here -- preserve the
            # original outer-Exception contract.
            print(f"{RED}Error: Failed to generate NPC data. {str(e)}{RESET}")
            return None

    # All retries exhausted -- emit the original-style final error
    # messages so log scrapers and operators see the familiar output.
    if last_json_err is not None:
        print(f"{RED}Error: Invalid JSON in AI response. {str(last_json_err)}{RESET}")
        print(f"{YELLOW}Processed AI response:{RESET}\n{last_ai_response}")
    elif last_validation_err is not None:
        print(f"{RED}Error: Generated NPC data does not match schema. {str(last_validation_err)}{RESET}")
        print(f"{YELLOW}Problematic NPC data:{RESET}\n{json.dumps(last_parsed_data, indent=2)}")

    return None

def remove_nested_values(data):
    if isinstance(data, dict):
        # Check if it's a dict with only 'value' and possibly 'type' keys
        # This was a specific pattern you wanted to remove.
        # However, the more general approach from generate_npc was:
        # remove_nested_values(v['value'] if isinstance(v, dict) and 'value' in v else v)
        # Let's stick to the logic that was in generate_npc for this function.
        new_dict = {}
        for k, v in data.items():
            if isinstance(v, dict) and 'value' in v and len(v) == 1: # Simple {'value': ...} case
                new_dict[k] = remove_nested_values(v['value'])
            elif isinstance(v, dict) and 'value' in v and 'type' in v and len(v) == 2: # {'type':..., 'value':...} case
                 new_dict[k] = remove_nested_values(v['value'])
            else:
                new_dict[k] = remove_nested_values(v)
        return new_dict
    elif isinstance(data, list):
        return [remove_nested_values(item) for item in data]
    else:
        return data


# The DM pipeline passes literal placeholders when a value is not
# established in play ('unknown', 'none', 'n/a', ...). Treat every such
# placeholder exactly like empty: the builder infers a sensible default.
# Rejecting them crashed party recruitment mid-turn (Scout Kira, live).
UNSPECIFIED_ARGUMENTS = frozenset({"unknown", "none", "n/a", "na", "null", "tbd", "?"})


def _active_module_path_manager():
    """Resolve the same active-module snapshot historically used by main()."""
    try:
        from utils.encoding_utils import safe_json_load

        party_tracker = safe_json_load("party_tracker.json")
        current_module = (
            party_tracker.get("module", "").replace(" ", "_")
            if party_tracker
            else None
        )
        return ModulePathManager(current_module)
    except Exception:
        return ModulePathManager()


def _game_relative_character_path(path, npc_name):
    """The game-relative form of a lock record's absolute path (#884).

    A record inside this game's characters/ comes back as
    characters/<file>, the form every other character path has. One
    written under another working directory is returned unchanged, as it
    is loaded, and logged so the shape change is never silent.
    """
    if not os.path.isabs(path):
        return path
    if os.path.dirname(path) == os.path.abspath("characters"):
        return "characters/" + os.path.basename(path)
    warning(
        f"NPC_LOADING: lock record for {npc_name} points outside this "
        f"game's characters/ ({path})",
        category="npc_creation",
    )
    return path


def _drop_model_recoverable(sheet):
    """An ammunition row's count of recoverable shots is the engine's
    (core/nql/ammunition); a new sheet starts with none, as the update path
    drops it (stats.drop_model_totals) (#1458)."""
    dropped = []
    for row in sheet.get("ammunition") or []:
        if isinstance(row, dict) and "recoverable" in row:
            row.pop("recoverable")
            dropped.append(str(row.get("name")))
    if dropped:
        info(f"NPC_CREATION: dropped model-written recoverable from {', '.join(dropped)}",
             category="npc_creation")
    return dropped


def build_npc_file_with_path(
    npc_name,
    schema,
    npc_race=None,
    npc_class=None,
    npc_level=None,
    npc_background=None,
    path_manager=None,
    npc_identity=None,
):
    """Generate and save one NPC; return (sheet, path it was loaded or saved at), or None.
    npc_identity is the NPC's authored record, given to the model (#534).
    A name carrying a status word ("Wounded Ranger Gareth") is refused: an NPC
    takes its proper name, which its sheet keeps (#1119)."""
    from utils.status_words import status_word_refusal
    refusal = status_word_refusal(npc_name)
    if refusal:
        warning(f"NPC_CREATION: NPC not created: {refusal}", category="npc_creation")
        return None
    path_manager = path_manager or _active_module_path_manager()
    expected_name = str(npc_name or "").strip()
    logical_target = path_manager.get_character_unified_path(expected_name)

    with single_target_generation(logical_target) as transaction:
        candidates = [transaction.resolved_target, logical_target]
        for candidate in dict.fromkeys(path for path in candidates if path):
            existing = load_valid_generated_target(candidate, schema)
            if existing is not None:
                transaction.remember_target(candidate)
                info(
                    f"SUCCESS: NPC creation ({existing.get('name', expected_name)}) "
                    "- already exists",
                    category="npc_creation",
                )
                return existing, _game_relative_character_path(candidate, npc_name)

        generated = generate_npc(
            npc_name,
            schema,
            npc_race,
            npc_class,
            npc_level,
            npc_background,
            npc_identity=npc_identity,
        )
        if not generated:
            return None

        if expected_name and status_word_refusal(generated.get("name")):
            # The sheet keeps the name it was asked for, never a status word (#1119).
            warning(f"NPC_CREATION: generated name {generated.get('name')!r} replaced by "
                    f"{expected_name!r}: {status_word_refusal(generated.get('name'))}",
                    category="npc_creation")
            generated["name"] = expected_name
        clean_name = generated.get("name", expected_name)
        actual_target = path_manager.get_character_unified_path(clean_name)
        existing = load_valid_generated_target(actual_target, schema)
        if existing is not None:
            transaction.remember_target(actual_target)
            return existing, actual_target
        _drop_model_recoverable(generated)
        # Record the intended path before the atomic save. This closes the
        # post-replace/pre-marker crash window for cleaned NPC filenames.
        transaction.remember_target(actual_target)
        if not save_json(actual_target, generated):
            return None
        return generated, actual_target


def build_npc_file(
    npc_name,
    schema,
    npc_race=None,
    npc_class=None,
    npc_level=None,
    npc_background=None,
    path_manager=None,
    npc_identity=None,
):
    """Generate and save one NPC as a deduplicated target transaction."""
    built = build_npc_file_with_path(
        npc_name, schema, npc_race, npc_class, npc_level, npc_background,
        path_manager=path_manager, npc_identity=npc_identity,
    )
    return built[0] if built else None

def main():
    # Use argparse so we can accept --party-level alongside the existing
    # positional args. Positional args remain optional for backward
    # compatibility with any legacy callers.
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate a 5e NPC JSON file.")
    parser.add_argument("npc_name", help="Name of the NPC to generate.")
    parser.add_argument("race", nargs="?", default=None,
                        help="Optional race override.")
    parser.add_argument("npc_class", nargs="?", default=None,
                        help="Optional class override.")
    parser.add_argument("level", nargs="?", default=None,
                        help="Optional explicit NPC level (integer or "
                             "empty string).")
    parser.add_argument("background", nargs="?", default=None,
                        help="Optional background override.")
    parser.add_argument("--party-level", type=int, default=None,
                        help="Average party level. When supplied, overrides "
                             "the default 'level 1-3' guidance used for "
                             "NPC creation if no explicit level is given.")
    args = parser.parse_args()

    if args.level is not None and args.level.strip().lower() in UNSPECIFIED_ARGUMENTS:
        args.level = ""
    if args.npc_class is not None and args.npc_class.strip().lower() in UNSPECIFIED_ARGUMENTS:
        args.npc_class = ""
    if args.race is not None and args.race.strip().lower() in UNSPECIFIED_ARGUMENTS:
        args.race = ""

    npc_name_arg = args.npc_name
    npc_race_arg = args.race
    npc_class_arg = args.npc_class

    # Parse explicit positional level (preserve legacy validation).
    npc_level_arg = None
    if args.level is not None and args.level != "":
        if args.level.isdigit():
            try:
                npc_level_arg = int(args.level)
            except ValueError:
                print(f"{RED}Error: Level must be an integer.{RESET}")
                sys.exit(1)
        else:
            print(f"{RED}Error: Level must be an integer or empty if not specified.{RESET}")
            sys.exit(1)

    npc_background_arg = args.background

    # If no explicit positional level was supplied, use --party-level as
    # the level guidance so the NPC is scaled to the party.
    if npc_level_arg is None and args.party_level is not None:
        npc_level_arg = args.party_level

    debug(f"INPUT_PROCESSING: Received arguments - Name: {npc_name_arg}, Race: {npc_race_arg}, Class: {npc_class_arg}, Level: {npc_level_arg}, Background: {npc_background_arg}", category="npc_creation")

    npc_schema_data = load_schema("schemas/char_schema.json") # Use unified character schema
    if not npc_schema_data:
        sys.exit(1)

    generated_npc_data = build_npc_file(
        npc_name_arg,
        npc_schema_data,
        npc_race_arg,
        npc_class_arg,
        npc_level_arg,
        npc_background_arg,
    )
    if generated_npc_data:
        clean_npc_name = generated_npc_data.get("name", npc_name_arg)
        info(f"SUCCESS: NPC creation ({clean_npc_name}) - PASS", category="npc_creation")
    else:
        error(f"FAILURE: NPC creation ({npc_name_arg}) - FAIL", category="npc_creation")
        sys.exit(1)

if __name__ == "__main__":
    main()
