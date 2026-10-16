# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""A short or long rest for the whole party (the rest action).

The engine refills every pool the rest recovers on every party sheet in one
request (core/nql/resources.rest): a long rest restores hit points, spell slots
and every feature use pool; a short rest restores the pools tagged shortRest
and, for a pact caster, spell slots. Hit dice are an engine pool per character
(``hitdice:d<N>``, maximum = level, the sheet's ``hitDice``; a long rest restores
all of them). A short rest may spend them: the rest action's ``hitDice`` names how
many each character spends, code rolls them here (the class hit die plus the
Constitution modifier per die, at least 1 each) and the engine spends them from
the pool and heals the total in the same request, refusing a spend the pool
cannot pay (#840, D-KWA-7). Any other extra
healing the table narrates on a short rest is an ordinary updateCharacterInfo
change. Rest-bound temporary effects are cleared by the effects lifecycle after
the sheets are written. All sheets are written together or none is.
"""
import random
from typing import Any, Dict, List, Optional, Tuple

from core.leveling import tables as leveling_tables
from core.managers.currency_transfer import _run
from core.nql import resources as nql_resources
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import info

_ROLLER = random.SystemRandom()


def _party_paths(party: Dict[str, Any]) -> List[str]:
    from core.managers.effects_runtime import _party_sheets

    _sheets, paths = _party_sheets(party)
    return sorted(set(paths.values()))


def _match_sheet(sheets: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    """The resting sheet whose full name is ``name`` (whole value, case ignored).
    Never a first name or other part of a name (#855)."""
    wanted = name.strip().casefold()
    return next((s for s in sheets if str(s.get("name") or "").strip().casefold() == wanted), None)


def roll_hit_dice(sheets: List[Dict[str, Any]], hit_dice: Any,
                  roller: Any = None) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """Roll the hit dice a short rest spends: ([{name, die, count, modifier, rolls, total}], "") or (None, why).

    ``hit_dice`` maps a resting character's name to how many dice they spend.
    Each die is the class hit die plus the Constitution modifier, at least 1;
    a character needs at least 1 hit point to rest. How many dice are left is
    the engine's pool (core/nql/resources.rest). Nothing is applied here.
    """
    if not hit_dice:
        return [], ""
    if not isinstance(hit_dice, dict):
        return None, 'hitDice must name each character and how many dice they spend, e.g. {"Bryn Ashwood": 1}'
    roller = roller or _ROLLER
    spends = []
    seen = set()
    for raw_name, count in hit_dice.items():
        sheet = _match_sheet(sheets, str(raw_name))
        if sheet is None:
            resting = ", ".join(repr(str(s.get("name"))) for s in sheets)
            return None, f"no resting party character is named {raw_name!r}; name each by full name: {resting}"
        name = str(sheet.get("name"))
        if name in seen:
            return None, f"{name} is named twice in hitDice"
        seen.add(name)
        if type(count) is not int or count < 1:
            return None, f"{name}'s hit dice must be a whole number of at least 1, not {count!r}"
        cls = leveling_tables.class_key(sheet)
        if cls is None:
            return None, f"{name}'s class {sheet.get('class')!r} has no known hit die"
        if type(sheet.get("hitPoints")) is not int:
            return None, f"{name}'s sheet has no hit points to heal"
        if sheet["hitPoints"] < 1:
            return None, f"{name} is at 0 hit points and cannot spend hit dice until they have at least 1"
        die = leveling_tables.hit_die(cls)
        modifier = leveling_tables.modifier((sheet.get("abilities") or {}).get("constitution"))
        rolls = [roller.randint(1, die) for _ in range(count)]
        total = sum(max(1, r + modifier) for r in rolls)
        spends.append({"name": name, "die": die, "count": count, "modifier": modifier,
                       "rolls": rolls, "total": total})
    return spends, ""


def hit_dice_receipt(spend: Dict[str, Any], before: Any, after: Any, maximum: Any, left: Any = None) -> str:
    """The player-facing line for one character's spent hit dice."""
    modifier = spend["modifier"]
    sign = f"+{modifier}" if modifier >= 0 else str(modifier)
    dice = "die" if spend["count"] == 1 else "dice"
    rolled = ", ".join(str(r) for r in spend["rolls"])
    gained = after - before if type(after) is int and type(before) is int else spend["total"]
    line = (f"{spend['name']} spends {spend['count']} hit {dice} (d{spend['die']} {sign} Constitution each): "
            f"rolled {rolled}, regains {gained} hit point{'' if gained == 1 else 's'}")
    if type(after) is int and type(maximum) is int:
        line += f" ({after}/{maximum})"
    if type(left) is int:
        line += f"; d{spend['die']} hit dice left: {left}"
    return line + "."


def execute_rest(rest_type: Any, party_tracker: Optional[Dict[str, Any]] = None,
                 conversation_history: Optional[list] = None, hit_dice: Any = None) -> Dict[str, Any]:
    kind = str(rest_type or "").strip().lower()
    if kind not in nql_resources.REST_KINDS:
        return {"success": False, "error": f"rest needs restType short or long, not {rest_type!r}"}
    if hit_dice and kind != "short":
        return {"success": False, "error": "hit dice are spent on a short rest; a long rest already restores "
                                           "every hit point, so leave hitDice out"}
    party = party_tracker or safe_json_load("party_tracker.json") or {}
    paths = _party_paths(party)
    if not paths:
        return {"success": False, "error": "no party character sheet could be found"}
    spent: Dict[str, Any] = {}

    def build(sheets, location):
        spends, why = roll_hit_dice(sheets, hit_dice)
        if spends is None:
            return nql_resources.RestOutcome(False, reason=why)
        spent["spends"] = spends
        spent["before"] = {str(s.get("name")): s.get("hitPoints") for s in sheets}
        return nql_resources.rest(sheets, kind, location=location,
                                  hp_heals={s["name"]: s["total"] for s in spends},
                                  hit_dice={s["name"]: s["count"] for s in spends})

    result = _run(paths, build, party)
    if not result.get("success"):
        return result
    outcome = result["outcome"]
    parts = []
    for name, labels in outcome.restored.items():
        parts.append(f"{name}: {', '.join(labels) if labels else 'nothing to recover'}")
    message = f"{kind} rest applied by the rules engine. " + "; ".join(parts) + "."
    receipts = []
    after = {str(s.get("name")): s for s in outcome.sheets}
    for spend in spent.get("spends") or []:
        sheet = after.get(spend["name"]) or {}
        receipts.append(hit_dice_receipt(spend, spent["before"].get(spend["name"]),
                                         sheet.get("hitPoints"), sheet.get("maxHitPoints"),
                                         (sheet.get("hitDice") or {}).get(f"d{spend['die']}")))
    if receipts:
        message += " Hit dice rolled by code (the player sees this receipt): " + " ".join(receipts)
    from core.managers.effects_runtime import process_effect_lifecycle

    note = process_effect_lifecycle(conversation_history, rest_kind=f"{kind}_rest")
    info(f"REST: {message}", category="character_updates")
    return {"success": True, "message": message, "effects_note": note, "restored": outcome.restored,
            "hit_dice_receipts": receipts}
