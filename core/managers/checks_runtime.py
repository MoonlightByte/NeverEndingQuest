"""rollCheck staging, the roll prompt, and the DM Note line (C2a).

A submitted roll is player input: a check the DM asks for in
turn N is scored before the DM's turn N+1 begins, and its result line is in
that turn's DM Note. The player's dice are typed at a numbers-only roll
prompt (blank = the game rolls); the DM never converts words into dice.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from core.managers import checks_state, roll_prompt
from core.managers.effects_runtime import _resolve_character
from core.nql import checks
from utils.enhanced_logger import info, warning

ROLL_TAG = "[ROLL]"
_NUMBERS = re.compile(r"^\s*(\d{1,2})(?:[\s,]+(\d{1,2}))?\s*$")


def _is_player(role: Optional[str]) -> bool:
    return str(role or "").lower() == "player"


def stage_roll_check(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a rollCheck action and either resolve it now or hold it for the roll prompt."""
    name = parameters.get("characterName")
    if not isinstance(name, str) or not name.strip():
        return {"error": "rollCheck requires characterName."}
    stat = checks.stat_id(parameters.get("stat"))
    if stat is None:
        # Fail forward: the turn goes on and the DM reads why next turn.
        line = (f"{name} check {parameters.get('stat')!r}: not resolved (stat must be exactly one of "
                f"{', '.join(checks.STATS)}; issue rollCheck again)")
        checks_state.add_result(line)
        warning(f"CHECK: {line}", category="character_updates")
        return {"resolved": line}
    dc = parameters.get("dc")
    if dc is not None and (type(dc) is not int or dc < 1):
        return {"error": "rollCheck: dc must be a positive whole number or omitted."}
    mode = parameters.get("mode")
    if mode is not None and mode not in ("normal",) + checks.MODES:
        return {"error": "rollCheck: mode must be advantage, disadvantage or omitted."}
    if mode == "normal":
        mode = None
    roller = parameters.get("roller") or "player"
    if roller not in ("player", "engine"):
        return {"error": "rollCheck: roller must be player or engine."}
    resolved, role, _path, sheet = _resolve_character(name)
    reason = str(parameters.get("reason") or "").strip()
    if roller == "engine" or not _is_player(role):
        result = checks.resolve(sheet, stat, dc=dc, mode=mode)
        line = checks.describe(result) + (f" [{reason}]" if reason else "")
        checks_state.add_result(line)
        info(f"CHECK: {line}", category="character_updates")
        return {"resolved": line}
    net = checks.net_mode(sheet, stat, mode)
    if net.reason:
        warning(f"CHECK: {resolved}: roll mode not read ({net.reason}); asking for one die", category="character_updates")
    if net.mode == "fail":
        result = checks.resolve(sheet, stat, dc=dc, mode=mode)
        line = checks.describe(result) + (f" [{reason}]" if reason else "")
        checks_state.add_result(line)
        info(f"CHECK: {line}", category="character_updates")
        return {"resolved": line}
    entry = {"characterName": resolved, "stat": stat, "dc": dc, "mode": mode, "netMode": net.mode,
             "sources": net.sources, "faces": checks.faces_needed(net.mode), "reason": reason}
    if net.dice:
        # #889: an added die (Guidance, Bless) is the game's to roll.
        entry["dice"] = [{"name": d["name"], "count": d["count"], "sides": d["sides"]} for d in net.dice]
    checks_state.add_pending(entry)
    info(f"CHECK: pending for {resolved}: {checks.label(stat)} ({net.mode}, {entry['faces']} dice)", category="character_updates")
    return {"pending": entry}


def roll_prompt_text(entry: Dict[str, Any]) -> str:
    what = checks.label(entry["stat"])
    count = entry["faces"]
    why = f" ({entry['netMode']}" + (f" from {', '.join(entry['sources'])}" if entry.get("sources") else "") + ")" if count == 2 else ""
    dc = f" vs DC {entry['dc']}" if entry.get("dc") is not None else ""
    dice = f"roll {count}d20{why} and type " + ("both results (e.g. 15 3)" if count == 2 else "the result (e.g. 15)")
    added = "".join(f", plus {d['count']}d{d['sides']} from {d['name']} that the game rolls"
                    for d in entry.get("dice") or [])
    return f"{ROLL_TAG} {what} for {entry['characterName']}{dc}{added}: {dice}, or press Enter and the game rolls: "


def parse_faces(text: str, count: int) -> Optional[List[int]]:
    """Whole numbers 1-20 in the required count, or [] for a blank line; None when it is neither."""
    if text is None or not text.strip():
        return []
    match = _NUMBERS.match(text)
    if not match:
        return None
    faces = [int(g) for g in match.groups() if g is not None]
    if len(faces) != count or any(f < 1 or f > 20 for f in faces):
        return None
    return faces


def new_message_id() -> str:
    """A fresh player-output message id (the web cache keys a record by it)."""
    return f"msg-{uuid4().hex}"


