# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Read-only game state snapshots for headless mode.

Snapshots are built ONLY from the on-disk state files (party_tracker.json,
characters/<name>.json, module_plot.json, encounter files) -- never from
scraped narration text. Every read is tolerant: a missing or malformed file
yields None for that section rather than an exception, because snapshots
are taken while the engine owns the files.
"""

import json
import os


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return None


def _mtime(path):
    try:
        return round(os.path.getmtime(path), 3)
    except OSError:
        return None


def _normalize_name(name):
    try:
        from updates.update_character_info import normalize_character_name
        return normalize_character_name(name)
    except Exception:
        return str(name).strip().lower().replace(" ", "_")


def build_snapshot():
    """Build a state snapshot from the current working directory's game files."""
    tracker = _load_json("party_tracker.json")
    snapshot = {
        "party_tracker": None,
        "player": None,
        "location": None,
        "plot": None,
        "combat": None,
        "files": {
            "party_tracker": _mtime("party_tracker.json"),
        },
    }
    if not isinstance(tracker, dict):
        return snapshot

    world = tracker.get("worldConditions") or {}
    snapshot["party_tracker"] = {
        "module": tracker.get("module"),
        "partyMembers": tracker.get("partyMembers", []),
        "partyNPCs": tracker.get("partyNPCs", []),
        "time": world.get("time"),
        "day": world.get("day"),
        "month": world.get("month"),
        "year": world.get("year"),
    }
    snapshot["location"] = {
        "id": world.get("currentLocationId"),
        "name": world.get("currentLocation"),
        "area_id": world.get("currentAreaId"),
        "area_name": world.get("currentArea"),
    }

    members = tracker.get("partyMembers") or []
    if members:
        char_path = os.path.join(
            "characters", _normalize_name(members[0]) + ".json")
        character = _load_json(char_path)
        snapshot["files"]["character"] = _mtime(char_path)
        if isinstance(character, dict):
            try:
                from core.effects.effective import effective_sheet

                character = effective_sheet(character)
            except Exception:
                pass
            snapshot["player"] = {
                "name": character.get("name"),
                "class": character.get("class"),
                "race": character.get("race"),
                "level": character.get("level"),
                "hp": character.get("hitPoints"),
                "max_hp": character.get("maxHitPoints"),
                "xp": character.get("experience_points"),
                "next_level_xp": character.get("exp_required_for_next_level"),
                "armor_class": character.get("armorClass"),
                "status": character.get("status"),
                "condition": character.get("condition"),
                "currency": character.get("currency"),
            }

    module = (tracker.get("module") or "").strip()
    if module:
        plot_path = os.path.join("modules", module, "module_plot.json")
        plot = _load_json(plot_path)
        snapshot["files"]["module_plot"] = _mtime(plot_path)
        if isinstance(plot, dict):
            snapshot["plot"] = [
                {
                    "id": point.get("id"),
                    "title": point.get("title"),
                    "status": point.get("status"),
                }
                for point in plot.get("plotPoints", [])
                if isinstance(point, dict)
            ]

    encounter_id = (world.get("activeCombatEncounter") or "").strip()
    if encounter_id:
        encounter_path = os.path.join(
            "modules", "encounters", "encounter_%s.json" % encounter_id)
        encounter = _load_json(encounter_path)
        combat = {"active": True, "encounter_id": encounter_id}
        if isinstance(encounter, dict):
            for key in ("current_round", "combat_round", "round"):
                if key in encounter:
                    combat["round"] = encounter.get(key)
                    break
        snapshot["combat"] = combat

    return snapshot
