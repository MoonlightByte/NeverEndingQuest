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
modifier, at least 1, refusing a spend the pool cannot pay (#840, D-KWA-7). A die
certain to heal nothing is never rolled: each die heals at least 1, so a
character spends at most the hit points they are missing in dice, and the dice
named beyond that are refused before rolling with a typed record the DM is told
about (#1239). The
player's own dice take the faces the player typed, or the engine's draw; every
other character's dice are the engine's. Any other extra healing the table
narrates on a short rest is an ordinary updateCharacterInfo change. Rest-bound
temporary effects are cleared by the effects lifecycle after the sheets are
written. All sheets are written together or none is.
"""
import json
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


def _sheets_with_id(sheets: List[Dict[str, Any]], character_id: Any) -> List[Dict[str, Any]]:
    """The resting sheets whose engine id (``genesis.character_id``, the id Party
    stats shows the DM) is ``character_id``: a typed id compare, never a name
    read (D-KW-12)."""
    from core.nql import genesis

    return [s for s in sheets if genesis.character_id(s) == character_id]


def _party_root(sheets: List[Dict[str, Any]], party: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The player's resting sheet: the sheet whose engine id is the id of the
    party tracker's first member: two engine ids from the engine's own key
    derivation (genesis.character_id) over code-written game files, an id
    compare, never a read of model or player text."""
    from core.nql import genesis

    names = list(party.get("partyMembers") or [])
    if not names:
        return None
    found = _sheets_with_id(sheets, genesis.character_id({"name": names[0]}))
    return found[0] if len(found) == 1 else None


def _refusal(name: str, reason: str, hit_points: int, maximum: int, dice: int, can_heal: int) -> str:
    """The typed record of hit dice refused before rolling (#1239, D-1239-3 B):
    the model words it; no code reads it back. It says nothing of what was then
    spent: the engine may still refuse the dice that can heal, and the Rest line
    and receipt say what was."""
    return "hit dice refused before rolling: " + json.dumps({
        "character": name, "reason": reason, "hitPoints": hit_points, "maxHitPoints": maximum,
        "dice": dice, "diceThatCanHeal": can_heal})


def hit_dice_spends(sheets: List[Dict[str, Any]],
                    hit_dice: Any) -> Tuple[Optional[Dict[str, int]], Dict[str, str], str]:
    """The hit dice a short rest spends, keyed by sheet name: ({name: count}, refused, "") or (None, {}, why).

    ``hit_dice`` maps a resting character's engine id (``char:...``, shown to the
    DM in Party stats) to how many dice they spend (D-KW-12).
    A character needs a known class and at least 1 hit point to spend them.
    How many dice are left is the engine's pool; nothing is rolled here.
    A character spends no more dice than the hit points they are missing, since
    each die heals at least 1 (#1239, D-1239-1 B). The dice named beyond that
    are refused and the rest goes ahead without them (D-1239-2 B): the
    character offers only the dice that can heal (D-1239-5), none at full hit
    points, and ``refused`` maps their name to the typed record.
    """
    if not hit_dice:
        return {}, {}, ""
    if not isinstance(hit_dice, dict):
        return None, {}, ('hitDice must key each character by their id from Party stats and give how many dice '
                          'they spend, e.g. {"char:bryn-ashwood": 1}')
    from core.nql import genesis

    resting = ", ".join(f"{genesis.character_id(s)} ({s.get('name')})" for s in sheets)
    spends: Dict[str, int] = {}
    refused: Dict[str, str] = {}
    for key, count in hit_dice.items():
        found = _sheets_with_id(sheets, key)
        if len(found) != 1:
            return None, {}, (f"no single resting party character has the id {key!r}; key each character by "
                              f"their id from Party stats: {resting}")
        sheet = found[0]
        name = str(sheet.get("name"))
        if type(count) is not int or count < 1:
            return None, {}, f"{name}'s hit dice must be a whole number of at least 1, not {count!r}"
        if leveling_tables.class_key(sheet) is None:
            return None, {}, f"{name}'s class {sheet.get('class')!r} has no known hit die"
        if type(sheet.get("hitPoints")) is not int:
            return None, {}, f"{name}'s sheet has no hit points to heal"
        if sheet["hitPoints"] < 1:
            return None, {}, f"{name} is at 0 hit points and cannot spend hit dice until they have at least 1"
        maximum = sheet.get("maxHitPoints")
        if type(maximum) is int and maximum >= 1:
            can_heal = max(0, maximum - sheet["hitPoints"])
            if count > can_heal:
                refused[name] = _refusal(name, "full_hit_points" if can_heal == 0 else "more_dice_than_missing",
                                         sheet["hitPoints"], maximum, count, can_heal)
                count = can_heal
        if count:
            spends[name] = count
    return spends, refused, ""


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
    so the player rolls them; None otherwise (no prompt: the engine rolls or refuses the rest). The count
    is the dice that can heal (#1239): none at full hit points, so no prompt."""
    from core.managers.effects_runtime import _party_sheets
    from core.nql import genesis

    if not party.get("partyMembers") or not hit_dice:
        return None
    sheets, _paths = _party_sheets(party)
    spends, _refused, _why = hit_dice_spends(list(sheets.values()), hit_dice)
    player = _party_root(list(sheets.values()), party)
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

    answers: List[Any] = []
    while len(answers) < count:
        which = f" ({len(answers) + 1} of {count})" if count > 1 else ""
        try:
            text = read(f"{ROLL_TAG} Hit die for {name}{which}: roll 1d{die} and type the result (e.g. {min(4, die)}), "
                        "or press Enter and the game rolls: ")
        except EOFError:
            text = ""
        text = (text or "").strip()
        if not text:
            answers.append("engine")
        elif text.isdigit() and 1 <= int(text) <= die:
            answers.append(int(text))
        else:
            print(f"Type one whole number between 1 and {die}, or press Enter to let the game roll.")
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
    spent: Dict[str, Any] = {}

    def build(sheets, location):
        spends, refused, why = hit_dice_spends(sheets, hit_dice)
        if spends is None:
            return nql_resources.RestOutcome(False, reason=why)
        spent["refused"] = refused
        root = _party_root(sheets, party)
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
    refused = dict(outcome.refused)
    for name, record in spent["refused"].items():
        # #1239: the dice beyond those that can heal; the rest went ahead without them.
        message += f" {name}'s hit dice beyond those that can heal were not spent ({record})."
        refused[name] = f"{refused[name]}; {record}" if name in refused else record
    from core.managers.effects_runtime import process_effect_lifecycle

    note = process_effect_lifecycle(conversation_history, rest_kind=f"{kind}_rest")
    info(f"REST: {message}", category="character_updates")
    return {"success": True, "message": message, "effects_note": note, "restored": outcome.restored,
            "hit_dice_receipts": receipts, "hit_dice_refused": refused}