def _show_check_receipt(content: str, message_id: Optional[str] = None) -> None:
    """Show the player the scored check at once (#530). The DM narrates it next turn without the numbers.
    A record shown again under its own ``message_id`` (a dice card, #1118) is not shown twice on the web."""
    from web.shared_state import emit_player_output, has_player_output_sink
    has_sink = has_player_output_sink()
    if emit_player_output({"type": "system", "content": content,
                           "message_id": message_id or new_message_id()}) is True:
        return
    if not has_sink:
        print(content)


def take_player_rolls(read: Callable[[str], str]) -> List[str]:
    """Persist pending checks and return their outcomes for the next narrated turn.

    The caller must not ask for another command after an accepted roll.
    Empty means no roll was submitted and ordinary input is still needed.
    """
    completed: List[str] = []
    while True:
        pending = checks_state.pending_checks()
        if not pending:
            return completed
        entry = pending[0]
        faces: Optional[List[int]] = None
        try:
            while faces is None:
                roll_prompt.publish({**entry, 'label': checks.label(entry['stat'])})
                faces = parse_faces(read(roll_prompt_text(entry)), entry["faces"])
                if faces is None:
                    print(f"Type {entry['faces']} whole number{'s' if entry['faces'] == 2 else ''} between 1 and 20, or press Enter to let the game roll.")
        finally:
            roll_prompt.publish(None)
        try:
            _resolved, _role, _path, sheet = _resolve_character(entry["characterName"])
            result = checks.resolve(sheet, entry["stat"], dc=entry.get("dc"), mode=entry.get("mode"), faces=faces or None)
        except Exception as exc:  # the sheet vanished or the engine is down: the DM hears why
            warning(f"CHECK: {entry['characterName']}: not resolved ({exc})", category="character_updates")
            line = f"{entry['characterName']} {checks.label(entry['stat'])}: not resolved (rules engine unavailable)"
            checks_state.complete_pending(entry, line)
            completed.append(line)
            continue
        line = checks.describe(result) + (f" [{entry['reason']}]" if entry.get("reason") else "")
        checks_state.complete_pending(entry, line)
        # The rules command is not ordinary chat input. Publish its accepted
        # dice separately as the player's reply, including engine-rolled dice,
        # before the next DM narration. Keep totals/mechanics in the DM context.
        if result.ok and result.faces:
            from web.shared_state import emit_player_output
            dice = [f"{face} on a d20" for face in result.faces]
            rolled = " and ".join(dice)
            emit_player_output({'type': 'user-input', 'content': f"I rolled {rolled}."})
        if result.ok:
            _show_check_receipt(checks.describe(result))
        info(f"CHECK: {line}", category="character_updates")
        completed.append(line)


LAST_NOTE = ""  # the CHECK RESULTS delivered with the current turn's DM note (the validator reviews against it)

# A read of a person or a scene: the character's own silent observation.
_READ = re.compile(r"^(?P<who>.+?) (?P<skill>Insight|Perception) check\b(?!: not resolved)")


def read_note(line: str) -> str:
    """The narration rule for a scored read, beside its result. Replays of a
    successful Insight read on an NPC whose record says she admits a secret
    had her confess it in every draft while this rule lived only in the system
    prompt; next to the result, no draft did, and pressing her still did."""
    match = _READ.match(line)
    if not match:
        return ""
    who, skill = match.group("who"), match.group("skill")
    return (f"READ ({who}'s {skill}): a silent observation; no one in the scene knows a check was made. Narrate only what "
            f"{who} notices (tells, tension, a mismatch between words and body, a detail out of place) and what it suggests; "
            "on a failure the surface stays consistent or the signs are ambiguous. In this response no NPC confesses, explains "
            "or names what they are hiding, even if their record says they admit it: that disclosure waits until the player "
            "presses, asks or persuades them. Then stop and leave the next move to the player.\n")


def check_results_note(turn_marker=None) -> str:
    """turn_marker: the count of DM replies in the history (the turn this note is for); see checks_state.consume_results."""
    global LAST_NOTE
    lines = checks_state.consume_results(turn_marker)
    if not lines:
        LAST_NOTE = ""
        return ""
    LAST_NOTE = ("\nCHECK RESULTS (the rules engine scored the attempts you left unresolved last turn; open this response by narrating "
                 "each outcome in story terms, then answer the new input; never re-roll or re-add; the player already sees "
                 "these numbers on the dice receipt, so do not restate dice, bonus, total, DC or margin): "
                 + " | ".join(lines) + "\n" + "".join(read_note(line) for line in lines))
    return LAST_NOTE


def validation_context() -> str:
    """What the validator must know: the engine already scored these checks and the DM was told to narrate them."""
    if not LAST_NOTE:
        return ""
    return ("The Dungeon Master Note for this turn carried the rules engine's scored check results below. The candidate "
            "is REQUIRED to narrate each outcome (success or failure and what it means in the scene) as a settled fact; "
            "a candidate that calls such a check pending or unresolved, contradicts its success or failure, or asks for "
            "its dice again, is invalid. The dice, bonus, total, DC and margin are the engine's and the player already "
            "sees them on the dice receipt: do NOT require the narration to state any of these numbers, and do not reject "
            "a candidate for leaving them out. Numbers the player typed in chat are not dice; only these lines are. A READ "
            "line governs how its read is narrated: a candidate in which an NPC confesses, explains or names what they are "
            "hiding in answer to that read is invalid." + LAST_NOTE)
