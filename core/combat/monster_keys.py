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
   of the bestiary keys it was shown;
3. else a new key that no name can select: the stat block is generated from
   the DM's name and flavor, so the DM can always bring a new creature.

Bestiary keys are the global compendium's keys (data/bestiary). A minted key
is never one of them, so the list the DM sees never grows with opaque keys; a
minted creature is reached again through the occupant created for it.
"""

import json
import os
import uuid

COMPENDIUM = os.path.join("data", "bestiary", "monster_compendium.json")


def mint_key():
    """A new monster key; never the stem of an existing stat block, and its
    own file name (normalize_character_name leaves it unchanged)."""
    return "new_%s" % uuid.uuid4().hex


def bestiary():
    """{key: name} for the keys the DM may name: the compendium's entries."""
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


def bestiary_keys():
    """The keys the DM may name, sorted."""
    return sorted(bestiary())


def monster_key(slot, encounter_data, place_occupants, listed):
    """(key, source, stock name) for one createEncounter monster slot
    ("monster:N").

    ``place_occupants`` maps the occupant IDs at the fight's place to their
    engine records; ``listed`` is bestiary(). source is "occupant", "listed"
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
