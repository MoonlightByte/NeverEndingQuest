# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Typed damage riders (#1666, D-1666-1 A).

data/srd_damage_riders.json types the spells whose marked target takes an extra
die from the caster's hits. Code stamps that rider on the effect; the model
never writes it. A spell is found by the repository's canonical key.
"""

import json
from functools import lru_cache
from pathlib import Path

from core.effects.model import DAMAGE_RIDER_ON, normalize_damage_rider

TABLE = Path(__file__).resolve().parents[2] / "data" / "srd_damage_riders.json"


@lru_cache(maxsize=1)
def _table():
    with open(TABLE, encoding="utf-8") as handle:
        riders = json.load(handle)["riders"]
    return {
        key: normalize_damage_rider({"die": entry["die"], "damageType": entry["damageType"],
                                     "on": DAMAGE_RIDER_ON, "label": entry["label"]})
        for key, entry in riders.items()
    }


def rider_for(intent, effect):
    """The rider an effect op carries, or None: the cast's typed ``ability``,
    then its ``spellName``, then the effect's own name (T096 words that one
    freely), each looked up by the repository's canonical key."""
    from core.ai.srd_reference import load_srd_reference_index

    names = []
    if isinstance(intent, dict) and intent.get("action") == "cast":
        names += [intent.get("ability"), intent.get("spellName")]
    if isinstance(effect, dict):
        names.append(effect.get("name"))
    index = load_srd_reference_index()
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        reference = index.reference(name)
        if reference and reference.get("kind") == "spell" and reference.get("key") in _table():
            return dict(_table()[reference["key"]])
    return None
