# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""One-time repair of live effect records saved before their spell's typed modifier form (#1442).

A Mage Armor cast before #1421 was saved with ``modifiers: []``: the classifier
had no form for "base AC becomes 13 + Dexterity", so the engine never derived
it and the sheet kept its unarmored AC. At character load, a live record of a
spell that ``data/srd_spell_effect_rules.json`` types is given those typed
modifiers, with a receipt. Only the record's typed name, ids, modifiers and
expiry are read; its description and change note never are (D-KW-18), and no
number is computed here (D-KW-8).

A record already past its expiry is left for the effect clock to end. A record
of such a spell whose stored modifiers are not its typed rule is kept as saved
and reported, never overwritten. A record with no expiry is never given a rule
(the clock could not end it), and a spell whose typed form needs a choice the
record never kept (Guidance's skill) is never filled: both are reported once,
with a receipt naming the gap (#1446).
"""
from typing import Any, Dict, List, Optional, Tuple

from core.ai import srd_spell_effect_rules
from core.nql import effects as nql_effects, genesis

VERSION = "srd-effect-rules-v1"
RECEIPT_FIELD = "ruleMigration"


def _expires_tick(effect: Dict[str, Any]) -> Optional[int]:
    tick = effect.get(genesis.EFFECT_EXPIRES_TICK)
    return tick if type(tick) is int else nql_effects._expires_tick(effect)


def migrate(sheet: Dict[str, Any], now_tick: Optional[int]) -> Tuple[List[str], List[str]]:
    """Mutate only un-migrated live records with no modifiers; return (recorded repairs, gaps).

    ``now_tick`` is the world clock's scalar (None when it cannot be read: a record
    with an expiry is then not migrated, and that is a gap).
    """
    changes: List[str] = []
    gaps: List[str] = []
    effects = sheet.get("temporaryEffects")
    if not isinstance(effects, list):
        return changes, gaps
    hero = sheet.get("name") or "character"
    for index, effect in enumerate(effects):
        if not (isinstance(effect, dict) and isinstance(effect.get("effectId"), str) and effect["effectId"].strip()
                and isinstance(effect.get("authoredBy"), str) and effect["authoredBy"].strip()):
            continue
        if effect.get(RECEIPT_FIELD):
            continue
        status, key, rule = srd_spell_effect_rules.lookup(effect.get("name"))
        if status not in ("recorded", "needs_choice"):
            continue
        stored = effect.get("modifiers")
        if status == "needs_choice":
            if stored != []:
                continue  # a typed record names its own choice (Guidance: its skill die)
        elif stored == rule:
            continue
        elif stored != []:
            gaps.append(f"{hero}: {effect.get('name')} was saved before its typed rule; its stored modifiers "
                        f"are kept and its numbers may be wrong")
            continue
        expires = _expires_tick(effect)
        if expires is not None and now_tick is None:
            gaps.append(f"{hero}: {effect.get('name')} was saved before its typed rule and the world clock "
                        f"could not be read; left as saved")
            continue
        if expires is not None and expires <= now_tick:
            continue  # already over: the effect clock ends it as saved
        if status == "needs_choice":
            # #1446: the choice its typed form needs was never kept; reported once, never guessed.
            effect[RECEIPT_FIELD] = {"version": VERSION, "spell": key, "gap": rule}
            changes.append(f"temporaryEffects[{index}].{RECEIPT_FIELD}=gap:{rule}:{key}")
            gaps.append(f"{hero}: {effect.get('name')} was saved before its typed die and its chosen {rule} "
                        f"was not recorded; it adds nothing until it is cast again")
            continue
        if expires is None:
            # #1446: a typed rule on a record the effect clock cannot end would be permanent.
            effect[RECEIPT_FIELD] = {"version": VERSION, "spell": key, "gap": "no_expiry"}
            changes.append(f"temporaryEffects[{index}].{RECEIPT_FIELD}=gap:no_expiry:{key}")
            gaps.append(f"{hero}: {effect.get('name')} was saved before its typed rule with no duration; it is "
                        f"left as saved and adds nothing until it is cast again")
            continue
        effect["modifiers"] = rule
        effect[RECEIPT_FIELD] = {"version": VERSION, "spell": key}
        changes.append(f"temporaryEffects[{index}].modifiers=srd_rule:{key}")
    return changes, gaps
