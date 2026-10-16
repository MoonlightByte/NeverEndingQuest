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
many each character spends and the engine rolls them (7b-host): a hit-die Ability
spends one die from the pool and heals the class die plus the Constitution
modifier, at least 1, refusing a spend the pool cannot pay (#840, D-KWA-7). The
player's own dice take the faces the player typed, or the engine's draw; every
other character's dice are the engine's. Any other extra healing the table
narrates on a short rest is an ordinary updateCharacterInfo change. Rest-bound
temporary effects are cleared by the effects lifecycle after the sheets are
written. All sheets are written together or none is.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.leveling import tables as leveling_tables
from core.managers.currency_transfer import _run
from core.nql import game_clock
from core.nql import resources as nql_resources
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import info


def _party_paths(party: Dict[str, Any]) -> List[str]:
    from core.managers.effects_runtime import _party_sheets

    _sheets, paths = _party_sheets(party)
    return sorted(set(paths.values()))


def _match_sheet(sheets: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    """The resting sheet whose full name is ``name`` (whole value, case ignored).
    Never a first name or other part of a name (#855)."""
    wanted = name.strip().casefold()
    return next((s for s in sheets if str(s.get("name") or "").strip().casefold() == wanted), None)


def hit_dice_spends(sheets: List[Dict[str, Any]], hit_dice: Any) -> Tuple[Optional[Dict[str, int]], str]:
    """The hit dice a short rest spends by full sheet name: ({name: count}, "") or (None, why).

    ``hit_dice`` maps a resting character's name to how many dice they spend.
    A character needs a known class and at least 1 hit point to spend them.
    How many dice are left is the engine's pool; nothing is rolled here.
    """
    if not hit_dice:
        return {}, ""
    if not isinstance(hit_dice, dict):
        return None, 'hitDice must name each character and how many dice they spend, e.g. {"Bryn Ashwood": 1}'
    spends: Dict[str, int] = {}
    for raw_name, count in hit_dice.items():
        sheet = _match_sheet(sheets, str(raw_name))
        if sheet is None:
            resting = ", ".join(repr(str(s.get("name"))) for s in sheets)
            return None, f"no resting party character is named {raw_name!r}; name each by full name: {resting}"
        name = str(sheet.get("name"))
        if name in spends:
            return None, f"{name} is named twice in hitDice"
        if type(count) is not int or count < 1:
            return None, f"{name}'s hit dice must be a whole number of at least 1, not {count!r}"
        if leveling_tables.class_key(sheet) is None:
            return None, f"{name}'s class {sheet.get('class')!r} has no known hit die"
        if type(sheet.get("hitPoints")) is not int:
            return None, f"{name}'s sheet has no hit points to heal"
        if sheet["hitPoints"] < 1:
            return None, f"{name} is at 0 hit points and cannot spend hit dice until they have at least 1"
        spends[name] = count
    return spends, ""


def hit_dice_receipt(name: str, rolls: List[Dict[str, Any]], before: Any, after: Any, maximum: Any,
                     left: Any = None) -> str:
    """The player-facing line for one character's spent hit dice, from the engine's roll records."""
    die = rolls[0].get("sides")
    modifier = rolls[0].get("bonus")
    sign = f"+{modifier}" if type(modifier) is int and modifier >= 0 else str(modifier)
    dice = "die" if len(rolls) == 1 else "dice"
    rolled = ", ".join(", ".join(str(face) for face in roll.get("faces") or [])
                       + (" (the game rolled)" if roll.get("engine_drawn") or roll.get("source") == "agent" else "")
                       for roll in rolls)
    gained = after - before if type(after) is int and type(before) is int else sum(r["actual"] for r in rolls)
    line = (f"{name} spends {len(rolls)} hit {dice} (d{die} {sign} Constitution each, at least 1): "
            f"rolled {rolled}, regains {gained} hit point{'' if gained == 1 else 's'}")
    if type(after) is int and type(maximum) is int:
        line += f" ({after}/{maximum})"
    if type(left) is int:
        line += f"; d{die} hit dice left: {left}"
    return line + "."


def player_hit_dice(party: Dict[str, Any], hit_dice: Any) -> Optional[Tuple[str, int, int]]:
    """(player's full name, die, count) when the rest spends the player's hit dice and their pool can pay,
    so the player rolls them; None otherwise (no prompt: the engine rolls or refuses the rest)."""
    from core.managers.effects_runtime import _party_sheets
    from core.nql import genesis

    names = list(party.get("partyMembers") or [])
    if not names or not hit_dice:
        return None
    sheets, _paths = _party_sheets(party)
    spends, _why = hit_dice_spends(list(sheets.values()), hit_dice)
    player = _match_sheet(list(sheets.values()), str(names[0]))
    if not spends or player is None or str(player.get("name")) not in spends:
        return None
    die = genesis.hit_die(player)
    left = {rid: cur for rid, cur, _ in genesis.pool_resources(player, [])}.get(genesis.hit_dice_resource_id(die))
    count = spends[str(player.get("name"))]
    if type(left) is not int or left < count:
        return None
    return str(player.get("name")), die, count


def ask_hit_die_faces(name: str, die: int, count: int, read: Callable[[str], str]) -> List[Any]:
    """Ask the player for each hit die: the face they rolled, or Enter to let the engine roll it ("engine")."""
    from core.managers.checks_runtime import ROLL_TAG
    from core.managers.combat_orchestrator import _lets_the_game_roll

    answers: List[Any] = []
    again = ""
    while len(answers) < count:
        which = f" ({len(answers) + 1} of {count})" if count > 1 else ""
        try:
            text = read(f"{again}{ROLL_TAG} Hit die for {name}{which}: roll 1d{die} and type the result (e.g. {min(4, die)}), "
                        "or type roll and the game rolls: ")
        except EOFError:
            text = ""
        text = (text or "").strip()
        again = ""
        if not text or _lets_the_game_roll(text):
            answers.append("engine")
        elif text.isdigit() and 1 <= int(text) <= die:
            answers.append(int(text))
        else:
            again = f"Type one whole number between 1 and {die}, or type roll and the game rolls. "
    return answers


def execute_rest(rest_type: Any, party_tracker: Optional[Dict[str, Any]] = None,
                 conversation_history: Optional[list] = None, hit_dice: Any = None,
                 faces: Optional[Dict[str, List[Any]]] = None) -> Dict[str, Any]:
    """``faces``: the player's hit dice by full name, one entry per die: the face the player rolled, or
    "engine" to let the engine roll it. Without it the engine rolls every die."""
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
    player = str((party.get("partyMembers") or [""])[0])
    spent: Dict[str, Any] = {}

    def build(sheets, location):
        spends, why = hit_dice_spends(sheets, hit_dice)
        if spends is None:
            return nql_resources.RestOutcome(False, reason=why)
        root = _match_sheet(sheets, player)
        root_name = str(root.get("name")) if root else None
        spent["before"] = {str(s.get("name")): s.get("hitPoints") for s in sheets}
        return nql_resources.rest(sheets, kind, location=location, hit_dice=spends, root=root_name,
                                  faces=(faces or {}).get(root_name) if root_name in spends else None,
                                  clock_tick=game_clock.declared_tick(party))

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
    for name in dict.fromkeys(roll["name"] for roll in outcome.rolls):
        rolls = [roll for roll in outcome.rolls if roll["name"] == name]
        sheet = after.get(name) or {}
        receipts.append(hit_dice_receipt(name, rolls, spent["before"].get(name), sheet.get("hitPoints"),
                                         sheet.get("maxHitPoints"),
                                         (sheet.get("hitDice") or {}).get(f"d{rolls[0].get('sides')}")))
    if receipts:
        message += " Hit dice rolled by the rules engine (the player sees this receipt): " + " ".join(receipts)
    for name, why in outcome.refused.items():
        message += f" {name}'s hit dice were not spent ({why}); {name}'s hit points and hit dice are unchanged."
    from core.managers.effects_runtime import process_effect_lifecycle

    note = process_effect_lifecycle(conversation_history, rest_kind=f"{kind}_rest")
    info(f"REST: {message}", category="character_updates")
    return {"success": True, "message": message, "effects_note": note, "restored": outcome.restored,
            "hit_dice_receipts": receipts, "hit_dice_refused": dict(outcome.refused)}
